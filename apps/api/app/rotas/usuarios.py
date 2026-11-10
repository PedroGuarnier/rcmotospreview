from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import obter_db
from app.models import Perfil, Usuario
from app.permissoes import P, exigir, usuario_atual
from app.security import gerar_hash

router = APIRouter(prefix="/usuarios", tags=["usuários"])


def _obter(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return usuario


def _email_livre(db: Session, email: str, ignorar_id: int | None = None) -> None:
    existente = db.scalar(select(Usuario).where(Usuario.email == email))
    if existente is not None and existente.id != ignorar_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um usuário com este e-mail.")


def _outro_dono_ativo(db: Session, exceto_id: int) -> bool:
    return (
        db.scalar(
            select(Usuario.id).where(
                Usuario.perfil == Perfil.dono, Usuario.ativo, Usuario.id != exceto_id
            )
        )
        is not None
    )


@router.get("/vendedores", response_model=list[schemas.PessoaRef])
def listar_vendedores(_: Usuario = Depends(usuario_atual), db: Session = Depends(obter_db)):
    """Usuários ativos, para escolher o vendedor na baixa de venda."""
    return db.scalars(select(Usuario).where(Usuario.ativo).order_by(Usuario.nome)).all()


@router.get("", response_model=list[schemas.UsuarioOut])
def listar(_: Usuario = Depends(exigir(P.usuarios_gerir)), db: Session = Depends(obter_db)):
    return db.scalars(select(Usuario).order_by(Usuario.ativo.desc(), Usuario.nome)).all()


@router.post("", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: schemas.UsuarioCriar,
    _: Usuario = Depends(exigir(P.usuarios_gerir)),
    db: Session = Depends(obter_db),
):
    email = dados.email.lower()
    _email_livre(db, email)
    usuario = Usuario(
        nome=dados.nome,
        email=email,
        senha_hash=gerar_hash(dados.senha),
        perfil=dados.perfil,
        acesso_aportes=dados.acesso_aportes or dados.perfil == Perfil.dono,
        comissao_regra=dados.comissao_regra,
        comissao_valor=dados.comissao_valor if dados.comissao_regra else None,
    )
    db.add(usuario)
    db.commit()
    return usuario


@router.patch("/{usuario_id}", response_model=schemas.UsuarioOut)
def atualizar(
    usuario_id: int,
    dados: schemas.UsuarioAtualizar,
    eu: Usuario = Depends(exigir(P.usuarios_gerir)),
    db: Session = Depends(obter_db),
):
    usuario = _obter(db, usuario_id)
    campos = dados.model_dump(exclude_unset=True)

    deixa_de_ser_dono = usuario.perfil == Perfil.dono and (
        campos.get("perfil", Perfil.dono) != Perfil.dono or campos.get("ativo") is False
    )
    if deixa_de_ser_dono and not _outro_dono_ativo(db, usuario.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A loja precisa ter pelo menos um dono ativo."
        )
    if "email" in campos:
        campos["email"] = campos["email"].lower()
        _email_livre(db, campos["email"], ignorar_id=usuario.id)
    if "comissao_regra" in campos and campos["comissao_regra"] is None:
        campos["comissao_valor"] = None

    perfil_antes = usuario.perfil
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)
    if usuario.perfil == Perfil.dono:
        usuario.acesso_aportes = True
    if campos.get("ativo") is False or usuario.perfil != perfil_antes:
        usuario.versao_sessao += 1  # perde o acesso antigo na hora
    db.commit()
    return usuario


@router.post("/{usuario_id}/redefinir-senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(
    usuario_id: int,
    dados: schemas.NovaSenha,
    _: Usuario = Depends(exigir(P.usuarios_gerir)),
    db: Session = Depends(obter_db),
):
    usuario = _obter(db, usuario_id)
    usuario.senha_hash = gerar_hash(dados.nova_senha)
    usuario.versao_sessao += 1
    usuario.tentativas_login = 0
    usuario.bloqueado_ate = None
    db.commit()
