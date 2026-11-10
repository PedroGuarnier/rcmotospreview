from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import schemas, servicos
from app.db import obter_db
from app.models import StatusVenda, Usuario, Venda
from app.permissoes import P, exigir, pode, usuario_atual

router = APIRouter(prefix="/vendas", tags=["vendas"])

_CARGA = (
    selectinload(Venda.veiculo),
    selectinload(Venda.cliente),
    selectinload(Venda.vendedor),
    selectinload(Venda.comissao),
)


def intervalo_do_mes(mes: str) -> tuple[date, date]:
    """'AAAA-MM' → (primeiro dia, primeiro dia do mês seguinte)."""
    try:
        ano, numero = (int(p) for p in mes.split("-"))
        inicio = date(ano, numero, 1)
    except ValueError as exc:
        raise HTTPException(422, "Mês inválido. Use AAAA-MM.") from exc
    fim = date(ano + 1, 1, 1) if numero == 12 else date(ano, numero + 1, 1)
    return inicio, fim


def serializar(venda: Venda, usuario: Usuario) -> schemas.VendaOut:
    propria = venda.vendedor_id == usuario.id
    dados = {
        "id": venda.id,
        "data_venda": venda.data_venda,
        "valor": venda.valor,
        "forma": venda.forma,
        "status": venda.status,
        "veiculo": schemas.VeiculoRef(
            id=venda.veiculo.id,
            descricao=venda.veiculo.descricao,
            tipo=venda.veiculo.tipo,
            placa=venda.veiculo.placa,
        ),
        "cliente": schemas.ClienteOut.model_validate(venda.cliente),
        "vendedor": schemas.PessoaRef.model_validate(venda.vendedor),
        "banco": venda.banco,
        "entrada": venda.entrada,
        "numero_parcelas": venda.numero_parcelas,
        "valor_parcela": venda.valor_parcela,
        "primeiro_vencimento": venda.primeiro_vencimento,
        "observacoes": venda.observacoes,
        "motivo_cancelamento": venda.motivo_cancelamento,
        "cancelada_em": venda.cancelada_em,
    }
    if pode(usuario, P.custos_ver):
        dados.update(
            valor_compra=venda.valor_compra, total_custos=venda.total_custos, lucro=venda.lucro
        )
    if venda.comissao is not None and (pode(usuario, P.comissoes_ver_todas) or propria):
        c = venda.comissao
        dados["comissao"] = schemas.ComissaoResumo(
            id=c.id, valor=c.valor, status=c.status, regra=c.regra, regra_valor=c.regra_valor
        )
    return schemas.VendaOut(**dados)


def _obter(db: Session, venda_id: int, usuario: Usuario) -> Venda:
    venda = db.scalar(select(Venda).where(Venda.id == venda_id).options(*_CARGA))
    # Venda de outro vendedor responde 404, para não revelar que existe.
    if venda is None or not (pode(usuario, P.vendas_ver_todas) or venda.vendedor_id == usuario.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Venda não encontrada.")
    return venda


@router.get("", response_model=list[schemas.VendaOut])
def listar(
    mes: str | None = Query(None, description="AAAA-MM"),
    vendedor_id: int | None = None,
    incluir_canceladas: bool = False,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(obter_db),
):
    consulta = select(Venda).options(*_CARGA)
    if not pode(usuario, P.vendas_ver_todas):
        consulta = consulta.where(Venda.vendedor_id == usuario.id)
    elif vendedor_id is not None:
        consulta = consulta.where(Venda.vendedor_id == vendedor_id)
    if mes:
        inicio, fim = intervalo_do_mes(mes)
        consulta = consulta.where(Venda.data_venda >= inicio, Venda.data_venda < fim)
    if not incluir_canceladas:
        consulta = consulta.where(Venda.status == StatusVenda.ativa)
    consulta = consulta.order_by(Venda.data_venda.desc(), Venda.id.desc()).limit(500)
    return [serializar(v, usuario) for v in db.scalars(consulta)]


@router.post("", response_model=schemas.VendaOut, status_code=status.HTTP_201_CREATED)
def registrar(
    dados: schemas.VendaCriar,
    usuario: Usuario = Depends(exigir(P.vendas_registrar)),
    db: Session = Depends(obter_db),
):
    venda = servicos.registrar_venda(db, dados, usuario)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Não foi possível registrar: veículo já vendido ou CPF/CNPJ já cadastrado.",
        ) from exc
    return serializar(_obter(db, venda.id, usuario), usuario)


@router.get("/{venda_id}", response_model=schemas.VendaOut)
def detalhar(
    venda_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(obter_db)
):
    return serializar(_obter(db, venda_id, usuario), usuario)


@router.post("/{venda_id}/cancelar", response_model=schemas.VendaOut)
def cancelar(
    venda_id: int,
    dados: schemas.VendaCancelar,
    usuario: Usuario = Depends(exigir(P.vendas_cancelar)),
    db: Session = Depends(obter_db),
):
    venda = _obter(db, venda_id, usuario)
    servicos.cancelar_venda(db, venda, dados.motivo, usuario)
    db.commit()
    return serializar(_obter(db, venda.id, usuario), usuario)
