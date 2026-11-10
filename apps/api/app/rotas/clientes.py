from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import schemas
from app.db import obter_db
from app.models import Cliente, Usuario
from app.permissoes import P, exigir
from app.validacao import so_digitos

router = APIRouter(prefix="/clientes", tags=["clientes"])


def _cpf_livre(db: Session, cpf_cnpj: str | None, ignorar_id: int | None = None) -> None:
    if not cpf_cnpj:
        return
    outro = db.scalar(select(Cliente).where(Cliente.cpf_cnpj == cpf_cnpj))
    if outro is not None and outro.id != ignorar_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Este CPF/CNPJ já está cadastrado: {outro.nome}."
        )


@router.get("", response_model=list[schemas.ClienteOut])
def listar(
    busca: str | None = None,
    _: Usuario = Depends(exigir(P.clientes_ver)),
    db: Session = Depends(obter_db),
):
    consulta = select(Cliente)
    if busca and busca.strip():
        termo = busca.strip()
        filtros = [Cliente.nome.ilike(f"%{termo}%")]
        digitos = so_digitos(termo)
        if len(digitos) >= 3:
            filtros += [
                Cliente.cpf_cnpj.like(f"%{digitos}%"),
                Cliente.telefone.like(f"%{digitos}%"),
            ]
        consulta = consulta.where(or_(*filtros))
    return db.scalars(consulta.order_by(Cliente.nome).limit(30)).all()


@router.post("", response_model=schemas.ClienteOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: schemas.ClienteCriar,
    _: Usuario = Depends(exigir(P.vendas_registrar)),
    db: Session = Depends(obter_db),
):
    _cpf_livre(db, dados.cpf_cnpj)
    cliente = Cliente(**dados.model_dump())
    db.add(cliente)
    db.commit()
    return cliente


@router.patch("/{cliente_id}", response_model=schemas.ClienteOut)
def atualizar(
    cliente_id: int,
    dados: schemas.ClienteAtualizar,
    _: Usuario = Depends(exigir(P.vendas_ver_todas)),
    db: Session = Depends(obter_db),
):
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente não encontrado.")
    campos = dados.model_dump(exclude_unset=True)
    if campos.get("nome", cliente.nome) is None:
        raise HTTPException(422, "O nome é obrigatório.")
    _cpf_livre(db, campos.get("cpf_cnpj"), ignorar_id=cliente.id)
    for campo, valor in campos.items():
        setattr(cliente, campo, valor)
    db.commit()
    return cliente
