"""Ferramentas (tools) que a IA usa para consultar o banco. Só leitura.

Cada ferramenta reaproveita a consulta da tela correspondente (as funções das rotas e
`vendas.serializar`), então devolve exatamente o que o perfil de quem pergunta vê na tela:
o vendedor só enxerga as próprias vendas e comissões, custos e lucro só com `custos.ver`,
painel só com `painel.ver` e aportes só com `aportes.ver`. A permissão é conferida aqui
também, não só na lista de ferramentas oferecidas ao modelo.

Os resultados vão para o modelo em JSON enxuto, com valores já formatados (R$ 1.234,56 e
DD/MM/AAAA): assim ele só copia, não faz conta nem conversão.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import obter_config
from app.models import (
    FormaPagamento,
    Situacao,
    StatusComissao,
    StatusVenda,
    TipoVeiculo,
    Usuario,
    Veiculo,
    Venda,
)
from app.permissoes import P, pode
from app.rotas import aportes as rotas_aportes
from app.rotas import comissoes as rotas_comissoes
from app.rotas import painel as rotas_painel
from app.rotas import veiculos as rotas_veiculos
from app.rotas import vendas as rotas_vendas
from app.tempo import hoje

MAX_LISTA = 20  # itens de lista devolvidos ao modelo (o total vem sempre completo)
MAX_DIAS_PERIODO = 3 * 366
ZERO = Decimal("0.00")

SITUACAO = {
    Situacao.compra: "compra",
    Situacao.documentacao: "documentação",
    Situacao.preparacao: "preparação",
    Situacao.a_venda: "à venda",
    Situacao.vendido: "vendido",
    Situacao.pos_venda: "pós-venda",
    Situacao.concluido: "concluído",
}
FORMA = {
    FormaPagamento.a_vista: "à vista",
    FormaPagamento.financiado_banco: "financiado (banco)",
    FormaPagamento.parcelado_loja: "parcelado na loja",
}
STATUS_COMISSAO = {StatusComissao.pendente: "pendente", StatusComissao.paga: "paga"}


class ErroFerramenta(Exception):
    """Pedido inválido ou sem permissão: vira um tool_result com is_error, em português."""


def reais(valor: Decimal | int | None) -> str | None:
    if valor is None:
        return None
    texto = f"{abs(Decimal(valor)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-R$ {texto}" if valor < 0 else f"R$ {texto}"


def data_br(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def _mes_br(mes: str) -> str:
    ano, numero = mes.split("-")
    return f"{numero}/{ano}"


def _data(valor: Any, campo: str) -> date:
    try:
        return date.fromisoformat(str(valor))
    except ValueError as exc:
        raise ErroFerramenta(f"{campo} inválido: use AAAA-MM-DD.") from exc


def _periodo(entrada: dict) -> tuple[date, date]:
    inicio = _data(entrada.get("inicio"), "inicio")
    fim = _data(entrada.get("fim"), "fim")
    if fim < inicio:
        raise ErroFerramenta("fim é anterior ao início.")
    if (fim - inicio).days > MAX_DIAS_PERIODO:
        raise ErroFerramenta("Período longo demais: consulte no máximo 3 anos por vez.")
    return inicio, fim


def _mes(entrada: dict) -> str:
    mes = entrada.get("mes") or hoje().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", str(mes)):
        raise ErroFerramenta("mes inválido: use AAAA-MM.")
    return str(mes)


def _tipo(entrada: dict) -> TipoVeiculo | None:
    valor = entrada.get("tipo")
    if valor in (None, ""):
        return None
    try:
        return TipoVeiculo(valor)
    except ValueError as exc:
        raise ErroFerramenta("tipo inválido: use moto ou carro.") from exc


def _vendedor_por_nome(db: Session, nome: str) -> Usuario:
    padrao = f"%{nome.strip()}%"
    achados = db.scalars(select(Usuario).where(Usuario.nome.ilike(padrao)).limit(6)).all()
    if not achados:
        raise ErroFerramenta(f"Nenhum vendedor com o nome “{nome}”.")
    if len(achados) > 1:
        nomes = ", ".join(u.nome for u in achados)
        raise ErroFerramenta(f"Mais de uma pessoa com esse nome: {nomes}. Diga qual.")
    return achados[0]


def _somar(itens: list[dict], campo: str) -> Decimal:
    return sum((i[campo] for i in itens), ZERO)


def _limpo(dados: dict) -> dict:
    """Tira os campos vazios: menos tokens e nada de "null" para o modelo interpretar."""
    return {k: v for k, v in dados.items() if v not in (None, [], {})}


# ---------------------------------------------------------------------------------------
# Ferramentas
# ---------------------------------------------------------------------------------------


def consultar_vendas(db: Session, usuario: Usuario, entrada: dict) -> dict:
    inicio, fim = _periodo(entrada)
    tipo = _tipo(entrada)
    ve_todas = pode(usuario, P.vendas_ver_todas)
    ve_custos = pode(usuario, P.custos_ver)

    consulta = (
        select(Venda)
        .options(*rotas_vendas._CARGA)
        .where(
            Venda.status == StatusVenda.ativa,
            Venda.data_venda >= inicio,
            Venda.data_venda <= fim,
        )
        .order_by(Venda.data_venda.desc(), Venda.id.desc())
    )
    # A mesma regra da tela de Vendas: quem não vê todas, vê só as próprias.
    if not ve_todas:
        consulta = consulta.where(Venda.vendedor_id == usuario.id)
    elif entrada.get("vendedor"):
        vendedor = _vendedor_por_nome(db, str(entrada["vendedor"]))
        consulta = consulta.where(Venda.vendedor_id == vendedor.id)
    if tipo is not None:
        consulta = consulta.join(Venda.veiculo).where(Veiculo.tipo == tipo)
    vendas = [rotas_vendas.serializar(v, usuario) for v in db.scalars(consulta)]

    def numeros(grupo: list[schemas.VendaOut]) -> dict:
        faturamento = sum((v.valor for v in grupo), ZERO)
        dados: dict[str, Any] = {"vendas": len(grupo), "faturamento": reais(faturamento)}
        if grupo:
            dados["ticket_medio"] = reais((faturamento / len(grupo)).quantize(Decimal("0.01")))
        if ve_custos:  # serializar só preenche lucro e imposto para quem vê custos
            lucro = sum((v.lucro or ZERO for v in grupo), ZERO)
            imposto = sum((v.imposto or ZERO for v in grupo), ZERO)
            dados.update(
                lucro=reais(lucro),
                imposto_estimado=reais(imposto),
                lucro_liquido=reais(lucro - imposto),
            )
        return dados

    por_vendedor: dict[str, list[schemas.VendaOut]] = {}
    por_forma: dict[str, list[schemas.VendaOut]] = {}
    for v in vendas:
        por_vendedor.setdefault(v.vendedor.nome, []).append(v)
        por_forma.setdefault(FORMA[v.forma], []).append(v)

    lista = []
    for v in vendas[:MAX_LISTA]:
        item = {
            "data": data_br(v.data_venda),
            "veiculo": v.veiculo.descricao,
            "tipo": v.veiculo.tipo.value,
            "valor": reais(v.valor),
            "forma": FORMA[v.forma],
            "vendedor": v.vendedor.nome,
            "comprador": v.cliente.nome,
            "lucro": reais(v.lucro) if ve_custos else None,
        }
        lista.append(_limpo(item))

    return _limpo(
        {
            "periodo": f"{data_br(inicio)} a {data_br(fim)}",
            "escopo": "todas as vendas da loja" if ve_todas else "só as vendas de quem pergunta",
            "observacao": None if ve_custos else "este perfil não vê custos, lucro nem imposto",
            **numeros(vendas),
            "por_tipo": {
                t.value: numeros([v for v in vendas if v.veiculo.tipo == t])
                for t in TipoVeiculo
                if tipo in (None, t)
            },
            "por_forma_pagamento": {
                forma: {
                    "vendas": len(grupo),
                    "faturamento": reais(sum((v.valor for v in grupo), ZERO)),
                }
                for forma, grupo in por_forma.items()
            },
            "por_vendedor": [
                {"vendedor": nome, **numeros(grupo)}
                for nome, grupo in sorted(por_vendedor.items(), key=lambda par: -len(par[1]))
            ]
            if ve_todas
            else None,
            "lista": lista,
            "lista_incompleta": len(vendas) > MAX_LISTA or None,
        }
    )


_PLACA = re.compile(r"^[A-Za-z]{3}-?\d[A-Za-z0-9]\d{2}$")
_GRUPOS = {"estoque": "estoque", "vendidos": "vendidos", "todos": None}


def consultar_estoque(db: Session, usuario: Usuario, entrada: dict) -> dict:
    if not pode(usuario, P.estoque_ver):
        raise ErroFerramenta("Este perfil não tem acesso ao estoque.")
    situacao = entrada.get("situacao") or None
    if situacao is not None:
        try:
            situacao = Situacao(situacao)
        except ValueError as exc:
            raise ErroFerramenta("situacao inválida.") from exc
    grupo = entrada.get("grupo") or ("todos" if situacao else "estoque")
    if grupo not in _GRUPOS:
        raise ErroFerramenta("grupo inválido: use estoque, vendidos ou todos.")
    busca = " ".join(
        t.replace("-", "") if _PLACA.match(t) else t
        for t in str(entrada.get("busca") or "").split()
    )
    parado = entrada.get("parado_ha_dias")
    if parado is not None and (not isinstance(parado, int) or parado < 0):
        raise ErroFerramenta("parado_ha_dias deve ser um número inteiro de dias.")

    # A própria consulta da tela de Estoque (mesmos filtros e os mesmos campos por perfil).
    veiculos = [
        schemas.VeiculoOut(**v)
        for v in rotas_veiculos.listar(
            situacao=situacao,
            tipo=_tipo(entrada),
            busca=busca or None,
            grupo=_GRUPOS[grupo],
            usuario=usuario,
            db=db,
        )
    ]
    if parado:
        veiculos = [v for v in veiculos if v.dias_na_situacao >= parado]
        veiculos.sort(key=lambda v: -v.dias_na_situacao)
    ve_custos = pode(usuario, P.custos_ver)

    contagem: dict[str, int] = {}
    for v in veiculos:
        contagem[SITUACAO[v.situacao]] = contagem.get(SITUACAO[v.situacao], 0) + 1
    a_venda = [v for v in veiculos if v.situacao == Situacao.a_venda and v.preco_venda]
    lista = [
        _limpo(
            {
                "veiculo": v.descricao,
                "tipo": v.tipo.value,
                "cor": v.cor,
                "km": v.km,
                "situacao": SITUACAO[v.situacao],
                "dias_na_situacao": v.dias_na_situacao,
                "preco_venda": reais(v.preco_venda),
                "custo_total": reais(v.custo_total) if ve_custos else None,
                "lucro_previsto": reais(v.lucro_previsto) if ve_custos else None,
            }
        )
        for v in veiculos[:MAX_LISTA]
    ]
    return _limpo(
        {
            "grupo": grupo,
            "quantidade": len(veiculos),
            "por_situacao": contagem,
            "por_tipo": {
                t.value: n for t in TipoVeiculo if (n := sum(v.tipo == t for v in veiculos))
            },
            "valor_anunciado_a_venda": reais(sum((v.preco_venda for v in a_venda), ZERO))
            if a_venda
            else None,
            "investido_compra_mais_custos": reais(
                sum((v.custo_total or ZERO for v in veiculos), ZERO)
            )
            if ve_custos and veiculos
            else None,
            "observacao": None if ve_custos else "este perfil não vê valor de compra nem custos",
            "alerta_parado_dias": obter_config().dias_parado_alerta,
            "lista": lista,
            "lista_incompleta": len(veiculos) > MAX_LISTA or None,
        }
    )


def consultar_comissoes(db: Session, usuario: Usuario, entrada: dict) -> dict:
    mes = _mes(entrada)
    ve_todas = pode(usuario, P.comissoes_ver_todas)
    vendedor_id: int | None = None
    if not ve_todas:  # como na tela: o vendedor vê só as próprias
        vendedor_id = usuario.id
    elif entrada.get("vendedor"):
        vendedor_id = _vendedor_por_nome(db, str(entrada["vendedor"])).id
    relatorio = rotas_comissoes.relatorio(db, mes, vendedor_id)
    return _limpo(
        {
            "mes": _mes_br(mes),
            "escopo": "todos os vendedores" if ve_todas else "só as comissões de quem pergunta",
            "total": reais(relatorio.total),
            "pendente": reais(relatorio.pendente),
            "pago": reais(relatorio.total - relatorio.pendente),
            "por_vendedor": [
                {
                    "vendedor": g.vendedor.nome,
                    "vendas": g.vendas,
                    "total": reais(g.total),
                    "pago": reais(g.pago),
                    "pendente": reais(g.pendente),
                }
                for g in relatorio.por_vendedor
            ],
            "lista": [
                {
                    "data_venda": data_br(c.data_venda),
                    "veiculo": c.veiculo,
                    "valor_venda": reais(c.valor_venda),
                    "comissao": reais(c.valor),
                    "situacao": STATUS_COMISSAO.get(c.status, c.status.value),
                    "vendedor": c.vendedor.nome,
                }
                for c in relatorio.itens[:MAX_LISTA]
            ],
            "lista_incompleta": len(relatorio.itens) > MAX_LISTA or None,
        }
    )


def consultar_painel(db: Session, usuario: Usuario, entrada: dict) -> dict:
    if not pode(usuario, P.painel_ver):
        raise ErroFerramenta("Este perfil não tem acesso ao painel.")
    painel = rotas_painel.painel(meses=6, _=usuario, db=db)  # os números da tela /painel
    ve_custos = pode(usuario, P.custos_ver)

    def numeros(n: schemas.NumerosPeriodo) -> dict:
        dados: dict[str, Any] = {
            "vendas": n.vendas,
            "faturamento": reais(n.faturamento),
            "ticket_medio": reais(n.ticket_medio),
        }
        if ve_custos:
            dados.update(
                lucro=reais(n.lucro),
                imposto_estimado=reais(n.imposto),
                lucro_liquido=reais(n.lucro_liquido),
            )
        return _limpo(dados)

    estoque = painel.estoque
    return _limpo(
        {
            "hoje": data_br(painel.hoje),
            "mes_atual": {
                "mes": _mes_br(painel.mes_atual.mes),
                "total": numeros(painel.mes_atual.total),
                "moto": numeros(painel.mes_atual.moto),
                "carro": numeros(painel.mes_atual.carro),
            },
            "ultimos_6_meses": [{"mes": _mes_br(m.mes), **numeros(m.total)} for m in painel.meses],
            "estoque": _limpo(
                {
                    "em_estoque": estoque.em_estoque,
                    "por_situacao": {
                        SITUACAO[Situacao(s)]: n for s, n in estoque.por_situacao.items() if n
                    },
                    "capital_investido": reais(estoque.capital_investido) if ve_custos else None,
                    "valor_anunciado_a_venda": reais(estoque.potencial_venda),
                }
            ),
            "parados": {
                "alerta_dias": painel.dias_parado_alerta,
                "quantidade": len(painel.parados),
                "quantidade_e_no_minimo": len(painel.parados) >= 20 or None,
                "mais_antigos": [
                    {"veiculo": p.descricao, "situacao": SITUACAO[p.situacao], "dias": p.dias}
                    for p in painel.parados[:5]
                ],
            },
            "comissoes_do_mes": [
                {"vendedor": g.vendedor.nome, "vendas": g.vendas, "total": reais(g.total)}
                for g in painel.comissoes_mes
            ],
        }
    )


def consultar_aportes(db: Session, usuario: Usuario, entrada: dict) -> dict:
    if not pode(usuario, P.aportes_ver):
        raise ErroFerramenta("Este perfil não tem acesso a essa informação.")
    tudo = rotas_aportes.listar(_=usuario, db=db)  # a mesma consulta da tela de Aportes
    itens = tudo.itens
    periodo = None
    if entrada.get("inicio") or entrada.get("fim"):
        inicio = _data(entrada.get("inicio") or "2000-01-01", "inicio")
        fim = _data(entrada.get("fim") or hoje().isoformat(), "fim")
        if fim < inicio:
            raise ErroFerramenta("fim é anterior ao início.")
        itens = [a for a in itens if inicio <= a.data <= fim]
        periodo = f"{data_br(inicio)} a {data_br(fim)}"
    return _limpo(
        {
            "periodo": periodo or "desde o primeiro registro",
            "quantidade": len(itens),
            "total": reais(sum((a.valor for a in itens), ZERO)),
            "total_geral_de_todos_os_aportes": reais(tudo.total),
            "lista": [
                {"data": data_br(a.data), "valor": reais(a.valor), "descricao": a.descricao}
                for a in itens[:MAX_LISTA]
            ],
            "lista_incompleta": len(itens) > MAX_LISTA or None,
        }
    )


# ---------------------------------------------------------------------------------------
# Definições para o modelo
# ---------------------------------------------------------------------------------------

_DATA = {"type": "string", "description": "AAAA-MM-DD"}
_TIPO = {"type": "string", "enum": ["moto", "carro"]}


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    parametros: dict
    obrigatorios: tuple[str, ...]
    executar: Callable[[Session, Usuario, dict], dict]
    permissao: P | None = None  # None: todo perfil usa, com o recorte da tela

    def esquema(self) -> dict:
        """JSON Schema dos parâmetros; cada provedor embrulha no próprio formato."""
        return {
            "type": "object",
            "properties": self.parametros,
            "required": list(self.obrigatorios),
            "additionalProperties": False,
        }


FERRAMENTAS: tuple[Ferramenta, ...] = (
    Ferramenta(
        "consultar_vendas",
        "Vendas registradas (sem as canceladas) entre duas datas, inclusive: quantidade, "
        "faturamento, ticket médio, divisão por tipo (moto/carro), forma de pagamento e "
        "vendedor, e a lista das vendas mais recentes. Lucro e imposto só vêm se o perfil vê "
        "custos. Para quem não vê todas as vendas, considera só as vendas da própria pessoa.",
        {
            "inicio": _DATA,
            "fim": _DATA,
            "tipo": _TIPO,
            "vendedor": {"type": "string", "description": "nome ou parte do nome do vendedor"},
        },
        ("inicio", "fim"),
        consultar_vendas,
    ),
    Ferramenta(
        "consultar_estoque",
        "Veículos do estoque (ou vendidos) com filtros: quantidade por situação e tipo, valor "
        "anunciado, valor investido (só se o perfil vê custos) e a lista dos veículos, com "
        "preço, km, cor, situação e dias parado na situação. Também serve para achar um veículo "
        "por marca, modelo, placa ou cor.",
        {
            "grupo": {
                "type": "string",
                "enum": ["estoque", "vendidos", "todos"],
                "description": "estoque (padrão): ainda não vendidos",
            },
            "situacao": {"type": "string", "enum": [s.value for s in Situacao]},
            "tipo": _TIPO,
            "busca": {"type": "string", "description": "marca, modelo, placa ou cor"},
            "parado_ha_dias": {
                "type": "integer",
                "description": "só os que estão na mesma situação há pelo menos N dias",
            },
        },
        (),
        consultar_estoque,
        P.estoque_ver,
    ),
    Ferramenta(
        "consultar_comissoes",
        "Comissões de um mês (pela data da venda): total, pago, pendente, por vendedor e a "
        "lista. Quem não vê todas as comissões recebe só as próprias.",
        {
            "mes": {"type": "string", "description": "AAAA-MM; padrão: mês atual"},
            "vendedor": {"type": "string", "description": "nome ou parte do nome do vendedor"},
        },
        (),
        consultar_comissoes,
    ),
    Ferramenta(
        "consultar_painel",
        "Os números da tela Painel: mês atual (vendas, faturamento, ticket médio, lucro, "
        "imposto estimado e lucro líquido, total e por moto/carro), os últimos 6 meses, "
        "resumo do estoque (capital investido, valor anunciado), veículos parados há muito "
        "tempo e comissões do mês.",
        {},
        (),
        consultar_painel,
        P.painel_ver,
    ),
    Ferramenta(
        "consultar_aportes",
        "Aportes: gastos pessoais do dono investidos na loja. Total e lista, de um período "
        "ou de todos.",
        {"inicio": _DATA, "fim": _DATA},
        (),
        consultar_aportes,
        P.aportes_ver,
    ),
)
_POR_NOME = {f.nome: f for f in FERRAMENTAS}


def disponiveis(usuario: Usuario) -> list[Ferramenta]:
    """As ferramentas que o perfil pode usar (as outras nem são mostradas ao modelo)."""
    return [f for f in FERRAMENTAS if f.permissao is None or pode(usuario, f.permissao)]


def executar(db: Session, usuario: Usuario, nome: str, entrada: Any) -> tuple[str, bool]:
    """Roda uma ferramenta. Devolve (conteúdo JSON, é_erro). Nunca levanta exceção."""
    ferramenta = _POR_NOME.get(nome)
    try:
        if ferramenta is None or ferramenta not in disponiveis(usuario):
            raise ErroFerramenta("Ferramenta indisponível para este perfil.")
        if not isinstance(entrada, dict):
            raise ErroFerramenta("Parâmetros inválidos.")
        resultado = ferramenta.executar(db, usuario, entrada)
        return json.dumps(resultado, ensure_ascii=False, separators=(",", ":")), False
    except ErroFerramenta as erro:
        return json.dumps({"erro": str(erro)}, ensure_ascii=False), True
    except HTTPException as erro:  # validação das funções das rotas (ex.: mês inválido)
        db.rollback()
        return json.dumps({"erro": str(erro.detail)}, ensure_ascii=False), True
