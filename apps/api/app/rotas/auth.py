from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.audit import registrar_evento
from app.config import obter_config
from app.db import obter_db
from app.models import Usuario
from app.permissoes import permissoes_de, usuario_atual
from app.security import conferir_senha, criar_token, gerar_hash

router = APIRouter(prefix="/auth", tags=["auth"])


def _eu(usuario: Usuario) -> schemas.EuOut:
    return schemas.EuOut(
        **schemas.UsuarioOut.model_validate(usuario).model_dump(),
        permissoes=sorted(permissoes_de(usuario)),
        dados_demo=obter_config().dados_demo,
    )


def _gravar_cookie(resposta: Response, usuario: Usuario) -> None:
    cfg = obter_config()
    resposta.set_cookie(
        cfg.cookie_sessao,
        criar_token(usuario.id, usuario.versao_sessao),
        max_age=cfg.sessao_horas * 3600,
        httponly=True,
        secure=cfg.producao,
        samesite="lax",
        path="/",
    )


@router.post("/entrar", response_model=schemas.EuOut)
def entrar(dados: schemas.Credenciais, resposta: Response, db: Session = Depends(obter_db)):
    cfg = obter_config()
    email = dados.email.strip().lower()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email).with_for_update())
    agora = datetime.now(UTC)

    if usuario is not None and usuario.bloqueado_ate and usuario.bloqueado_ate > agora:
        minutos = max(1, int((usuario.bloqueado_ate - agora).total_seconds() // 60) + 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Muitas tentativas. Tente de novo em {minutos} min.",
        )

    senha_ok = conferir_senha(dados.senha, usuario.senha_hash if usuario else None)
    if usuario is None or not senha_ok or not usuario.ativo:
        if usuario is not None and not senha_ok:
            usuario.tentativas_login += 1
            if usuario.tentativas_login >= cfg.max_tentativas_login:
                usuario.bloqueado_ate = agora + timedelta(minutes=cfg.bloqueio_login_minutos)
                usuario.tentativas_login = 0
                registrar_evento(
                    db,
                    "bloqueou",
                    "sessao",
                    usuario=usuario,
                    resumo="Login bloqueado por tentativas",
                )
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")

    usuario.tentativas_login = 0
    usuario.bloqueado_ate = None
    registrar_evento(db, "entrou", "sessao", usuario=usuario, resumo="Entrou no sistema")
    db.commit()
    _gravar_cookie(resposta, usuario)
    return _eu(usuario)


@router.post("/sair", status_code=status.HTTP_204_NO_CONTENT)
def sair(resposta: Response):
    resposta.delete_cookie(obter_config().cookie_sessao, path="/")


@router.get("/eu", response_model=schemas.EuOut)
def eu(usuario: Usuario = Depends(usuario_atual)):
    return _eu(usuario)


@router.post("/trocar-senha", response_model=schemas.EuOut)
def trocar_senha(
    dados: schemas.TrocaSenha,
    resposta: Response,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(obter_db),
):
    if not conferir_senha(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(422, "A senha atual não confere.")
    usuario.senha_hash = gerar_hash(dados.nova_senha)
    usuario.versao_sessao += 1  # derruba as outras sessões abertas
    db.commit()
    _gravar_cookie(resposta, usuario)
    return _eu(usuario)
