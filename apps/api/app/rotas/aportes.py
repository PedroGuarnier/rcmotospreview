from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import schemas
from app.db import obter_db
from app.models import Aporte, Usuario
from app.permissoes import P, exigir
from app.tempo import hoje

router = APIRouter(prefix="/aportes", tags=["aportes"])


def _serializar(a: Aporte) -> schemas.AporteOut:
    return schemas.AporteOut(
        id=a.id,
        data=a.data,
        valor=a.valor,
        descricao=a.descricao,
        registrado_por=a.registrado_por.nome if a.registrado_por else None,
    )


@router.get("", response_model=schemas.AportesOut)
def listar(_: Usuario = Depends(exigir(P.aportes_ver)), db: Session = Depends(obter_db)):
    aportes = db.scalars(
        select(Aporte)
        .options(selectinload(Aporte.registrado_por))
        .order_by(Aporte.data.desc(), Aporte.id.desc())
    ).all()
    return schemas.AportesOut(
        itens=[_serializar(a) for a in aportes],
        total=sum((a.valor for a in aportes), Decimal("0.00")),
    )


@router.post("", response_model=schemas.AporteOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: schemas.AporteCriar,
    usuario: Usuario = Depends(exigir(P.aportes_ver)),
    db: Session = Depends(obter_db),
):
    data = dados.data or hoje()
    if data > hoje():
        raise HTTPException(422, "A data não pode ser futura.")
    aporte = Aporte(
        data=data, valor=dados.valor, descricao=dados.descricao, registrado_por_id=usuario.id
    )
    db.add(aporte)
    db.commit()
    db.refresh(aporte)
    return _serializar(aporte)


@router.delete("/{aporte_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(
    aporte_id: int,
    # Excluir é só do dono, mesmo que outra pessoa esteja habilitada a ver.
    _: Usuario = Depends(exigir(P.aportes_ver, P.usuarios_gerir)),
    db: Session = Depends(obter_db),
):
    aporte = db.get(Aporte, aporte_id)
    if aporte is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aporte não encontrado.")
    db.delete(aporte)
    db.commit()
