from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import obter_config

_hasher = PasswordHasher()
# Hash usado quando o e-mail não existe, para o tempo de resposta não revelar isso.
_HASH_FALSO = _hasher.hash("senha-inexistente")

ALGORITMO = "HS256"


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def conferir_senha(senha: str, senha_hash: str | None) -> bool:
    try:
        return _hasher.verify(senha_hash or _HASH_FALSO, senha) and senha_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def criar_token(usuario_id: int, versao_sessao: int) -> str:
    cfg = obter_config()
    agora = datetime.now(UTC)
    payload = {
        "sub": str(usuario_id),
        "vs": versao_sessao,
        "iat": agora,
        "exp": agora + timedelta(hours=cfg.sessao_horas),
    }
    return jwt.encode(payload, cfg.segredo_jwt, algorithm=ALGORITMO)


def ler_token(token: str) -> tuple[int, int] | None:
    """Devolve (usuario_id, versao_sessao) ou None se o token for inválido/expirado."""
    try:
        dados = jwt.decode(token, obter_config().segredo_jwt, algorithms=[ALGORITMO])
        return int(dados["sub"]), int(dados["vs"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
