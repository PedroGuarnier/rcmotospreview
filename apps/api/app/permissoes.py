"""Hierarquia de acesso (CLAUDE.md, "Perfis e permissões").

A matriz fica só aqui: a API valida com `exigir(...)` e a interface recebe a lista
pronta em /auth/eu, sem duplicar a regra.
"""

import enum

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import obter_config
from app.db import obter_db
from app.models import Perfil, Usuario
from app.security import ler_token


class P(enum.StrEnum):
    estoque_ver = "estoque.ver"
    estoque_editar = "estoque.editar"
    custos_ver = "custos.ver"  # valor de compra, custos e lucro
    vendas_registrar = "vendas.registrar"
    vendas_ver_todas = "vendas.ver_todas"
    vendas_cancelar = "vendas.cancelar"
    clientes_ver = "clientes.ver"
    comissoes_ver_todas = "comissoes.ver_todas"
    comissoes_pagar = "comissoes.pagar"
    painel_ver = "painel.ver"
    usuarios_gerir = "usuarios.gerir"
    aportes_ver = "aportes.ver"
    historico_ver = "historico.ver"
    historico_veiculo_ver = "historico.veiculo_ver"


MATRIZ: dict[Perfil, frozenset[P]] = {
    Perfil.dono: frozenset(P),
    Perfil.gerente: frozenset(
        {
            P.estoque_ver,
            P.estoque_editar,
            P.custos_ver,
            P.vendas_registrar,
            P.vendas_ver_todas,
            P.vendas_cancelar,
            P.clientes_ver,
            P.comissoes_ver_todas,
            P.painel_ver,
            P.historico_veiculo_ver,
        }
    ),
    Perfil.financeiro: frozenset(
        {
            P.estoque_ver,
            P.vendas_ver_todas,
            P.clientes_ver,
            P.comissoes_ver_todas,
            P.comissoes_pagar,
        }
    ),
    Perfil.vendedor: frozenset({P.estoque_ver, P.vendas_registrar, P.clientes_ver}),
}


def permissoes_de(usuario: Usuario) -> frozenset[P]:
    base = MATRIZ[usuario.perfil]
    if usuario.acesso_aportes:
        base = base | {P.aportes_ver}
    return base


def pode(usuario: Usuario, permissao: P) -> bool:
    return permissao in permissoes_de(usuario)


def usuario_atual(request: Request, db: Session = Depends(obter_db)) -> Usuario:
    nao_autenticado = HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar.")
    token = request.cookies.get(obter_config().cookie_sessao)
    lido = ler_token(token) if token else None
    if lido is None:
        raise nao_autenticado
    usuario_id, versao = lido
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo or usuario.versao_sessao != versao:
        raise nao_autenticado
    # O audit log lê quem está agindo a partir da sessão do banco.
    db.info["usuario"] = usuario
    return usuario


def exigir(*permissoes: P):
    """Dependência: o usuário logado precisa ter todas as permissões informadas."""

    def _dep(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        faltando = [p for p in permissoes if not pode(usuario, p)]
        if faltando:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Seu perfil não tem acesso a esta função."
            )
        return usuario

    return _dep
