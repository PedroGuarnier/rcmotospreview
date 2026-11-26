"""Procura no site, para a equipe: visitas à página de cada veículo e cliques no WhatsApp.

Os números vêm de `contagem_site` (somados por veículo e por dia, sem dado de quem visitou).
Vê quem vê o estoque.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import fotos, schemas
from app.db import obter_db
from app.models import ContagemSite, Usuario, Veiculo
from app.permissoes import P, exigir
from app.tempo import hoje

router = APIRouter(prefix="/procura", tags=["procura no site"])

DIAS = 30  # janela de "últimos 30 dias", contando hoje
MAIS_PROCURADOS = 5

_CLIQUES = ContagemSite.cliques_cartao + ContagemSite.cliques_pagina + ContagemSite.cliques_proposta
_COLUNAS = {
    "visualizacoes": ContagemSite.visualizacoes,
    "cliques": _CLIQUES,
    "cliques_cartao": ContagemSite.cliques_cartao,
    "cliques_pagina": ContagemSite.cliques_pagina,
    "cliques_proposta": ContagemSite.cliques_proposta,
}


def _desde():
    return hoje() - timedelta(days=DIAS - 1)


@router.get("/veiculos/{veiculo_id}", response_model=schemas.ProcuraVeiculo)
def do_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(exigir(P.estoque_ver)),
    db: Session = Depends(obter_db),
):
    if db.get(Veiculo, veiculo_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Veículo não encontrado.")
    recente = ContagemSite.dia >= _desde()
    colunas = []
    for coluna in _COLUNAS.values():
        colunas.append(func.coalesce(func.sum(coluna).filter(recente), 0))
        colunas.append(func.coalesce(func.sum(coluna), 0))
    linha = db.execute(select(*colunas).where(ContagemSite.veiculo_id == veiculo_id)).one()
    nomes = list(_COLUNAS)
    return schemas.ProcuraVeiculo(
        dias=DIAS,
        recente=schemas.NumerosProcura(**{n: int(linha[2 * i]) for i, n in enumerate(nomes)}),
        total=schemas.NumerosProcura(**{n: int(linha[2 * i + 1]) for i, n in enumerate(nomes)}),
    )


@router.get("/mais-procurados", response_model=schemas.MaisProcurados)
def mais_procurados(
    _: Usuario = Depends(exigir(P.estoque_ver)),
    db: Session = Depends(obter_db),
):
    """Os 5 veículos com mais cliques no WhatsApp nos últimos 30 dias (empate: mais visitas)."""
    cliques = func.sum(_CLIQUES).label("cliques")
    visitas = func.sum(ContagemSite.visualizacoes).label("visitas")
    ranking = db.execute(
        select(ContagemSite.veiculo_id, cliques, visitas)
        .where(ContagemSite.dia >= _desde())
        .group_by(ContagemSite.veiculo_id)
        .having((func.sum(_CLIQUES) + func.sum(ContagemSite.visualizacoes)) > 0)
        .order_by(cliques.desc(), visitas.desc(), ContagemSite.veiculo_id)
        .limit(MAIS_PROCURADOS)
    ).all()
    veiculos = {
        v.id: v
        for v in db.scalars(
            select(Veiculo)
            .where(Veiculo.id.in_([linha.veiculo_id for linha in ranking]))
            .options(selectinload(Veiculo.fotos))
        )
    }
    return schemas.MaisProcurados(
        dias=DIAS,
        veiculos=[
            schemas.VeiculoProcurado(
                id=v.id,
                descricao=v.descricao,
                situacao=v.situacao,
                foto_capa=fotos.url(v.fotos[0].miniatura) if v.fotos else None,
                visualizacoes=int(linha.visitas),
                cliques=int(linha.cliques),
            )
            for linha in ranking
            if (v := veiculos.get(linha.veiculo_id)) is not None
        ],
    )
