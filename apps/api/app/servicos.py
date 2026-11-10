"""Regras de negócio de vendas, lucro e comissão."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.models import (
    Cliente,
    Comissao,
    RegraComissao,
    Situacao,
    StatusComissao,
    StatusVenda,
    Usuario,
    Veiculo,
    Venda,
)
from app.permissoes import P, pode
from app.tempo import hoje

CENTAVO = Decimal("0.01")


def erro(codigo: int, mensagem: str) -> HTTPException:
    return HTTPException(codigo, mensagem)


def calcular_lucro(valor_venda: Decimal, valor_compra: Decimal, total_custos: Decimal) -> Decimal:
    """Lucro = venda − compra − custos (contrato, cláusula 1)."""
    return valor_venda - valor_compra - total_custos


def calcular_comissao(
    regra: RegraComissao, regra_valor: Decimal, valor_venda: Decimal, lucro: Decimal
) -> Decimal:
    if regra == RegraComissao.valor_fixo:
        bruto = regra_valor
    elif regra == RegraComissao.percentual_venda:
        bruto = valor_venda * regra_valor / 100
    else:  # percentual do lucro: venda no prejuízo não gera comissão negativa
        bruto = max(lucro, Decimal(0)) * regra_valor / 100
    return bruto.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def mudar_situacao(veiculo: Veiculo, nova: Situacao) -> None:
    if veiculo.situacao != nova:
        veiculo.situacao = nova
        veiculo.situacao_desde = datetime.now(UTC)


def _obter_ou_criar_cliente(db: Session, dados: schemas.VendaCriar) -> Cliente:
    if dados.cliente_id is not None:
        cliente = db.get(Cliente, dados.cliente_id)
        if cliente is None:
            raise erro(status.HTTP_404_NOT_FOUND, "Cliente não encontrado.")
        return cliente
    novo = dados.cliente_novo
    assert novo is not None
    if novo.cpf_cnpj:
        existente = db.scalar(select(Cliente).where(Cliente.cpf_cnpj == novo.cpf_cnpj))
        if existente:
            return existente
    cliente = Cliente(**novo.model_dump())
    db.add(cliente)
    return cliente


def registrar_venda(db: Session, dados: schemas.VendaCriar, usuario: Usuario) -> Venda:
    # Trava a linha do veículo: duas baixas simultâneas não vendem a mesma moto duas vezes.
    veiculo = db.scalar(select(Veiculo).where(Veiculo.id == dados.veiculo_id).with_for_update())
    if veiculo is None:
        raise erro(status.HTTP_404_NOT_FOUND, "Veículo não encontrado.")
    if veiculo.situacao != Situacao.a_venda:
        raise erro(
            status.HTTP_409_CONFLICT,
            "Este veículo não está à venda. Mude a situação para “à venda” antes de dar baixa."
            if veiculo.venda_ativa is None
            else "Este veículo já foi vendido.",
        )

    vendedor_id = dados.vendedor_id or usuario.id
    if not pode(usuario, P.vendas_ver_todas) and vendedor_id != usuario.id:
        raise erro(status.HTTP_403_FORBIDDEN, "Você só pode registrar vendas em seu nome.")
    vendedor = db.get(Usuario, vendedor_id)
    if vendedor is None or not vendedor.ativo:
        raise erro(422, "Vendedor inválido ou desativado.")

    data_venda = dados.data_venda or hoje()
    if data_venda > hoje():
        raise erro(422, "A data da venda não pode ser futura.")

    cliente = _obter_ou_criar_cliente(db, dados)
    total_custos = veiculo.total_custos
    lucro = calcular_lucro(dados.valor, veiculo.valor_compra, total_custos)
    venda = Venda(
        veiculo=veiculo,
        cliente=cliente,
        vendedor=vendedor,
        registrada_por_id=usuario.id,
        data_venda=data_venda,
        valor=dados.valor,
        forma=dados.forma,
        banco=dados.banco,
        entrada=dados.entrada,
        numero_parcelas=dados.numero_parcelas,
        valor_parcela=dados.valor_parcela,
        primeiro_vencimento=dados.primeiro_vencimento,
        valor_compra=veiculo.valor_compra,
        total_custos=total_custos,
        lucro=lucro,
        observacoes=dados.observacoes,
        status=StatusVenda.ativa,
    )
    db.add(venda)
    if vendedor.comissao_regra is not None and vendedor.comissao_valor is not None:
        venda.comissao = Comissao(
            vendedor_id=vendedor.id,
            regra=vendedor.comissao_regra,
            regra_valor=vendedor.comissao_valor,
            valor=calcular_comissao(
                vendedor.comissao_regra, vendedor.comissao_valor, dados.valor, lucro
            ),
            status=StatusComissao.pendente,
        )
    mudar_situacao(veiculo, Situacao.vendido)
    return venda


def cancelar_venda(db: Session, venda: Venda, motivo: str, usuario: Usuario) -> None:
    if venda.status != StatusVenda.ativa:
        raise erro(status.HTTP_409_CONFLICT, "Esta venda já está cancelada.")
    if venda.comissao is not None and venda.comissao.status == StatusComissao.paga:
        raise erro(
            status.HTTP_409_CONFLICT,
            "A comissão desta venda já foi paga. Desfaça o pagamento antes de cancelar.",
        )
    venda.status = StatusVenda.cancelada
    venda.cancelada_em = datetime.now(UTC)
    venda.cancelada_por_id = usuario.id
    venda.motivo_cancelamento = motivo
    if venda.comissao is not None:
        venda.comissao.status = StatusComissao.cancelada
    mudar_situacao(venda.veiculo, Situacao.a_venda)


def recalcular_venda_do_veiculo(veiculo: Veiculo) -> None:
    """Custo lançado/removido ou valor de compra corrigido depois da venda: refaz o lucro.

    A comissão acompanha enquanto estiver pendente; depois de paga, fica como foi paga.
    """
    venda = veiculo.venda_ativa
    if venda is None:
        return
    venda.valor_compra = veiculo.valor_compra
    venda.total_custos = veiculo.total_custos
    venda.lucro = calcular_lucro(venda.valor, venda.valor_compra, venda.total_custos)
    comissao = venda.comissao
    if comissao is not None and comissao.status == StatusComissao.pendente:
        comissao.valor = calcular_comissao(
            comissao.regra, comissao.regra_valor, venda.valor, venda.lucro
        )
