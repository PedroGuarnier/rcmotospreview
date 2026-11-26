"""Leitura das mensagens de venda e de alteração de veículo (função pura, sem banco).

Complementa `app.assistente.interpretar`: lá fica o vocabulário e a leitura do cadastro; aqui,
o que muda quando a frase fala de um veículo que já está no estoque.

- Venda: "vendi a CG 160 placa ABC1D23 pro João Silva por 14.900 à vista, vendedor Carlos".
  Sai a referência ao veículo (`Interpretacao.referencia`) e os dados da baixa
  (`Interpretacao.venda_dados`): comprador, valor, forma, parcelas, vendedor, data.
- Alteração: "a CG placa ABC1D23 agora custa 13.900", "põe a Biz 125 branca à venda",
  "muda a cor da Factor para azul". A frase é cortada no ponto em que começa o valor novo
  ("agora", "para", "tá com"): antes dele está o veículo; depois, o que muda.

Como no cadastro, nada é chutado: número sem pista vira pergunta.
"""

import re
from typing import Any

from app import assistente_datas, validacao
from app.assistente import (
    _AJUDA,
    _CONTATOS,
    _CORES,
    _DATA_DE_MES_INVALIDO,
    _DISPENSA,
    _FAMILIAS,
    _MARCAS,
    _MODELOS,
    _OBRIGADO,
    _SAUDACAO,
    _UNIDADES_KM,
    _VENDA_PEDIDO,
    CENTAVO,
    Interpretacao,
    _Leitor,
    _moeda,
    _normalizar,
    _numero_curto,
)
from app.models import FormaPagamento, Situacao

# ---------------------------------------------------------------------------------------
# Nomes de pessoas (comprador, vendedor, banco)
# ---------------------------------------------------------------------------------------

_CONECTORES_NOME = {"da", "de", "do", "das", "dos", "e"}
_NAO_E_NOME = set(
    "por a o as os no na nos nas com sem em ao aos vendedor vendedora hoje hj ontem anteontem "
    "dia valor reais real pelo pela pelos pelas parcelado parcelada financiado financiada "
    "financiamento avista vista pix dinheiro cartao boleto carne entrada vezes parcelas parcela "
    "x cliente comprador compradora banco loja moto carro placa final que foi ja mas so ele ela "
    "eu mim voce vc la ai aqui mesmo mesma preco anunciado tabela quem comprou vendeu vendi "
    "vender venda vendida vendido cor ano km um uma mil todo toda semana mes cada primeira "
    "primeiro vencimento vence telefone fone tel whats whatsapp zap cel celular contato cpf "
    "cnpj obs isso ok sim nao n pra pro para seu sua dele dela nosso nossa minha meu "
    "janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro "
    "segunda terca quarta quinta sexta sabado domingo especie vez prestacao prestacoes "
    "registra registrar dar baixa lanca lancar agora ainda tambem ate apos depois antes "
    "cheio fipe tudo nada pagou pago paga deu dei vai vou".split()
)
_PALAVRA = re.compile(r"[ \t]*([a-z][a-z']*)(?![a-z0-9])")


def _pode_ser_nome(palavra: str) -> bool:
    return (
        len(palavra) >= 2
        and palavra not in _NAO_E_NOME
        and palavra not in _CORES
        and (palavra,) not in _MODELOS
        and (palavra,) not in _MARCAS
        and palavra not in _FAMILIAS
    )


def _nome_em(leitor: _Leitor, pos: int, maximo: int = 5) -> tuple[str, int, int] | None:
    """Nome de pessoa a partir de `pos` no texto normalizado: (nome, início, fim)."""
    texto = leitor.texto()
    palavras: list[tuple[int, int, bool]] = []
    k = pos
    while len([p for p in palavras if not p[2]]) < maximo:
        m = _PALAVRA.match(texto, k)
        if not m:
            break
        palavra = m[1]
        if palavra in _CONECTORES_NOME:
            seguinte = _PALAVRA.match(texto, m.end())
            if not palavras or not seguinte or not _pode_ser_nome(seguinte[1]):
                break
            palavras.append((m.start(1), m.end(1), True))
        elif _pode_ser_nome(palavra):
            palavras.append((m.start(1), m.end(1), False))
        else:
            break
        k = m.end()
    while palavras and palavras[-1][2]:
        palavras.pop()
    if not palavras:
        return None
    ini, fim = palavras[0][0], palavras[-1][1]
    return _capitalizar(leitor.original[ini:fim]), ini, fim


def _capitalizar(nome: str) -> str:
    """ "joão da silva" vira "João da Silva"; o que veio com maiúscula fica como foi escrito."""
    nome = " ".join(nome.split())
    if nome != nome.lower():
        return nome
    return " ".join(p if p in _CONECTORES_NOME else p.capitalize() for p in nome.split())


def _nome_de_banco(trecho: str) -> str:
    """ "bv" vira "BV", "banco do brasil" vira "Banco do Brasil"."""
    trecho = " ".join(trecho.split())
    if trecho != trecho.lower():
        return trecho
    partes = []
    for p in trecho.split():
        if p in _CONECTORES_NOME:
            partes.append(p)
        elif len(p) <= 3 or any(c.isdigit() for c in p):
            partes.append(p.upper())
        else:
            partes.append(p.capitalize())
    return " ".join(partes)


# ---------------------------------------------------------------------------------------
# Venda
# ---------------------------------------------------------------------------------------

_VENDEDOR = re.compile(
    r"\b(?:vendedora?|vendid[oa] pel[oa]|quem vendeu(?: foi)?|"
    r"comissao (?:d[oa]|pr[oa]|para(?: [oa])?))\b\s*[:=\-]?\s*(?:(?:foi|o|a|e|eh)\s+)*"
)
_VENDEDOR_SUJEITO = re.compile(r"^(?:(?:o|a)\s+)?(?=[a-z])(?!eu\b)")
_EU_VENDI = re.compile(
    r"\b(?:vendedora?\s*[:=\-]?\s*(?:fui |sou |e |eh )?eu(?: mesm[oa])?|"
    r"eu (?:mesm[oa] )?(?:que )?vendi|fui eu(?: que vendi)?)\b"
)
_COMPRADOR = re.compile(
    r"\b(?:pr[oa]|para|ao|compradora?|cliente|quem comprou(?: foi)?)\b\s*[:=\-]?\s*"
    r"(?:(?:o|a|seu|sr|sra|dona|senhor|senhora|cliente|comprador|compradora)\s+)*"
)
_A_VISTA = re.compile(
    r"\b(?:a vista|avista|no pix|via pix|pelo pix|pix|em dinheiro|dinheiro vivo|em especie)\b"
)
_FINANCIADO = re.compile(
    r"\b(?:financiad[oa]|financiamento|financiou|financiei|financiaram|pelo banco|no banco|"
    r"financeira|cdc)\b"
)
_PARCELADO = re.compile(
    r"\b(?:parcelad[oa]|parcelamento|parcelei|parcelou|carnes?|crediario|promissorias?|"
    r"\d{1,3} ?x(?!\d)|\d{1,3} vezes|\d{1,3} parcelas|\d{1,3} prestacoes)\b"
)
_BANCO = re.compile(
    r"\b(?:financiad[oa]|financiamento|financiou|financiei|financiaram)\b"
    r"(?:\s+(?:pel[oa]|n[oa]|com(?: [oa])?|via|junto (?:ao|a)))+\s+"
)
_BANCO_NOME = re.compile(r"(banco(?: d[oa])? [a-z0-9]+|[a-z][a-z0-9]{1,14})\b")
_VENCIMENTO = re.compile(
    r"\b(?:primeir[oa] (?:parcela|vencimento|prestacao|pagamento)|1[ao]? (?:parcela|vencimento)|"
    r"vencimento|vence|vencendo|vencem|comecando|comeca|a partir d[eo])\b"
    r"(?:\s+(?:em|no|na|dia|para|pra|de|todo|o|a|pagar|paga|pagando))*\s+"
    rf"(?P<data>{assistente_datas.EXPRESSAO})"
)
_ANUNCIADO = re.compile(
    r"\b(?:(?:pelo|no|o) (?:mesmo )?(?:preco |valor )?(?:anunciado|da tabela|de tabela|do anuncio)|"
    r"preco cheio|valor cheio)\b"
)
_TELEFONE_ROTULO = re.compile(
    r"\b(?:telefone|fone|tel|whats|whatsapp|zap|celular|cel|contato)\s*(?:d[oa]\s+\w+\s*)?"
    r"[:=\-]?\s*(\(?\d[\d\s().\-]{7,16}\d)"
)
_DOCUMENTO_ROTULO = re.compile(r"\b(?:cpf|cnpj)\s*[:=\-]?\s*(\d[\d.\-/]{9,18}\d)")
_PARCELA_UNIDADE = {"x", "vezes", "parcelas", "parcela", "prestacoes", "prestacao"}
_ANTES_DO_VALOR = {"de", "da", "do", "no", "na", "o", "a", "um", "uma", ":", "=", "-", "foi", "e"}


def _apagar_tudo(leitor: _Leitor, padrao: re.Pattern) -> list[re.Match]:
    achados = list(padrao.finditer(leitor.texto()))
    for m in achados:
        leitor.apagar(m.start(), m.end())
    return achados


def ler_venda(leitor: _Leitor, limpo: str, *, sim: bool, nao: bool) -> Interpretacao:
    """Mensagem que registra uma venda (ou responde a uma pergunta sobre ela)."""
    r = leitor.r
    r.venda = True
    dados = r.venda_dados
    aguardando = leitor.aguardando

    _ler_pessoas(leitor, dados)
    _ler_contatos(leitor, dados)
    _ler_forma(leitor, dados)
    _ler_datas(leitor, dados)
    if _apagar_tudo(leitor, _ANUNCIADO):
        dados["valor_anunciado"] = True
    _apagar_tudo(leitor, _VENDA_PEDIDO)

    if aguardando == "vendedor" and re.fullmatch(
        r"(?:(?:fui|sou|foi)\s+)?eu(?:\s+mesm[oa])?(?:\s+que\s+vendi)?", limpo
    ):
        dados["vendedor_eu"] = True
        leitor.apagar(0, len(leitor.buf))
    # resposta curta à pergunta feita: "João Silva" para o comprador, "Carlos" para o vendedor
    if aguardando in ("comprador", "vendedor") and not (
        "comprador" in dados or "vendedor_nome" in dados or "vendedor_eu" in dados
    ):
        inicio = re.match(r"\s*(?:(?:o|a|e|eh|foi|e o|e a)\s+)*", leitor.texto())
        nome = _nome_em(leitor, inicio.end() if inicio else 0)
        if nome and not leitor.texto()[nome[2] :].strip(" .,!;§"):
            dados["comprador" if aguardando == "comprador" else "vendedor_nome"] = nome[0]
            leitor.apagar(nome[1], nome[2])

    r.referencia = leitor.referencia()
    if leitor.contexto == "venda" and aguardando != "veiculo":
        r.referencia.pop("texto", None)  # palavra solta no meio da conversa não é o veículo
    _ler_valores(leitor, dados)

    tem_dados = bool(dados or r.referencia or r.erros or r.soltos or r.perguntas)
    if leitor.contexto != "venda" or tem_dados:
        r.intencao = "venda"
    elif limpo in _DISPENSA:
        r.intencao = "dispensa"
    elif sim:
        r.intencao = "afirmacao"
    elif nao:
        r.intencao = "negacao"
    elif _SAUDACAO.fullmatch(limpo) or _AJUDA.search(limpo):
        r.intencao = "ajuda"
    elif _OBRIGADO.fullmatch(limpo):
        r.intencao = "agradecimento"
    else:
        r.intencao = "nada"
    return r


def _ler_pessoas(leitor: _Leitor, dados: dict[str, Any]) -> None:
    for m in _EU_VENDI.finditer(leitor.texto()):
        dados["vendedor_eu"] = True
        leitor.apagar(m.start(), m.end())
        break
    for m in _VENDEDOR.finditer(leitor.texto()):
        nome = _nome_em(leitor, m.end(), maximo=3)
        if nome:
            dados["vendedor_nome"] = nome[0]
            leitor.apagar(m.start(), nome[2])
            break
    if "vendedor_nome" not in dados and "vendedor_eu" not in dados:
        # "o Carlos vendeu a biz", "Carlos que vendeu a CG"
        sujeito = _VENDEDOR_SUJEITO.match(leitor.texto())
        if sujeito:
            nome = _nome_em(leitor, sujeito.end(), maximo=3)
            if nome and re.match(r"\s+(?:que\s+)?vendeu\b", leitor.texto()[nome[2] :]):
                dados["vendedor_nome"] = nome[0]
                leitor.apagar(sujeito.start(), nome[2])
    for m in _COMPRADOR.finditer(leitor.texto()):
        nome = _nome_em(leitor, m.end())
        if nome:
            dados["comprador"] = nome[0]
            leitor.apagar(m.start(), nome[2])
            break


def _ler_contatos(leitor: _Leitor, dados: dict[str, Any]) -> None:
    r = leitor.r
    m = _DOCUMENTO_ROTULO.search(leitor.texto())
    achado = m[1] if m else None
    if achado is None:
        for padrao in _CONTATOS[:2]:  # CNPJ e CPF formatados
            m = padrao.search(leitor.texto())
            if m:
                achado = m[0]
                break
    if m and achado:
        try:
            dados["cpf_cnpj"] = validacao.normalizar_cpf_cnpj(achado)
        except ValueError as erro:
            r.erros.append(str(erro))
        leitor.apagar(m.start(), m.end())
    m = _TELEFONE_ROTULO.search(leitor.texto())
    achado = m[1] if m else None
    if achado is None:
        for padrao in _CONTATOS[3:]:  # telefones
            m = padrao.search(leitor.texto())
            if m:
                achado = m[0]
                break
    if m and achado:
        try:
            dados["telefone"] = validacao.normalizar_telefone(achado)
        except ValueError as erro:
            r.erros.append(str(erro))
        leitor.apagar(m.start(), m.end())


def _ler_forma(leitor: _Leitor, dados: dict[str, Any]) -> None:
    texto = leitor.texto()
    financiado = _FINANCIADO.search(texto)
    parcelado = _PARCELADO.search(texto)
    if financiado:
        dados["forma"] = FormaPagamento.financiado_banco
        banco = _BANCO.search(texto)
        if banco:
            nome = _BANCO_NOME.match(texto, banco.end())
            if nome and nome[1].split()[0] not in _NAO_E_NOME:
                ini, fim = nome.start(1), nome.end(1)
                dados["banco"] = _nome_de_banco(leitor.original[ini:fim])
                leitor.apagar(banco.start(), fim)
        else:
            m = re.search(r"\bbanco (?:d[oa] )?[a-z][a-z0-9]+\b", texto)
            if m and m[0].split()[-1] not in _NAO_E_NOME:
                dados["banco"] = _nome_de_banco(leitor.original[m.start() : m.end()])
                leitor.apagar(m.start(), m.end())
    elif parcelado:
        dados["forma"] = FormaPagamento.parcelado_loja
    elif _A_VISTA.search(texto):
        dados["forma"] = FormaPagamento.a_vista
    for padrao in (_FINANCIADO, _A_VISTA, _PARCELADO):
        for m in list(padrao.finditer(leitor.texto())):
            if not any(c.isdigit() for c in m[0]):  # "10x" fica para as parcelas
                leitor.apagar(m.start(), m.end())


def _ler_datas(leitor: _Leitor, dados: dict[str, Any]) -> None:
    r = leitor.r
    m = _VENCIMENTO.search(leitor.texto())
    if m:
        lida = assistente_datas.ler(
            m["data"], leitor.dia, sentido="futuro", o_que="do primeiro vencimento"
        )
        if lida is not None:
            leitor.apagar(m.start(), m.end())
            _guardar_data(r, dados, "primeiro_vencimento", lida)
    elif leitor.aguardando == "primeiro_vencimento":
        m = assistente_datas.procurar(leitor.texto())
        if m and not _DATA_DE_MES_INVALIDO.fullmatch(m[0]):
            lida = assistente_datas.ler(
                m[0], leitor.dia, sentido="futuro", o_que="do primeiro vencimento"
            )
            if lida is not None:
                leitor.apagar(m.start(), m.end())
                _guardar_data(r, dados, "primeiro_vencimento", lida)
                return
    inicio = 0
    while m := assistente_datas.procurar(leitor.texto(), inicio):
        inicio = m.end()
        if _DATA_DE_MES_INVALIDO.fullmatch(m[0]):
            continue  # "biz 21/22": é o ano
        lida = assistente_datas.ler(m[0], leitor.dia, o_que="da venda")
        if lida is None:
            continue
        leitor.apagar(m.start(), m.end())
        _guardar_data(r, dados, "data_venda", lida)
        break


def _guardar_data(r: Interpretacao, dados: dict, campo: str, lida) -> None:
    if lida.data is not None:
        dados[campo] = lida.data
    elif lida.pergunta:
        r.perguntas.append((campo, lida.pergunta, lida.sugestao))
    elif lida.erro:
        r.erros.append(lida.erro)


def _ler_valores(leitor: _Leitor, dados: dict[str, Any]) -> None:
    """Dinheiro da venda: valor, entrada, número e valor das parcelas."""
    r, toks, t = leitor.r, leitor.toks, leitor.t
    aguardando = leitor.aguardando
    livres = [q for q in leitor.qtds if leitor._livre(q)]
    usados: set[int] = set()

    def anterior(q) -> tuple[str, bool]:
        """Palavra antes do número, pulando ligações; e se passou por "valor"/"total"."""
        k, rotulo = q.i - 1, False
        while k >= 0 and (t(k) in _ANTES_DO_VALOR or t(k) in ("valor", "total", "r$", "rs")):
            rotulo = rotulo or t(k) in ("valor", "total")
            k -= 1
        return t(k), rotulo

    def ano(q) -> bool:
        return q.simples and len(toks[q.i].t) == 4 and leitor.ano_plausivel(int(q.valor))

    # parcelas: "10x de 1.200", "em 12 vezes de 1.250", "10 parcelas de 990"
    for posicao, q in enumerate(livres):
        unidade = t(q.j) in _PARCELA_UNIDADE
        if not (unidade or aguardando == "numero_parcelas") or not q.simples:
            continue
        if not 1 <= q.valor <= 120:
            continue
        dados["numero_parcelas"] = int(q.valor)
        usados.add(posicao)
        k = q.j + 1 if unidade else q.j
        while t(k) in ("de", "no", "valor", "com", ":", "=", "r$", "rs", "cada"):
            k += 1
        for outra, q2 in enumerate(livres):
            if outra not in usados and q2.i in (k, k - 1) and q2.i >= q.j:
                dados["valor_parcela"] = q2.valor.quantize(CENTAVO)
                usados.add(outra)
                break
        break

    # entrada: "entrada de 3 mil", "3 mil de entrada", "com 3 mil na entrada"
    for posicao, q in enumerate(livres):
        if posicao in usados:
            continue
        if t(q.j) in _UNIDADES_KM:  # "com 15 mil km": não é dinheiro da venda
            usados.add(posicao)
            continue
        depois = (t(q.j), t(q.j + 1))
        if (
            anterior(q)[0] == "entrada"
            or depois[0] == "entrada"
            or depois
            in (
                ("de", "entrada"),
                ("na", "entrada"),
            )
        ):
            dados["entrada"] = q.valor.quantize(CENTAVO)
            usados.add(posicao)

    # valor da venda (ou a resposta à pergunta feita)
    alvo = aguardando if aguardando in ("valor_parcela", "entrada") else "valor"
    candidatos: list[tuple] = []
    for posicao, q in enumerate(livres):
        if posicao in usados:
            continue
        antes, rotulo = anterior(q)
        if q.cifrao or antes == "por" or rotulo:
            candidatos.insert(0, (q, True))
        elif (q.dinheiro or q.valor >= 1000 or alvo != "valor") and not ano(q):
            candidatos.append((q, False))
    if not candidatos or (alvo == "valor" and "valor" in dados):
        return
    fortes = [q for q, forte in candidatos if forte]
    if len(fortes) == 1 or len(candidatos) == 1:
        q = fortes[0] if fortes else candidatos[0][0]
        if alvo == "valor" and (0 < q.valor < 100 or (q.valor < 1000 and not q.cifrao)):
            curto = _numero_curto(q.valor)
            r.erros.append(
                f"Entendi {_moeda(q.valor)} como valor da venda, o que é pouco para um veículo. "
                f"Se for {curto} mil, escreva “{curto} mil” ou o valor completo."
            )
        elif q.valor > 0:
            dados[alvo] = q.valor.quantize(CENTAVO)
        resto = [c for c, _ in candidatos if c is not q]
    else:
        resto = [c for c, _ in candidatos]
    for q in resto:
        if q.dinheiro or q.valor >= 1000:
            r.soltos.append((q.valor, q.cifrao))


# ---------------------------------------------------------------------------------------
# Alteração de veículo do estoque
# ---------------------------------------------------------------------------------------

# Onde começa o valor novo: "a biz agora custa", "muda a cor da factor para azul".
_MARCADOR = re.compile(
    r"\b(?:agora|para|pra|ta com|esta com|ficou com|fica com|custa|custando|vale|sai por|"
    r"saindo por)\b"
)
# "põe a biz à venda", "coloca a XRE em preparação"
_SITUACAO_NOVA = re.compile(
    r"\b(?:poe|por|coloca|colocar|coloque|bota|botar|bote|passa|passar|joga|manda|deixa|"
    r"deixar|muda|mudar|volta|voltar|vai|pode ir)\b.{0,50}?\b"
    r"(?P<prep>a|na|pra|para|em|pro) (?P<s>venda|vitrine|preparacao|documentacao|oficina)\b"
)
_A_VENDA_POR = re.compile(r"\b(?:venda|vitrine)\s+(?:por|a|de)\s+(?:r\$\s*)?\d")
_SITUACOES_ESCRITAS = {
    "venda": Situacao.a_venda,
    "vitrine": Situacao.a_venda,
    "preparacao": Situacao.preparacao,
    "oficina": Situacao.preparacao,
    "documentacao": Situacao.documentacao,
}
# Campo citado antes do valor novo: "muda a cor da factor para azul" -> o valor é a cor.
_CAMPO_CITADO = (
    ("modelo", re.compile(r"\bmodelo\b(?!\s*[:=\-]?\s*\d)")),
    ("marca", re.compile(r"\bmarca\b")),
    ("cor", re.compile(r"\bcor\b")),
    ("km", re.compile(r"\b(?:km|kms|quilometragem|kilometragem|hodometro)\b")),
    ("valor_compra", re.compile(r"\b(?:valor|preco) d[ae] compra\b|\bcusto\b")),
    ("preco_venda", re.compile(r"\b(?:preco|valor de venda|valor da venda|anuncio)\b")),
    ("placa", re.compile(r"\bplacas?\b(?!\s*[:=\-]?\s*[a-z]{3}\s*-?\s*\d)")),
    ("chassi", re.compile(r"\bchassis?\b(?!\s*[:=\-]?\s*[a-z0-9]*\d)")),
    ("renavam", re.compile(r"\brenavam\b(?!\s*[:=\-]?\s*\d)")),
    ("ano_modelo", re.compile(r"\bano\b(?!\s*[:=\-]?\s*\d)")),
    ("data_compra", re.compile(r"\bdata d[ae] compra\b")),
)
_VERBO_DE_PRECO = re.compile(
    r"\b(?:custa|custando|vale|sai por|saindo por|baixa|baixar|abaixa|abaixar|sobe|subir|"
    r"aumenta|aumentar|reduz|reduzir|diminui|diminuir)\b"
)
_CAMPOS_DE_REFERENCIA = ("tipo", "marca", "modelo")


def _sem_os_apagados(leitor: _Leitor) -> str:
    """O texto original, com espaços no lugar do que já foi lido."""
    return "".join(
        o if b == n else " "
        for o, b, n in zip(leitor.original, leitor.buf, leitor.norm, strict=True)
    )


def ler_edicao(leitor: _Leitor, limpo: str, *, sim: bool, nao: bool) -> Interpretacao:
    r = leitor.r
    ano, dia = leitor.ano_atual, leitor.dia

    if leitor.contexto == "edicao":
        # alteração em andamento: a frase traz só valores novos ("e o km é 15 mil"),
        # ou aponta o veículo que perguntei ("a branca", "placa ABC1D23")
        if leitor.aguardando == "veiculo":
            ref = _Leitor(leitor.original, None, ano, None, dia).referencia()
            if ref and not ref.get("dois"):
                r.intencao, r.referencia = "edicao", ref
                return r
        alvo = leitor.aguardando if leitor.aguardando not in ("veiculo", "mudanca") else None
        valores = _Leitor(leitor.original, alvo, ano, "cadastro", dia).ler()
        if valores.intencao != "cadastro":
            valores.campos.clear()
            return valores
        _juntar(r, valores)
        return r

    # 1. o que sai: "tira o preço da biz"; e a etapa nova: "põe a biz à venda"
    leitor.remocoes()
    m = _SITUACAO_NOVA.search(leitor.texto())
    if m:
        r.campos["situacao"] = _SITUACOES_ESCRITAS[m["s"]]
        leitor.apagar(m.start("prep"), m.end())
    else:
        leitor.situacao()
        if "situacao" in r.campos:
            for padrao in (r"\ba venda\b", r"\bna vitrine\b"):
                for achado in list(re.finditer(padrao, leitor.texto())):
                    leitor.apagar(achado.start(), achado.end())

    # 2. corta no ponto em que começa o valor novo
    texto = _sem_os_apagados(leitor)
    marcador = _MARCADOR.search(leitor.texto())
    if marcador:
        antes, depois = texto[: marcador.start()], texto[marcador.start() :]
        alvo = _campo_citado(_normalizar(antes), depois)
        ref = _Leitor(antes, None, ano, None, dia).referencia()
        valores = _Leitor(depois, alvo, ano, "cadastro", dia).ler()
        if alvo in ("marca", "modelo"):  # "troca o modelo pra biz 110i": muda o próprio nome
            for campo in _CAMPOS_DE_REFERENCIA:
                if campo in valores.campos:
                    r.campos[campo] = valores.campos.pop(campo)
    else:
        ref = _Leitor(texto, None, ano, None, dia).referencia()
        # "põe a biz à venda por 11.900": o valor depois da etapa é o preço
        alvo = "preco_venda" if _A_VENDA_POR.search(leitor.norm) else None
        valores = _Leitor(texto, alvo, ano, "cadastro", dia).ler()
        for campo in ("placa", "cor", "ano_fabricacao", "ano_modelo"):
            valores.campos.pop(campo, None)  # sem valor novo marcado, isso é o veículo
        valores.avisos = [a for a in valores.avisos if not a.startswith("Considerei")]
    if not ref:
        # sem dizer qual veículo ("tira o preço", "muda a cor pra azul"): é como sempre foi,
        # um dado de cadastro
        return _Leitor(leitor.original, leitor.aguardando, ano, "cadastro", dia).ler()
    r.intencao = "edicao"
    r.referencia = ref
    _juntar(r, valores)
    return r


def _campo_citado(antes_norm: str, depois: str) -> str | None:
    """O campo que a pessoa citou antes do valor novo, ou o preço quando o verbo é de preço."""
    melhor: tuple[int, str] | None = None
    for campo, padrao in _CAMPO_CITADO:
        for m in padrao.finditer(antes_norm):
            if melhor is None or m.end() > melhor[0]:
                melhor = (m.end(), campo)
    if melhor:
        return melhor[1]
    if _VERBO_DE_PRECO.search(antes_norm) or _VERBO_DE_PRECO.search(_normalizar(depois)):
        return "preco_venda"
    return None


def _juntar(r: Interpretacao, valores: Interpretacao) -> None:
    for campo, valor in valores.campos.items():
        if campo not in _CAMPOS_DE_REFERENCIA:
            r.campos[campo] = valor
    for campo in valores.remover:
        if campo not in r.remover:
            r.remover.append(campo)
    r.erros.extend(valores.erros)
    r.avisos.extend(valores.avisos)
    r.soltos.extend(valores.soltos)
    r.perguntas.extend(valores.perguntas)
    if valores.intencao == "cadastro" or r.campos or r.remover:
        r.intencao = "edicao"
