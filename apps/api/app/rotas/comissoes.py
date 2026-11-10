from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import schemas
from app.db import obter_db
from app.models import Comissao, StatusComissao, Usuario, Venda
from app.permissoes import P, exigir, pode, usuario_atual
from app.rotas.vendas import intervalo_do_mes
from app.tempo import hoje

router = APIRouter(prefix="/comissoes", tags=["comissões"])

ZERO = Decimal("0.00")


def _serializar(c: Comissao) -> schemas.ComissaoOut:
    return schemas.ComissaoOut(
        id=c.id,
        valor=c.valor,
        status=c.status,
        regra=c.regra,
        regra_valor=c.regra_valor,
        paga_em=c.paga_em,
        vendedor=schemas.PessoaRef.model_validate(c.vendedor),
        venda_id=c.venda_id,
        data_venda=c.venda.data_venda,
        valor_venda=c.venda.valor,
        veiculo=c.venda.veiculo.descricao,
    )


def agrupar_por_vendedor(itens: list[schemas.ComissaoOut]) -> list[schemas.ComissaoPorVendedor]:
    grupos: dict[int, schemas.ComissaoPorVendedor] = {}
    for item in itens:
        g = grupos.setdefault(
            item.vendedor.id,
            schemas.ComissaoPorVendedor(
                vendedor=item.vendedor, vendas=0, total=ZERO, pago=ZERO, pendente=ZERO
            ),
        )
        g.vendas += 1
        g.total += item.valor
        if item.status == StatusComissao.paga:
            g.pago += item.valor
        else:
            g.pendente += item.valor
    return sorted(grupos.values(), key=lambda g: g.total, reverse=True)


def relatorio(db: Session, mes: str, vendedor_id: int | None) -> schemas.RelatorioComissoes:
    inicio, fim = intervalo_do_mes(mes)
    consulta = (
        select(Comissao)
        .join(Comissao.venda)
        .where(
            Venda.data_venda >= inicio,
            Venda.data_venda < fim,
            Comissao.status != StatusComissao.cancelada,
        )
        .options(
            selectinload(Comissao.vendedor),
            selectinload(Comissao.venda).selectinload(Venda.veiculo),
        )
        .order_by(Venda.data_venda.desc(), Comissao.id.desc())
    )
    if vendedor_id is not None:
        consulta = consulta.where(Comissao.vendedor_id == vendedor_id)
    itens = [_serializar(c) for c in db.scalars(consulta)]
    por_vendedor = agrupar_por_vendedor(itens)
    return schemas.RelatorioComissoes(
        mes=mes,
        itens=itens,
        por_vendedor=por_vendedor,
        total=sum((g.total for g in por_vendedor), ZERO),
        pendente=sum((g.pendente for g in por_vendedor), ZERO),
    )


@router.get("", response_model=schemas.RelatorioComissoes)
def listar(
    mes: str | None = Query(None, description="AAAA-MM (padrão: mês atual)"),
    vendedor_id: int | None = None,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(obter_db),
):
    """Relatório de comissões do mês. O vendedor vê só as próprias."""
    if not pode(usuario, P.comissoes_ver_todas):
        vendedor_id = usuario.id
    return relatorio(db, mes or hoje().strftime("%Y-%m"), vendedor_id)


def _obter(db: Session, comissao_id: int) -> Comissao:
    comissao = db.scalar(
        select(Comissao)
        .where(Comissao.id == comissao_id)
        .options(
            selectinload(Comissao.vendedor),
            selectinload(Comissao.venda).selectinload(Venda.veiculo),
        )
        .with_for_update(of=Comissao)
    )
    if comissao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comissão não encontrada.")
    return comissao


@router.post("/{comissao_id}/pagar", response_model=schemas.ComissaoOut)
def pagar(
    comissao_id: int,
    _: Usuario = Depends(exigir(P.comissoes_pagar)),
    db: Session = Depends(obter_db),
):
    comissao = _obter(db, comissao_id)
    if comissao.status != StatusComissao.pendente:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta comissão não está pendente.")
    comissao.status = StatusComissao.paga
    comissao.paga_em = datetime.now(UTC)
    db.commit()
    return _serializar(comissao)


@router.post("/{comissao_id}/desfazer-pagamento", response_model=schemas.ComissaoOut)
def desfazer_pagamento(
    comissao_id: int,
    _: Usuario = Depends(exigir(P.comissoes_pagar)),
    db: Session = Depends(obter_db),
):
    comissao = _obter(db, comissao_id)
    if comissao.status != StatusComissao.paga:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta comissão não está paga.")
    comissao.status = StatusComissao.pendente
    comissao.paga_em = None
    db.commit()
    return _serializar(comissao)
