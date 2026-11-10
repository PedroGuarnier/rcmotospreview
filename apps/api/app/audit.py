"""Audit log automático.

Toda criação, alteração e exclusão feita pelo ORM vira uma linha em `audit_log`,
na mesma transação — não depende de cada rota lembrar de registrar.
Quem está agindo vem de `session.info["usuario"]` (preenchido em `usuario_atual`).
"""

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import event, insert
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.models import (
    Aporte,
    AuditLog,
    Cliente,
    Comissao,
    CustoVeiculo,
    FotoVeiculo,
    LaudoProcedencia,
    Usuario,
    Veiculo,
    Venda,
)

ENTIDADES: dict[type, str] = {
    Usuario: "usuario",
    Veiculo: "veiculo",
    CustoVeiculo: "custo",
    FotoVeiculo: "foto",
    Cliente: "cliente",
    Venda: "venda",
    Comissao: "comissao",
    Aporte: "aporte",
    LaudoProcedencia: "laudo",
}

# Campos de controle que não interessam ao histórico.
IGNORAR = {
    "criado_em",
    "atualizado_em",
    "tentativas_login",
    "bloqueado_ate",
    "versao_sessao",
    "situacao_desde",
    "dados",  # corpo do laudo de procedência (grande; o laudo em si fica guardado)
}
SECRETOS = {"senha_hash"}


def _json(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return str(valor.quantize(Decimal("0.01")))  # todo Decimal do sistema é dinheiro
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, enum.Enum):
        return valor.value
    return valor


def _rotulo(obj: Any) -> str:
    if isinstance(obj, Veiculo):
        return obj.descricao
    if isinstance(obj, Usuario | Cliente):
        return obj.nome
    if isinstance(obj, CustoVeiculo | Aporte):
        return obj.descricao
    if isinstance(obj, LaudoProcedencia):
        return f"da placa {obj.placa}"
    return f"nº {obj.id}"


def _veiculo_id(obj: Any) -> int | None:
    if isinstance(obj, Veiculo):
        return obj.id
    return getattr(obj, "veiculo_id", None)


def _colunas(obj: Any) -> list[str]:
    return [a.key for a in sa_inspect(obj).mapper.column_attrs]


def _retrato(obj: Any) -> dict:
    dados = {}
    for chave in _colunas(obj):
        if chave in IGNORAR or chave in SECRETOS or chave == "id":
            continue
        valor = getattr(obj, chave)
        if valor is not None:
            dados[chave] = _json(valor)
    return dados


def _diferencas(obj: Any) -> dict:
    estado = sa_inspect(obj)
    dif = {}
    for chave in _colunas(obj):
        if chave in IGNORAR:
            continue
        hist = estado.attrs[chave].history
        if not hist.has_changes():
            continue
        if chave in SECRETOS:
            dif["senha"] = {"de": "•••", "para": "(alterada)"}
            continue
        antes = hist.deleted[0] if hist.deleted else None
        depois = hist.added[0] if hist.added else None
        if antes != depois:
            dif[chave] = {"de": _json(antes), "para": _json(depois)}
    return dif


def _linha(session: Session, acao: str, obj: Any, alteracoes: dict | None) -> dict:
    usuario: Usuario | None = session.info.get("usuario")
    return {
        "usuario_id": usuario.id if usuario else None,
        "usuario_nome": usuario.nome if usuario else None,
        "acao": acao,
        "entidade": ENTIDADES[type(obj)],
        "entidade_id": obj.id,
        "veiculo_id": _veiculo_id(obj),
        "resumo": _rotulo(obj)[:300],
        "alteracoes": alteracoes or None,
    }


def _apos_flush(session: Session, _contexto: Any) -> None:
    linhas: list[dict] = []
    for obj in session.new:
        if type(obj) in ENTIDADES:
            linhas.append(_linha(session, "criou", obj, _retrato(obj)))
    for obj in session.dirty:
        if type(obj) in ENTIDADES and session.is_modified(obj):
            dif = _diferencas(obj)
            if dif:
                linhas.append(_linha(session, "alterou", obj, dif))
    for obj in session.deleted:
        if type(obj) in ENTIDADES:
            linhas.append(_linha(session, "excluiu", obj, _retrato(obj)))
    if linhas:
        session.connection().execute(insert(AuditLog.__table__), linhas)


def registrar_evento(
    session: Session,
    acao: str,
    entidade: str,
    *,
    usuario: Usuario | None = None,
    entidade_id: int | None = None,
    veiculo_id: int | None = None,
    resumo: str | None = None,
    alteracoes: dict | None = None,
) -> None:
    """Registra um evento que não é mudança de tabela (login, saída, tentativa bloqueada)."""
    usuario = usuario or session.info.get("usuario")
    session.connection().execute(
        insert(AuditLog.__table__),
        [
            {
                "usuario_id": usuario.id if usuario else None,
                "usuario_nome": usuario.nome if usuario else None,
                "acao": acao,
                "entidade": entidade,
                "entidade_id": entidade_id,
                "veiculo_id": veiculo_id,
                "resumo": resumo[:300] if resumo else None,
                "alteracoes": alteracoes,
            }
        ],
    )


def instalar(fabrica_sessao: Any) -> None:
    event.listen(fabrica_sessao, "after_flush", _apos_flush)
