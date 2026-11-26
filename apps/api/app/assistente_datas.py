"""Datas escritas do jeito falado: "hoje", "ontem", "dia 20", "15/11", "15/11/2026",
"20 de outubro". Função pura, sem banco: quem chama informa o dia de hoje.

O assistente usa para a data da compra (cadastro), a data da venda e o primeiro vencimento
do parcelado. Regra da casa: na dúvida, pergunta. "Dia 28" dito no dia 26 tanto pode ser
uma data futura (inválida para compra) quanto o dia 28 do mês passado: vira pergunta. No
vencimento, que só pode ser futuro, "dia 5" é o próximo dia 5.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

_MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
_MES = "|".join(_MESES)

# Expressão de data, no texto já normalizado (minúsculas, sem acento).
EXPRESSAO = (
    r"(?:hoje|hj|ontem|anteontem|antes de ontem"
    rf"|(?:(?:no )?dia )?\d{{1,2}}/\d{{1,2}}(?:/\d{{2}}(?:\d{{2}})?)?(?!\d)"
    rf"|(?:(?:no )?dia )?\d{{1,2}} de (?:{_MES})(?: de \d{{4}})?"
    r"|(?:no )?dia \d{1,2}(?![\d/]))"
)
_EXPRESSAO = re.compile(rf"\b{EXPRESSAO}")


@dataclass(frozen=True)
class DataLida:
    """Resultado da leitura: a data, ou um erro, ou uma pergunta (data ambígua)."""

    data: date | None = None
    erro: str | None = None
    pergunta: str | None = None
    sugestao: date | None = None  # a leitura mais provável, quando é pergunta


def formatar(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def _montar(ano: int, mes: int, dia: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _mes_vizinho(ano: int, mes: int, passo: int) -> tuple[int, int]:
    total = ano * 12 + (mes - 1) + passo
    return total // 12, total % 12 + 1


def procurar(texto: str, inicio: int = 0) -> re.Match | None:
    """Primeira expressão de data no texto normalizado a partir de `inicio`."""
    return _EXPRESSAO.search(texto, inicio)


def ler(
    trecho: str, hoje: date, *, sentido: str = "passado", o_que: str = "da compra"
) -> DataLida | None:
    """Lê uma expressão de data (texto normalizado). None = não é uma data.

    `sentido`: "passado" (compra, venda: não pode ser futura) ou "futuro" (vencimento).
    """
    t = " ".join(trecho.split())
    t = re.sub(r"^(?:no )?dia ", "", t)
    if t in ("hoje", "hj"):
        return DataLida(hoje)
    if t == "ontem":
        return DataLida(hoje - timedelta(days=1))
    if t in ("anteontem", "antes de ontem"):
        return DataLida(hoje - timedelta(days=2))

    ano: int | None = None
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?", t):
        dia, mes = int(m[1]), int(m[2])
        if m[3]:
            ano = int(m[3]) if len(m[3]) == 4 else 2000 + int(m[3])
    elif m := re.fullmatch(rf"(\d{{1,2}}) de ({_MES})(?: de (\d{{4}}))?", t):
        dia, mes = int(m[1]), _MESES[m[2]]
        ano = int(m[3]) if m[3] else None
    elif m := re.fullmatch(r"(\d{1,2})", t):
        dia, mes = int(m[1]), None
    else:
        return None

    if mes is not None and not 1 <= mes <= 12:
        return DataLida(erro=f"Não entendi a data “{trecho.strip()}”: o mês vai de 1 a 12.")

    if ano is not None:  # data completa: não há o que adivinhar
        lida = _montar(ano, mes, dia)
        if lida is None:
            return DataLida(erro=f"A data “{trecho.strip()}” não existe no calendário.")
        return _conferir(lida, hoje, sentido, o_que)

    if mes is None:  # "dia 20": este mês, ou o vizinho se cair do lado errado de hoje
        lida = _montar(hoje.year, hoje.month, dia)
        if lida is None and not 1 <= dia <= 31:
            return DataLida(erro=f"Não entendi “dia {dia}”: o dia vai de 1 a 31.")
        errado = lida is None or (lida > hoje if sentido == "passado" else lida < hoje)
        if not errado:
            return DataLida(lida)
        ano_v, mes_v = _mes_vizinho(hoje.year, hoje.month, -1 if sentido == "passado" else 1)
        if sentido == "futuro" and _montar(ano_v, mes_v, dia):
            return DataLida(_montar(ano_v, mes_v, dia))  # vencimento "dia 5": o próximo dia 5
        return _perguntar(_montar(ano_v, mes_v, dia), f"dia {dia}", o_que)

    # "15/11": este ano, ou o vizinho se cair do lado errado de hoje
    lida = _montar(hoje.year, mes, dia)
    if lida is None:
        if dia == 29 and mes == 2:  # 29/02 só existe em ano bissexto
            vizinho = hoje.year - 1 if sentido == "passado" else hoje.year + 1
            return _perguntar(_montar(vizinho, mes, dia), t, o_que)
        return DataLida(erro=f"A data “{trecho.strip()}” não existe no calendário.")
    if (lida > hoje) if sentido == "passado" else (lida < hoje):
        vizinho = hoje.year - 1 if sentido == "passado" else hoje.year + 1
        if sentido == "futuro":  # vencimento "10/01": o próximo 10 de janeiro
            return DataLida(_montar(vizinho, mes, dia))
        return _perguntar(_montar(vizinho, mes, dia), t, o_que)
    return DataLida(lida)


def _conferir(lida: date, hoje: date, sentido: str, o_que: str) -> DataLida:
    if sentido == "passado" and lida > hoje:
        return DataLida(erro=f"A data {o_que} não pode ser futura ({formatar(lida)}).")
    if sentido == "passado" and lida.year < 1950:
        return DataLida(erro=f"A data {o_que} ({formatar(lida)}) está antiga demais.")
    if sentido == "futuro" and lida.year > hoje.year + 10:
        return DataLida(erro=f"A data {o_que} ({formatar(lida)}) está longe demais.")
    return DataLida(lida)


def _perguntar(sugestao: date | None, trecho: str, o_que: str) -> DataLida:
    if sugestao is None:
        return DataLida(erro=f"Não entendi a data {o_que}: mande a data completa, como 15/11/2026.")
    return DataLida(
        pergunta=(
            f"Fiquei na dúvida sobre a data {o_que} (“{trecho}”). Mande a data completa, "
            f"por exemplo: {formatar(sugestao)}."
        ),
        sugestao=sugestao,
    )
