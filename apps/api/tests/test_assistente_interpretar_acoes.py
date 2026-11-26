"""Interpretador (função pura): venda, alteração de veículo, data da compra e marca fora do
catálogo. O dia de hoje é fixo (26/11/2026) para "ontem", "dia 20" e datas futuras."""

import enum
from datetime import date
from decimal import Decimal

import pytest

from app.assistente import interpretar

HOJE = date(2026, 11, 26)


def ler(frase: str, aguardando: str | None = None, contexto: str | None = None):
    return interpretar(frase, aguardando, ano_atual=2026, contexto=contexto, dia=HOJE)


def limpo(dados: dict) -> dict:
    saida = {}
    for campo, valor in dados.items():
        if isinstance(valor, enum.Enum):
            valor = valor.value
        elif isinstance(valor, Decimal):
            valor = f"{valor:.2f}"
        saida[campo] = valor
    return saida


CG = {"tipo": "moto", "marca": "Honda"}

# ---------- Venda ----------


@pytest.mark.parametrize(
    "frase, referencia, dados",
    [
        (
            "vendi a CG 160 placa ABC1D23 pro João Silva por 14.900 à vista, vendedor Carlos",
            {**CG, "modelo": "CG 160", "placa": "ABC1D23"},
            {
                "comprador": "João Silva",
                "valor": "14900.00",
                "forma": "a_vista",
                "vendedor_nome": "Carlos",
            },
        ),
        (
            "o carlos vendeu a xre 300 pra maria de fátima por 22 mil financiado pelo bradesco",
            {**CG, "modelo": "XRE 300"},
            {
                "comprador": "Maria de Fátima",
                "valor": "22000.00",
                "forma": "financiado_banco",
                "banco": "Bradesco",
                "vendedor_nome": "Carlos",
            },
        ),
        (
            "vendi a biz final 23 pro josé, à vista, pelo anunciado",
            {**CG, "modelo": "Biz", "placa_final": "23"},
            {"comprador": "José", "forma": "a_vista", "valor_anunciado": True},
        ),
        (
            "vendi a biz pro joão em 10x de 1.200 com entrada de 3 mil, primeira parcela dia 10/12",
            {**CG, "modelo": "Biz"},
            {
                "comprador": "João",
                "forma": "parcelado_loja",
                "numero_parcelas": 10,
                "valor_parcela": "1200.00",
                "entrada": "3000.00",
                "primeiro_vencimento": date(2026, 12, 10),
            },
        ),
        (
            "vendi a hilux 4x4 pro pedro por 180 mil",  # 4x4 não é parcela
            {"tipo": "carro", "marca": "Toyota", "modelo": "Hilux 4x4"},
            {"comprador": "Pedro", "valor": "180000.00"},
        ),
        (
            "vendi a biz ontem pro joão por 9 mil, eu que vendi",
            {**CG, "modelo": "Biz"},
            {
                "comprador": "João",
                "valor": "9000.00",
                "data_venda": date(2026, 11, 25),
                "vendedor_eu": True,
            },
        ),
        (
            "vendi a biz 2021 branca pro joão 9.500",  # número sem "por": o único dinheiro
            {**CG, "modelo": "Biz", "ano": 2021, "cor": "Branca"},
            {"comprador": "João", "valor": "9500.00"},
        ),
        (
            "dar baixa na venda da fan 160 vermelha, cliente Ana Paula, whats (86) 99999-0001",
            {**CG, "modelo": "CG 160 Fan", "cor": "Vermelha"},
            {"comprador": "Ana Paula", "telefone": "86999990001"},
        ),
        (
            "vendi a biz pro joão com 15 mil km por 9 mil",  # km não é dinheiro da venda
            {**CG, "modelo": "Biz"},
            {"comprador": "João", "valor": "9000.00"},
        ),
    ],
)
def test_venda(frase, referencia, dados):
    lido = ler(frase)
    assert lido.intencao == "venda" and lido.venda is True
    assert limpo(lido.referencia) == referencia
    assert limpo(lido.venda_dados) == dados
    assert lido.campos == {} and lido.erros == [] and lido.soltos == []


@pytest.mark.parametrize(
    "frase, erro",
    [
        ("vendi a biz pro joão por 14", "como valor da venda, o que é pouco"),
        ("vendi a biz pro joão em 05/01/2027", "A data da venda não pode ser futura"),
        ("vendi a biz pro joão, cpf 111.111.111-11", "CPF"),
    ],
)
def test_venda_com_dado_invalido_vira_erro(frase, erro):
    lido = ler(frase)
    assert lido.intencao == "venda" and any(erro in e for e in lido.erros), lido.erros


def test_venda_com_dois_valores_sem_pista_pergunta():
    lido = ler("vendi a biz pro joão 9.500 12.000")
    assert "valor" not in lido.venda_dados and len(lido.soltos) == 2


@pytest.mark.parametrize(
    "frase",
    [
        "quantas motos vendemos em outubro?",
        "qual foi o total vendido no mês",
        "vendo por 14.900",  # preço de anúncio, não venda feita
        "biz 125 2021 comprei por 9 mil vou vender por 12 mil",
    ],
)
def test_nao_e_venda(frase):
    assert ler(frase).intencao != "venda"


@pytest.mark.parametrize(
    "aguardando, frase, dados",
    [
        ("comprador", "João Silva", {"comprador": "João Silva"}),
        (
            "comprador",
            "joão da silva, whats 86 99999-0001",
            {"comprador": "João da Silva", "telefone": "86999990001"},
        ),
        ("vendedor", "Carlos", {"vendedor_nome": "Carlos"}),
        ("vendedor", "eu mesmo", {"vendedor_eu": True}),
        ("valor_venda", "14.900", {"valor": "14900.00"}),
        ("valor_venda", "pelo anunciado", {"valor_anunciado": True}),
        ("forma", "à vista", {"forma": "a_vista"}),
        ("forma", "financiado", {"forma": "financiado_banco"}),
        ("forma", "parcelado na loja", {"forma": "parcelado_loja"}),
        ("numero_parcelas", "10", {"numero_parcelas": 10}),
        (
            "numero_parcelas",
            "12x de 990",
            {"forma": "parcelado_loja", "numero_parcelas": 12, "valor_parcela": "990.00"},
        ),
        ("valor_parcela", "990", {"valor_parcela": "990.00"}),
        ("primeiro_vencimento", "10/12", {"primeiro_vencimento": date(2026, 12, 10)}),
        ("primeiro_vencimento", "dia 5", {"primeiro_vencimento": date(2026, 12, 5)}),
        ("confirmacao", "não, foi 14 mil", {"valor": "14000.00"}),
    ],
)
def test_resposta_na_venda(aguardando, frase, dados):
    lido = ler(frase, aguardando, "venda")
    assert lido.intencao == "venda"
    assert limpo(lido.venda_dados) == dados
    assert lido.referencia == {}


@pytest.mark.parametrize(
    "frase, intencao",
    [("sim", "afirmacao"), ("confirmo", "afirmacao"), ("não", "negacao"), ("cancela", "cancelar")],
)
def test_confirmacao_na_venda(frase, intencao):
    lido = ler(frase, "confirmacao", "venda")
    assert lido.intencao == intencao and lido.venda_dados == {} and lido.referencia == {}


# ---------- Alteração ----------


@pytest.mark.parametrize(
    "frase, referencia, campos",
    [
        (
            "a CG placa ABC1D23 agora custa 13.900",
            {**CG, "modelo": "CG", "placa": "ABC1D23"},
            {"preco_venda": "13900.00"},
        ),
        (
            "põe a Biz 125 branca à venda",
            {**CG, "modelo": "Biz 125", "cor": "Branca"},
            {"situacao": "a_venda"},
        ),
        ("a XRE 300 tá com 15 mil km", {**CG, "modelo": "XRE 300"}, {"km": 15000}),
        (
            "muda a cor da Factor para azul",
            {"tipo": "moto", "marca": "Yamaha", "modelo": "Factor"},
            {"cor": "Azul"},
        ),
        ("baixa o preço da biz pra 9 mil", {**CG, "modelo": "Biz"}, {"preco_venda": "9000.00"}),
        (
            "a cg vermelha agora é preta",
            {**CG, "modelo": "CG", "cor": "Vermelha"},
            {"cor": "Preta"},
        ),
        (
            "a placa da biz final 23 agora é ABC1D24",
            {**CG, "modelo": "Biz", "placa_final": "23"},
            {"placa": "ABC1D24"},
        ),
        (
            "corrige o valor de compra da xre pra 18 mil",
            {**CG, "modelo": "XRE"},
            {"valor_compra": "18000.00"},
        ),
        (
            "põe a biz XYZ1A11 à venda por 11.900",
            {**CG, "modelo": "Biz", "placa": "XYZ1A11"},
            {"situacao": "a_venda", "preco_venda": "11900.00"},
        ),
        (
            "a biz placa XYZ1A11 agora custa 11.900 e pode ir pra vitrine",
            {**CG, "modelo": "Biz", "placa": "XYZ1A11"},
            {"situacao": "a_venda", "preco_venda": "11900.00"},
        ),
        (
            "coloca a fan 160 2021 em preparação",
            {**CG, "modelo": "CG 160 Fan", "ano": 2021},
            {"situacao": "preparacao"},
        ),
    ],
)
def test_alteracao(frase, referencia, campos):
    lido = ler(frase)
    assert lido.intencao == "edicao"
    assert limpo(lido.referencia) == referencia
    assert limpo(lido.campos) == campos
    assert lido.erros == [] and lido.soltos == []


def test_alteracao_que_tira_um_dado():
    lido = ler("tira o preço da biz")
    assert lido.intencao == "edicao" and lido.remover == ["preco_venda"]
    assert limpo(lido.referencia) == {**CG, "modelo": "Biz"}


@pytest.mark.parametrize(
    "frase",
    [
        "biz 125 2021 esta com 22 mil km comprei por 9 mil",  # comprou: é cadastro
        "chegou uma xre 300, agora é só anunciar, paguei 19 mil",
        "quanto custa a biz?",  # pergunta
        "tira o preço",  # sem dizer qual veículo: é o rascunho do cadastro
        "muda a cor pra azul",
    ],
)
def test_nao_e_alteracao(frase):
    assert ler(frase).intencao != "edicao"


@pytest.mark.parametrize(
    "aguardando, frase, campos",
    [
        (None, "e o km é 15 mil", {"km": 15000}),
        ("preco_venda", "9.900", {"preco_venda": "9900.00"}),
        ("mudanca", "cor azul e 12 mil km", {"cor": "Azul", "km": 12000}),
        (None, "à venda por 10 mil", {"situacao": "a_venda", "preco_venda": "10000.00"}),
    ],
)
def test_alteracao_em_andamento(aguardando, frase, campos):
    lido = ler(frase, aguardando, "edicao")
    assert lido.intencao == "edicao" and limpo(lido.campos) == campos


def test_alteracao_em_andamento_resposta_sobre_o_veiculo():
    lido = ler("a de placa ABC1D23", "veiculo", "edicao")
    assert lido.intencao == "edicao" and lido.referencia == {"placa": "ABC1D23"}


# ---------- Data da compra ----------


@pytest.mark.parametrize(
    "frase, data",
    [
        ("biz 125 comprei hoje por 9 mil", date(2026, 11, 26)),
        ("biz 125 comprei ontem por 9 mil", date(2026, 11, 25)),
        ("ontem comprei uma biz 125 por 9 mil", date(2026, 11, 25)),
        ("biz 125 comprei dia 20 por 9 mil", date(2026, 11, 20)),
        ("biz 125 comprei em 15/11 por 9 mil", date(2026, 11, 15)),
        ("biz 125 comprei 15/11/2026 por 9 mil", date(2026, 11, 15)),
        ("biz 125 comprada em 3/10/26 por 9 mil", date(2026, 10, 3)),
        ("biz 125 comprei por 9 mil anteontem", date(2026, 11, 24)),
        ("biz 125 comprei dia 5 de outubro por 9 mil", date(2026, 10, 5)),
        ("data da compra 10/11/2026 biz 125 por 9 mil", date(2026, 11, 10)),
    ],
)
def test_data_da_compra(frase, data):
    lido = ler(frase)
    assert lido.campos["data_compra"] == data
    assert lido.campos["valor_compra"] == Decimal("9000.00") and lido.erros == []


@pytest.mark.parametrize(
    "aguardando, frase, data",
    [
        ("data_compra", "ontem", date(2026, 11, 25)),
        ("data_compra", "28/10/2026", date(2026, 10, 28)),
    ],
)
def test_data_da_compra_como_resposta(aguardando, frase, data):
    assert ler(frase, aguardando, "cadastro").campos == {"data_compra": data}


def test_data_da_compra_futura_e_erro():
    lido = ler("biz 125 comprei 15/12/2026 por 9 mil")
    assert "data_compra" not in lido.campos
    assert lido.erros == ["A data da compra não pode ser futura (15/12/2026)."]


@pytest.mark.parametrize(
    "frase, sugestao",
    [
        ("biz 125 comprei dia 28 por 9 mil", date(2026, 10, 28)),  # dia 28 ainda não chegou
        ("biz 125 comprei 20/12 por 9 mil", date(2025, 12, 20)),  # 20/12 deste ano é futuro
    ],
)
def test_data_da_compra_ambigua_vira_pergunta(frase, sugestao):
    lido = ler(frase)
    assert "data_compra" not in lido.campos and lido.erros == []
    [(campo, pergunta, sugerida)] = lido.perguntas
    assert (campo, sugerida) == ("data_compra", sugestao)
    assert sugestao.strftime("%d/%m/%Y") in pergunta


@pytest.mark.parametrize(
    "frase",
    [
        "biz 21/22 comprei por 9 mil",  # par de anos
        "biz 125 comprei por 9 mil, o ipva vence dia 10",
        "biz 125 2021 chegou hoje comprei por 9 mil",  # "chegou hoje" não diz quando comprou
    ],
)
def test_sem_data_da_compra(frase):
    lido = ler(frase)
    assert "data_compra" not in lido.campos and lido.perguntas == [] and lido.erros == []


def test_dia_que_nao_existe():
    lido = ler("biz 125 comprei 31/11/2026 por 9 mil")
    assert lido.erros == ["A data “31/11/2026” não existe no calendário."]


# ---------- Marca fora do catálogo ----------


@pytest.mark.parametrize(
    "frase, marca, modelo",
    [
        ("lifan 530 2015 prata comprei por 20 mil", "Lifan", "530"),
        ("Zontes Tactic 400 2023 comprei por 30 mil", "Zontes", "Tactic 400"),
        ("oi, chegou uma gwm haval 2023 preta paguei 90 mil", "GWM", "Haval"),
        ("bom dia, Jonny Quick 150 2019 vermelha 9 mil km", "Jonny", "Quick 150"),
    ],
)
def test_marca_fora_do_catalogo(frase, marca, modelo):
    lido = ler(frase)
    assert (lido.campos["marca"], lido.campos["modelo"]) == (marca, modelo)
    assert "tipo" not in lido.campos  # vira a pergunta "é moto ou carro?"


@pytest.mark.parametrize(
    "frase",
    [
        "tabela fipe 15 mil comprei por 11 mil",
        "obrigado pela ajuda",
        "quero cadastrar uma moto",
        "galera 2015 comprei por 9 mil",
        "preço 15.900",
        "kkkk 2020",
        "lifan",  # sem modelo nem outro dado de veículo
        "teste 123",
    ],
)
def test_palavra_comum_nao_vira_marca(frase):
    assert "marca" not in ler(frase).campos
