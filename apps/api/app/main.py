from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app import audit
from app.config import obter_config
from app.db import SessionLocal
from app.rotas import (
    aportes,
    auth,
    clientes,
    comissoes,
    historico,
    painel,
    usuarios,
    veiculos,
    vendas,
)

cfg = obter_config()
audit.instalar(SessionLocal)

app = FastAPI(
    title="RC Motos Digital — API",
    version="0.1.0",
    docs_url=None if cfg.producao else "/docs",
    redoc_url=None,
    openapi_url=None if cfg.producao else "/openapi.json",
)

for modulo in (auth, usuarios, veiculos, clientes, vendas, comissoes, painel, aportes, historico):
    app.include_router(modulo.router)

cfg.uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/arquivos", StaticFiles(directory=cfg.uploads_dir), name="arquivos")


@app.exception_handler(IntegrityError)
def _conflito(_: Request, __: IntegrityError) -> JSONResponse:
    return JSONResponse(
        {"detail": "Registro duplicado ou em uso por outro cadastro."},
        status_code=status.HTTP_409_CONFLICT,
    )


_MENSAGENS = {
    "missing": "campo obrigatório",
    "string_too_short": "campo obrigatório",
    "string_too_long": "texto longo demais",
    "greater_than": "deve ser maior que zero",
    "greater_than_equal": "valor abaixo do mínimo",
    "less_than_equal": "valor acima do máximo",
    "decimal_parsing": "valor inválido",
    "decimal_max_places": "use no máximo 2 casas decimais",
    "decimal_max_digits": "valor grande demais",
    "int_parsing": "número inválido",
    "date_from_datetime_parsing": "data inválida",
    "date_parsing": "data inválida",
    "enum": "opção inválida",
}


@app.exception_handler(RequestValidationError)
def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Erros de validação em português: `detail` é uma frase pronta para mostrar na tela."""
    erros = []
    for erro in exc.errors():
        campo = next((str(p) for p in reversed(erro["loc"]) if isinstance(p, str)), "")
        campo = "" if campo == "body" else campo
        if erro["type"] == "value_error":
            mensagem = erro["msg"].removeprefix("Value error, ")
            campo = ""  # as mensagens próprias já dizem do que se trata
        else:
            mensagem = _MENSAGENS.get(erro["type"], "valor inválido")
        erros.append({"campo": campo, "mensagem": mensagem})
    frases = [f"{e['campo']}: {e['mensagem']}" if e["campo"] else e["mensagem"] for e in erros]
    return JSONResponse({"detail": "; ".join(frases), "erros": erros}, status_code=422)


@app.get("/saude", tags=["infra"])
def saude() -> dict:
    return {"status": "ok"}
