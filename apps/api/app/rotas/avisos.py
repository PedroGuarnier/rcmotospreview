"""Avisos de prazo dentro da plataforma: débitos dos veículos e transferência pelo comprador.

Não há tabela de avisos: a lista é calculada na hora a partir dos prazos, então nunca fica
desatualizada. Cada pessoa vê só o que o perfil dela permite.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import schemas, servicos
from app.db import obter_db
from app.models import DebitoVeiculo, StatusDebito, StatusVenda, Usuario, Venda
from app.permissoes import P, pode, usuario_atual
from app.rotas.vendas import prazo_transferencia
from app.tempo import hoje

router = APIRouter(prefix="/avisos", tags=["avisos"])

_TIPO = {"ipva": "IPVA", "licenciamento": "Licenciamento", "multa": "Multa", "outro": "Débito"}


def _quando(dias: int) -> str:
    if dias < 0:
        return f"venceu há {-dias} {'dia' if dias == -1 else 'dias'}"
    if dias == 0:
        return "vence hoje"
    return f"vence em {dias} {'dia' if dias == 1 else 'dias'}"


def avisos_de_debitos(db: Session) -> list[schemas.AvisoOut]:
    dia = hoje()
    debitos = db.scalars(
        select(DebitoVeiculo)
        .where(DebitoVeiculo.status == StatusDebito.aberto)
        .options(selectinload(DebitoVeiculo.veiculo))
    )
    avisos = []
    for debito in debitos:
        nivel = servicos.nivel_do_debito(debito.prazo, dia)
        if nivel == "ok":
            continue  # faltam mais de 15 dias
        restantes = (debito.prazo - dia).days
        avisos.append(
            schemas.AvisoOut(
                tipo="debito",
                nivel=nivel,
                titulo=f"{_TIPO[debito.tipo.value]}: {debito.descricao}",
                detalhe=f"{debito.veiculo.descricao} — {_quando(restantes)}",
                prazo=debito.prazo,
                dias_restantes=restantes,
                veiculo_id=debito.veiculo_id,
                veiculo=debito.veiculo.descricao,
                valor=debito.valor,
            )
        )
    return avisos


def avisos_de_transferencia(db: Session) -> list[schemas.AvisoOut]:
    dia = hoje()
    vendas = db.scalars(
        select(Venda)
        .where(Venda.status == StatusVenda.ativa, Venda.transferida_em.is_(None))
        .options(selectinload(Venda.veiculo), selectinload(Venda.cliente))
    )
    avisos = []
    for venda in vendas:
        prazo = prazo_transferencia(venda)
        nivel = servicos.nivel_da_transferencia(prazo, dia)
        if nivel == "ok":
            continue  # ainda antes do 10º dia
        restantes = (prazo - dia).days
        avisos.append(
            schemas.AvisoOut(
                tipo="transferencia",
                nivel=nivel,
                titulo=f"Transferência pendente: {venda.cliente.nome}",
                detalhe=f"{venda.veiculo.descricao} — prazo de 30 dias {_quando(restantes)}",
                prazo=prazo,
                dias_restantes=restantes,
                veiculo_id=venda.veiculo_id,
                veiculo=venda.veiculo.descricao,
                venda_id=venda.id,
                cliente_nome=venda.cliente.nome,
                cliente_telefone=venda.cliente.telefone,
            )
        )
    return avisos


@router.get("", response_model=schemas.AvisosOut)
def listar(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(obter_db)):
    itens: list[schemas.AvisoOut] = []
    if pode(usuario, P.custos_ver):  # débito tem valor: dono e gerente
        itens += avisos_de_debitos(db)
    if pode(usuario, P.transferencia_gerir):  # dono, gerente e financeiro
        itens += avisos_de_transferencia(db)
    itens.sort(key=lambda a: (a.prazo, a.tipo))
    return schemas.AvisosOut(
        itens=itens,
        total=len(itens),
        urgentes=sum(a.nivel in ("vencido", "hoje", "urgente") for a in itens),
    )
