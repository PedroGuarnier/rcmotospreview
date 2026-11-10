from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import obter_db
from app.models import AuditLog, Usuario
from app.permissoes import P, exigir

router = APIRouter(prefix="/historico", tags=["histórico"])


@router.get("", response_model=list[schemas.EventoOut])
def listar(
    entidade: str | None = None,
    usuario_id: int | None = None,
    antes_de: int | None = Query(None, description="Paginação: id do último evento já visto"),
    limite: int = Query(50, ge=1, le=200),
    _: Usuario = Depends(exigir(P.historico_ver)),
    db: Session = Depends(obter_db),
):
    consulta = select(AuditLog)
    if entidade:
        consulta = consulta.where(AuditLog.entidade == entidade)
    if usuario_id is not None:
        consulta = consulta.where(AuditLog.usuario_id == usuario_id)
    if antes_de is not None:
        consulta = consulta.where(AuditLog.id < antes_de)
    return db.scalars(consulta.order_by(AuditLog.id.desc()).limit(limite)).all()
