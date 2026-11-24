"""Interpretador do assistente: frase -> campos. Função pura, sem banco.

As frases imitam o jeito de digitar no celular: sem acento, sem pontuação, abreviado e em
qualquer ordem. `campos()` compara o dicionário inteiro, então o teste também pega o que
foi extraído a mais.
"""

import enum
from decimal import Decimal

import pytest

from app.assistente import interpretar


def ler(frase: str, aguardando: str | None = None):
    return interpretar(frase, aguardando, ano_atual=2026)


def campos(frase: str, aguardando: str | None = None) -> dict:
    limpos = {}
    for campo, valor in ler(frase, aguardando).campos.items():
        if isinstance(valor, enum.Enum):
            valor = valor.value
        elif isinstance(valor, Decimal):
            valor = f"{valor:.2f}"
        limpos[campo] = valor
    return limpos


CG = {"tipo": "moto", "marca": "Honda", "modelo": "CG 160 Fan"}

FRASES_COMPLETAS = [
    (
        "Cadastra uma Honda CG 160 Fan 2022 vermelha, placa ABC1D23, 18.500 km, "
        "comprei por 11.500 e vou vender por 14.900",
        {
            **CG,
            "ano_fabricacao": 2022,
            "ano_modelo": 2022,
            "cor": "Vermelha",
            "placa": "ABC1D23",
            "km": 18500,
            "valor_compra": "11500.00",
            "preco_venda": "14900.00",
        },
    ),
    (
        "cg 160 fan 22 vermelha abc1d23 18500km paguei 11500 vender 14900",
        {
            **CG,
            "ano_fabricacao": 2022,
            "ano_modelo": 2022,
            "cor": "Vermelha",
            "placa": "ABC1D23",
            "km": 18500,
            "valor_compra": "11500.00",
            "preco_venda": "14900.00",
        },
    ),
    (
        "chegou uma biz 125 2021 branca, 22 mil km, comprei por 9 mil",
        {
            "tipo": "moto",
            "marca": "Honda",
            "modelo": "Biz 125",
            "ano_fabricacao": 2021,
            "ano_modelo": 2021,
            "cor": "Branca",
            "km": 22000,
            "valor_compra": "9000.00",
        },
    ),
    (
        "fiat uno way 1.0 2015 prata placa PIA1B23 98.000km compra R$ 24.000,00 venda R$ 31.900,00",
        {
            "tipo": "carro",
            "marca": "Fiat",
            "modelo": "Uno Way 1.0",
            "ano_fabricacao": 2015,
            "ano_modelo": 2015,
            "cor": "Prata",
            "placa": "PIA1B23",
            "km": 98000,
            "valor_compra": "24000.00",
            "preco_venda": "31900.00",
        },
    ),
    (
        "hb20 1.0 2018/2019 branco 71 mil rodados, peguei por 42,5 mil, anunciar por 49.900",
        {
            "tipo": "carro",
            "marca": "Hyundai",
            "modelo": "HB20 1.0",
            "ano_fabricacao": 2018,
            "ano_modelo": 2019,
            "cor": "Branco",
            "km": 71000,
            "valor_compra": "42500.00",
            "preco_venda": "49900.00",
        },
    ),
    (
        "moto yamaha factor 150 ano 2023 azul 9.000 km custou 13,2 mil",
        {
            "tipo": "moto",
            "marca": "Yamaha",
            "modelo": "Factor 150",
            "ano_fabricacao": 2023,
            "ano_modelo": 2023,
            "cor": "Azul",
            "km": 9000,
            "valor_compra": "13200.00",
        },
    ),
    (
        "novo veiculo: carro, Volkswagen Gol 1.6, 2014, 120000 km, comprado por 28k, preco 34.900",
        {
            "tipo": "carro",
            "marca": "Volkswagen",
            "modelo": "Gol 1.6",
            "ano_fabricacao": 2014,
            "ano_modelo": 2014,
            "km": 120000,
            "valor_compra": "28000.00",
            "preco_venda": "34900.00",
        },
    ),
    (
        "pop 110i 2020 preta zero km... nao, 15 mil km",  # a última informação vale
        {
            "tipo": "moto",
            "marca": "Honda",
            "modelo": "Pop 110i",
            "ano_fabricacao": 2020,
            "ano_modelo": 2020,
            "cor": "Preta",
            "km": 15000,
        },
    ),
    (
        "Cadastra aí pra mim: Biz 125 ES 2019, vermelha, 32 mil km, placa OEA-4521, "
        "paguei 8.500 e quero vender por 10.900.",
        {
            "tipo": "moto",
            "marca": "Honda",
            "modelo": "Biz 125 ES",
            "ano_fabricacao": 2019,
            "ano_modelo": 2019,
            "cor": "Vermelha",
            "km": 32000,
            "placa": "OEA4521",
            "valor_compra": "8500.00",
            "preco_venda": "10900.00",
        },
    ),
    (
        "CHEGOU UMA HONDA POP 110I 2021 BRANCA 12 MIL KM COMPREI POR 6.500",
        {
            "tipo": "moto",
            "marca": "Honda",
            "modelo": "Pop 110i",
            "ano_fabricacao": 2021,
            "ano_modelo": 2021,
            "cor": "Branca",
            "km": 12000,
            "valor_compra": "6500.00",
        },
    ),
    (
        "Ford Ka 1.0 2018 branco, placa QWE-1234, 60.000 km, R$ 35.000 de compra, "
        "R$ 41.900 de venda",
        {
            "tipo": "carro",
            "marca": "Ford",
            "modelo": "Ka 1.0",
            "ano_fabricacao": 2018,
            "ano_modelo": 2018,
            "cor": "Branco",
            "placa": "QWE1234",
            "km": 60000,
            "valor_compra": "35000.00",
            "preco_venda": "41900.00",
        },
    ),
    (
        "Marca: Honda | Modelo: CG 160 Fan | Ano: 2022 | Cor: Vermelha | Km: 18.500 | "
        "Placa: ABC1D23 | Compra: R$ 11.500,00 | Venda: R$ 14.900,00",
        {
            **CG,
            "ano_fabricacao": 2022,
            "ano_modelo": 2022,
            "cor": "Vermelha",
            "km": 18500,
            "placa": "ABC1D23",
            "valor_compra": "11500.00",
            "preco_venda": "14900.00",
        },
    ),
    (
        "onix lt 1.0 2019, branco, 64.000 km, placa PIF7G89, comprei por 46 mil, "
        "vendo por 56.900, já pode anunciar",
        {
            "tipo": "carro",
            "marca": "Chevrolet",
            "modelo": "Onix LT 1.0",
            "ano_fabricacao": 2019,
            "ano_modelo": 2019,
            "cor": "Branco",
            "km": 64000,
            "placa": "PIF7G89",
            "valor_compra": "46000.00",
            "preco_venda": "56900.00",
            "situacao": "a_venda",
        },
    ),
    (
        "honda cg 160 fan 2022/2023 prata 12.000km compra 12500 venda 15900 "
        "chassi 9C2KC2200NR123456 renavam 01234567890",
        {
            **CG,
            "ano_fabricacao": 2022,
            "ano_modelo": 2023,
            "cor": "Prata",
            "km": 12000,
            "valor_compra": "12500.00",
            "preco_venda": "15900.00",
            "chassi": "9C2KC2200NR123456",
            "renavam": "01234567890",
        },
    ),
]


@pytest.mark.parametrize("frase, esperado", FRASES_COMPLETAS)
def test_frase_completa(frase, esperado):
    lido = ler(frase)
    assert lido.intencao == "cadastro"
    assert campos(frase) == esperado
    assert lido.erros == [] and lido.soltos == []


# ---------- Dinheiro ----------


@pytest.mark.parametrize(
    "frase, esperado",
    [
        ("comprei por 11.500", {"valor_compra": "11500.00"}),
        ("paguei 11500", {"valor_compra": "11500.00"}),
        ("compra R$ 11.500,00", {"valor_compra": "11500.00"}),
        ("custou 11,5 mil", {"valor_compra": "11500.00"}),
        ("peguei por 11 mil", {"valor_compra": "11000.00"}),
        ("paguei 11 mil e 500", {"valor_compra": "11500.00"}),
        ("comprado por 11k", {"valor_compra": "11000.00"}),
        ("comprei por 11.5k", {"valor_compra": "11500.00"}),
        ("paguei onze mil e quinhentos", {"valor_compra": "11500.00"}),
        ("paguei onze e quinhentos", {"valor_compra": "11500.00"}),
        ("paguei 11 e meio", {"valor_compra": "11500.00"}),
        ("custou nove mil", {"valor_compra": "9000.00"}),
        ("entrada na loja 9.800", {"valor_compra": "9800.00"}),
        ("valor de compra: 24000", {"valor_compra": "24000.00"}),
        ("dei 9 mil nessa", {"valor_compra": "9000.00"}),
        ("na verdade comprei por 11 mil", {"valor_compra": "11000.00"}),
        ("R$ 1.234.567,89 de compra", {"valor_compra": "1234567.89"}),
        ("vender por 14.900", {"preco_venda": "14900.00"}),
        ("vendo por 14900", {"preco_venda": "14900.00"}),
        ("venda 31.900,00", {"preco_venda": "31900.00"}),
        ("anunciar por 49.900", {"preco_venda": "49900.00"}),
        ("preco 15.900", {"preco_venda": "15900.00"}),
        ("por quanto sai: 12 mil", {"preco_venda": "12000.00"}),
        ("pedindo 18,5 mil", {"preco_venda": "18500.00"}),
        ("muda o preço pra 15.900", {"preco_venda": "15900.00"}),
        ("o preço é 15.900 e não 14.900", {"preco_venda": "15900.00"}),
        (
            "preço de compra 11000 preço de venda 14000",
            {"valor_compra": "11000.00", "preco_venda": "14000.00"},
        ),
        (
            "11500 de compra e 14900 de venda",
            {"valor_compra": "11500.00", "preco_venda": "14900.00"},
        ),
        ("11500 compra 14900 venda", {"valor_compra": "11500.00", "preco_venda": "14900.00"}),
        (
            "compra 8 mil venda 10 mil e 500",
            {"valor_compra": "8000.00", "preco_venda": "10500.00"},
        ),
        (
            "comprei por R$11.500,00 vendo por R$14.900,00",
            {"valor_compra": "11500.00", "preco_venda": "14900.00"},
        ),
        # a palavra de compra longe do número
        (
            "comprei uma cg 160 fan 2022 vermelha por 11.500",
            {
                **CG,
                "ano_fabricacao": 2022,
                "ano_modelo": 2022,
                "cor": "Vermelha",
                "valor_compra": "11500.00",
            },
        ),
        # número com cara de ano, mas colado na palavra de compra/venda: é dinheiro
        ("paguei 2000", {"valor_compra": "2000.00"}),
        ("vendo por 2020", {"preco_venda": "2020.00"}),
    ],
)
def test_dinheiro(frase, esperado):
    assert campos(frase) == esperado


@pytest.mark.parametrize(
    "frase, soltos",
    [
        ("biz 125 11500 14900", [11500, 14900]),  # dois valores sem pista: não chuta
        ("biz 125 R$ 9.000", [9000]),
        ("biz 110i 2019 vermelha 30 mil km 8.500", [8500]),
        ("por 9 mil", [9000]),
        ("valor 9 mil", [9000]),
        # "comprei" longe do número e sem "por": 22 mil pode ser o km
        ("comprei uma biz 2021 22 mil", [22000]),
        ("peguei uma biz 2018 numa troca, vale uns 8 mil", [8000]),
    ],
)
def test_valor_sem_pista_nao_e_chutado(frase, soltos):
    lido = ler(frase)
    assert [int(valor) for valor, _ in lido.soltos] == soltos
    assert "valor_compra" not in lido.campos and "preco_venda" not in lido.campos
    assert "km" not in lido.campos or lido.campos["km"] == 30000


@pytest.mark.parametrize(
    "frase",
    ["paguei 9", "comprei por 11,5", "comprei por R$ 11,50", "vendo por 18", "paguei 150"],
)
def test_valor_na_escala_errada_vira_pergunta(frase):
    """ "11,5" depois de "comprei por" quase sempre é 11,5 mil: não grava R$ 11,50."""
    lido = ler(frase)
    assert lido.campos == {}
    assert len(lido.erros) == 1 and "mil" in lido.erros[0]


def test_valor_abaixo_de_mil_so_com_reais_por_extenso():
    assert campos("paguei 800") == {}
    assert "800 reais" in ler("paguei 800").erros[0]
    assert campos("paguei 800 reais") == {"valor_compra": "800.00"}
    assert campos("paguei R$ 800") == {"valor_compra": "800.00"}
    assert campos("0", "valor_compra") == {"valor_compra": "0.00"}  # o formulário também aceita


# ---------- Quilometragem ----------


@pytest.mark.parametrize(
    "frase, km",
    [
        ("18.500 km", 18500),
        ("18500km", 18500),
        ("18 mil km", 18000),
        ("km 18500", 18500),
        ("km: 18.500", 18500),
        ("20 mil rodados", 20000),
        ("0 km", 0),
        ("zero km", 0),
        ("o km é 20 mil", 20000),
        ("quilometragem 45.300", 45300),
        ("rodou 30 mil", 30000),
        ("com 18 mil e 500 km", 18500),
        ("km errado, é 20.500", 20500),
    ],
)
def test_km(frase, km):
    assert campos(frase) == {"km": km}


def test_km_com_ano_antes():
    assert campos("honda xre 300 abs 2021 km 15000") == {
        "tipo": "moto",
        "marca": "Honda",
        "modelo": "XRE 300 ABS",
        "ano_fabricacao": 2021,
        "ano_modelo": 2021,
        "km": 15000,
    }


# ---------- Ano ----------

BIZ = {"tipo": "moto", "marca": "Honda", "modelo": "Biz"}


@pytest.mark.parametrize(
    "frase, esperado",
    [
        ("biz 2022", {**BIZ, "ano_fabricacao": 2022, "ano_modelo": 2022}),
        ("biz ano 2022", {**BIZ, "ano_fabricacao": 2022, "ano_modelo": 2022}),
        ("biz 2021/2022", {**BIZ, "ano_fabricacao": 2021, "ano_modelo": 2022}),
        ("biz 21/22", {**BIZ, "ano_fabricacao": 2021, "ano_modelo": 2022}),
        ("biz 2021 2022", {**BIZ, "ano_fabricacao": 2021, "ano_modelo": 2022}),
        ("biz 125 22", {**BIZ, "modelo": "Biz 125", "ano_fabricacao": 2022, "ano_modelo": 2022}),
        ("biz ano 98", {**BIZ, "ano_fabricacao": 1998, "ano_modelo": 1998}),
        (
            "biz fabricação 2021 modelo 2022",
            {**BIZ, "ano_fabricacao": 2021, "ano_modelo": 2022},
        ),
        (
            "civic 17",
            {
                "tipo": "carro",
                "marca": "Honda",
                "modelo": "Civic",
                "ano_fabricacao": 2017,
                "ano_modelo": 2017,
            },
        ),
        (
            "fusca 1976",
            {
                "tipo": "carro",
                "marca": "Volkswagen",
                "modelo": "Fusca",
                "ano_fabricacao": 1976,
                "ano_modelo": 1976,
            },
        ),
    ],
)
def test_ano(frase, esperado):
    assert campos(frase) == esperado


def test_ano_unico_avisa_a_suposicao():
    assert ler("biz 2022").avisos == ["Considerei 2022 como ano de fabricação e do modelo."]
    assert ler("biz 2021/2022").avisos == []
    assert "2022" in ler("cg 160 fan 22 vermelha").avisos[0]


@pytest.mark.parametrize(
    "frase, esperado",
    [
        # cilindrada e motor não são ano, km nem preço
        ("cg 160", {"tipo": "moto", "marca": "Honda", "modelo": "CG 160"}),
        ("biz 125", {**BIZ, "modelo": "Biz 125"}),
        ("xre 300", {"tipo": "moto", "marca": "Honda", "modelo": "XRE 300"}),
        ("factor 150", {"tipo": "moto", "marca": "Yamaha", "modelo": "Factor 150"}),
        ("uno way 1.0", {"tipo": "carro", "marca": "Fiat", "modelo": "Uno Way 1.0"}),
        ("gol 1000", {"tipo": "carro", "marca": "Volkswagen", "modelo": "Gol 1000"}),
        ("palio 16 valvulas", {"tipo": "carro", "marca": "Fiat", "modelo": "Palio"}),
        ("gol 1.0 16v", {"tipo": "carro", "marca": "Volkswagen", "modelo": "Gol 1.0 16V"}),
        (
            "titan 150 22 mil km",
            {"tipo": "moto", "marca": "Honda", "modelo": "CG 150 Titan", "km": 22000},
        ),
        # data, IPVA e "comprada em" não são o ano do veículo
        ("data da compra 10/11/2026", {}),
        ("biz ipva 2026 pago", BIZ),
        ("biz comprada em 2023", BIZ),
        # detalhes soltos não viram número de nada
        ("biz único dono 2 chaves", BIZ),
        # só uma cilindrada por modelo: o segundo número já não é do nome
        ("titan 150 800", {"tipo": "moto", "marca": "Honda", "modelo": "CG 150 Titan"}),
    ],
)
def test_nao_confunde_numeros(frase, esperado):
    lido = ler(frase)
    assert campos(frase) == esperado
    assert lido.soltos == [] and lido.erros == []


def test_ano_fora_da_faixa_e_erro_e_nao_entra():
    lido = ler("biz ano 1900")
    assert "ano_modelo" not in lido.campos and "ano_fabricacao" not in lido.campos
    assert lido.erros == ["O ano 1900 está fora da faixa que eu aceito (1950 a 2027)."]


# ---------- Placa, chassi e RENAVAM ----------


@pytest.mark.parametrize(
    "frase, placa",
    [
        ("placa abc1234", "ABC1234"),
        ("placa ABC-1234", "ABC1234"),
        ("placa abc 1234", "ABC1234"),
        ("abc-1d23", "ABC1D23"),
        ("abc 1d23", "ABC1D23"),
        ("ABC1D23", "ABC1D23"),
        ("placa: QRS1A23", "QRS1A23"),
        ("não, a placa é ABC1D24", "ABC1D24"),
        ("placa nova ABC1D24", "ABC1D24"),
    ],
)
def test_placa(frase, placa):
    assert campos(frase) == {"placa": placa}


@pytest.mark.parametrize("frase", ["fan 2022", "gol2014", "uno 2015", "biz 2021", "pop 2019"])
def test_modelo_e_ano_nao_viram_placa(frase):
    assert "placa" not in campos(frase)


def test_placa_invalida_avisa():
    lido = ler("placa abc12")
    assert lido.campos == {}
    assert lido.erros == ["Não reconheci a placa “ABC12”. Use o formato ABC1234 ou ABC1D23."]


def test_chassi_e_renavam():
    assert campos("chassi 9C2KC2200NR123456") == {"chassi": "9C2KC2200NR123456"}
    assert campos("9c2kc2200nr123456") == {"chassi": "9C2KC2200NR123456"}  # 17 caracteres
    assert campos("renavam 12345678901") == {"renavam": "12345678901"}
    assert campos("renavam: 123456789") == {"renavam": "00123456789"}
    # sem a palavra, um número comprido não é RENAVAM
    assert "renavam" not in campos("12345678901")
    assert ler("chassi 123").erros == ["Chassi inválido: use até 17 letras e números."]
    assert ler("renavam 123").erros == ["RENAVAM inválido: deve ter de 9 a 11 dígitos."]
    assert ler("chassi remarcado").campos == {}


# ---------- Tipo, marca e modelo ----------


def veiculo(tipo, marca, modelo):
    return {"tipo": tipo, "marca": marca, "modelo": modelo}


@pytest.mark.parametrize(
    "frase, esperado",
    [
        # modelo conhecido sem marca
        ("biz 125", veiculo("moto", "Honda", "Biz 125")),
        ("hb20", veiculo("carro", "Hyundai", "HB20")),
        ("gol", veiculo("carro", "Volkswagen", "Gol")),
        ("cg160 fan", veiculo("moto", "Honda", "CG 160 Fan")),
        ("xre300", veiculo("moto", "Honda", "XRE 300")),
        # apelidos de família
        ("titan 160", veiculo("moto", "Honda", "CG 160 Titan")),
        ("fan 160", veiculo("moto", "Honda", "CG 160 Fan")),
        ("bros 160", veiculo("moto", "Honda", "NXR 160 Bros")),
        ("nxr 160 bros esdd", veiculo("moto", "Honda", "NXR 160 Bros ESDD")),
        # Honda faz moto e carro: decide pelo modelo
        ("honda civic", veiculo("carro", "Honda", "Civic")),
        ("honda biz", veiculo("moto", "Honda", "Biz")),
        ("hr-v", veiculo("carro", "Honda", "HR-V")),
        ("hrv exl", veiculo("carro", "Honda", "HR-V EXL")),
        # grafia
        ("cb 500x", veiculo("moto", "Honda", "CB 500X")),
        ("cb 250f twister", veiculo("moto", "Honda", "CB 250F Twister")),
        ("nmax 160", veiculo("moto", "Yamaha", "NMax 160")),
        ("mt-07", veiculo("moto", "Yamaha", "MT-07")),
        ("yamaha fazer 250", veiculo("moto", "Yamaha", "Fazer 250")),
        ("crosser 150 z", veiculo("moto", "Yamaha", "Crosser 150 Z")),
        ("shineray jet 50", veiculo("moto", "Shineray", "Jet 50")),
        ("haojue dk 150", veiculo("moto", "Haojue", "DK 150")),
        ("avelloz az1", veiculo("moto", "Avelloz", "AZ1")),
        ("suzuki yes 125", veiculo("moto", "Suzuki", "Yes 125")),
        ("s10 2.8 4x4 diesel", veiculo("carro", "Chevrolet", "S10 2.8 4x4 Diesel")),
        ("f-250", veiculo("carro", "Ford", "F-250")),
        ("t-cross", veiculo("carro", "Volkswagen", "T-Cross")),
        ("vw gol g5 1.0", veiculo("carro", "Volkswagen", "Gol G5 1.0")),
        ("corsa classic", veiculo("carro", "Chevrolet", "Corsa Classic")),
        ("corolla xei 2.0", veiculo("carro", "Toyota", "Corolla XEi 2.0")),
        (
            "strada 1.4 working cabine dupla",
            veiculo("carro", "Fiat", "Strada 1.4 Working Cabine Dupla"),
        ),
        ("jeep renegade 1.8 sport", veiculo("carro", "Jeep", "Renegade 1.8 Sport")),
        ("citroen c4 cactus", veiculo("carro", "Citroën", "C4 Cactus")),
        # modelos que só valem junto da marca
        ("peugeot 208", veiculo("carro", "Peugeot", "208")),
        ("fiat tipo", veiculo("carro", "Fiat", "Tipo")),
        ("vw bora", veiculo("carro", "Volkswagen", "Bora")),
        # marca e modelo fora do catálogo
        ("moto Zontes Tactic 400", veiculo("moto", "Zontes", "Tactic 400")),
        ("marca Kasinski modelo Mirage 150", veiculo("moto", "Kasinski", "Mirage 150")),
        ("yamaha xyz 300", veiculo("moto", "Yamaha", "XYZ 300")),
        (
            "tipo: carro marca: fiat modelo: uno way 1.0",
            veiculo("carro", "Fiat", "Uno Way 1.0"),
        ),
    ],
)
def test_tipo_marca_modelo(frase, esperado):
    assert campos(frase) == esperado


@pytest.mark.parametrize(
    "frase, esperado",
    [
        ("honda", {"marca": "Honda"}),  # moto ou carro? não dá para saber: pergunta
        ("carro honda", {"tipo": "carro", "marca": "Honda"}),
        ("tipo moto", {"tipo": "moto"}),
        ("não é moto, é carro", {"tipo": "carro"}),
        ("chegou uma moto", {"tipo": "moto"}),
        # palavras comuns não viram modelo
        ("vou fazer o cadastro de uma cg", veiculo("moto", "Honda", "CG")),
        ("bora cadastrar uma cg 160", veiculo("moto", "Honda", "CG 160")),
        ("start", {}),
        ("moto nova chegou", {"tipo": "moto"}),
        ("moto 2022 modelo novo", {"tipo": "moto", "ano_fabricacao": 2022, "ano_modelo": 2022}),
    ],
)
def test_marca_e_tipo_sem_chute(frase, esperado):
    assert campos(frase) == esperado


# ---------- Cor ----------


@pytest.mark.parametrize(
    "frase, cor",
    [
        ("vermelha", "Vermelha"),
        ("vermelho", "Vermelho"),
        ("preto fosco", "Preto fosco"),
        ("azul marinho", "Azul marinho"),
        ("cinza grafite", "Cinza grafite"),
        ("vermelha e preta", "Vermelha e preta"),
        ("troca a cor pra preta", "Preta"),
        ("a cor é vinho", "Vinho"),
        ("cor abóbora", "Abóbora"),
    ],
)
def test_cor(frase, cor):
    assert campos(frase) == {"cor": cor}


@pytest.mark.parametrize(
    "frase",
    [
        "comprei da dona Rosa",
        "recibo em branco",
        "laudo verde",
        "sinal verde",
        "cg 160 fan",  # Fan é versão
        "uno way",  # Way é versão
        "cg 160 start",
    ],
)
def test_cor_falsos_positivos(frase):
    assert "cor" not in campos(frase)


# ---------- Situação, remoção e observações ----------


@pytest.mark.parametrize(
    "frase, situacao",
    [
        ("já pode ir pra vitrine", "a_venda"),
        ("ja esta a venda", "a_venda"),
        ("pode anunciar", "a_venda"),
        ("ainda não pode anunciar", "compra"),
        ("em preparação", "preparacao"),
    ],
)
def test_situacao(frase, situacao):
    assert campos(frase) == {"situacao": situacao}


def test_anunciar_por_e_so_preco():
    assert campos("anunciar por 49.900") == {"preco_venda": "49900.00"}
    assert campos("já está à venda por 14.900") == {
        "situacao": "a_venda",
        "preco_venda": "14900.00",
    }


@pytest.mark.parametrize(
    "frase, remover",
    [
        ("sem placa", ["placa"]),
        ("tira o preco", ["preco_venda"]),
        ("remove a cor", ["cor"]),
        ("não tem placa ainda", ["placa"]),
        ("tira o km", ["km"]),
        ("tira o ano", ["ano_fabricacao", "ano_modelo"]),
        ("apaga a observação", ["observacoes"]),
    ],
)
def test_remocao(frase, remover):
    lido = ler(frase)
    assert lido.remover == remover and lido.campos == {} and lido.intencao == "cadastro"


def test_remocao_junto_com_dados():
    lido = ler("biz 125 sem placa zero km")
    assert lido.remover == ["placa"]
    assert campos("biz 125 sem placa zero km") == {**BIZ, "modelo": "Biz 125", "km": 0}


def test_observacoes_ficam_como_foram_escritas():
    frase = "biz 125 2021 obs: comprei da dona Rosa, 2 chaves, IPVA 2026 pago"
    assert campos(frase) == {
        **BIZ,
        "modelo": "Biz 125",
        "ano_fabricacao": 2021,
        "ano_modelo": 2021,
        "observacoes": "comprei da dona Rosa, 2 chaves, IPVA 2026 pago",
    }


# ---------- Intenções ----------


@pytest.mark.parametrize(
    "frase, intencao",
    [
        *[
            (frase, "afirmacao")
            for frase in (
                "sim",
                "s",
                "confirmo",
                "confirmar",
                "pode",
                "pode cadastrar",
                "isso",
                "isso mesmo",
                "ok",
                "certo",
                "ta certo",
                "tá certo",
                "fechou",
                "cadastra",
                "manda ver",
                "bora",
                "Sim!",
                "pode sim",
            )
        ],
        *[(frase, "negacao") for frase in ("não", "nao", "errado", "espera", "n")],
        *[
            (frase, "cancelar")
            for frase in (
                "cancela",
                "cancelar",
                "esquece",
                "deixa pra la",
                "deixa pra lá",
                "desisto",
                "recomeçar",
                "apaga tudo",
                "limpar",
                "pode cancelar",
            )
        ],
        *[
            (frase, "ajuda")
            for frase in (
                "oi",
                "olá",
                "bom dia",
                "ajuda",
                "como funciona",
                "o que voce faz",
                "como funciona?",
                "cadastrar veiculo",
            )
        ],
        *[
            (frase, "fora_escopo")
            for frase in (
                "quantas motos vendemos em outubro?",
                "qual o lucro do mês?",
                "vendi a cg 160 pro joão por 14 mil",
                "me mostra o estoque",
                "tem moto à venda?",
                "quanto custa uma biz?",
                "relatório de comissões",
            )
        ],
        *[(frase, "agradecimento") for frase in ("obrigado", "valeu", "muito obrigada")],
        *[(frase, "nada") for frase in ("asdfgh", "kkkk", "?", "...", "👍", "123", "km")],
    ],
)
def test_intencao(frase, intencao):
    lido = ler(frase)
    assert lido.intencao == intencao
    assert lido.campos == {} and lido.remover == []


def test_pedido_de_venda_e_marcado_para_a_resposta_certa():
    assert ler("vendi a cg 160 pro joão por 14 mil").venda is True
    assert ler("quantas motos vendemos em outubro?").venda is False


def test_saudacao_com_dados_e_cadastro():
    assert ler("oi, chegou uma biz 125 2021").intencao == "cadastro"
    assert ler("sim, mas a cor é preta").intencao == "cadastro"
    assert ler("não, a placa é ABC1D24").intencao == "cadastro"


# ---------- Resposta à pergunta que foi feita ----------


@pytest.mark.parametrize(
    "aguardando, frase, esperado",
    [
        ("valor_compra", "11500", {"valor_compra": "11500.00"}),
        ("valor_compra", "11,5 mil", {"valor_compra": "11500.00"}),
        ("valor_compra", "onze e quinhentos", {"valor_compra": "11500.00"}),
        ("valor_compra", "foi uns 9 mil", {"valor_compra": "9000.00"}),
        ("valor_compra", "R$ 11.500,00", {"valor_compra": "11500.00"}),
        ("valor_compra", "2021", {"valor_compra": "2021.00"}),  # aqui não é ano
        ("valor_compra", "vendo por 14 mil", {"preco_venda": "14000.00"}),
        ("preco_venda", "14.900", {"preco_venda": "14900.00"}),
        ("km", "18500", {"km": 18500}),
        ("km", "zero", {"km": 0}),
        ("marca", "Honda Biz 125", veiculo("moto", "Honda", "Biz 125")),
        ("marca", "biz 125", veiculo("moto", "Honda", "Biz 125")),
        ("marca", "Zontes Tactic 400", {"marca": "Zontes", "modelo": "Tactic 400"}),
        ("marca", "é uma comet 250 da kasinski", veiculo("moto", "Kasinski", "Comet 250")),
        ("marca", "Zontes", {"marca": "Zontes"}),
        ("modelo", "CG 160 Fan", veiculo("moto", "Honda", "CG 160 Fan")),
        ("modelo", "Tactic 400", {"modelo": "Tactic 400"}),
        ("modelo", "civic lxr", veiculo("carro", "Honda", "Civic LXR")),
        ("tipo", "moto", {"tipo": "moto"}),
        ("tipo", "é carro", {"tipo": "carro"}),
        ("cor", "abóbora", {"cor": "Abóbora"}),
        ("placa", "abc 1234", {"placa": "ABC1234"}),
        ("chassi", "9C2KC2200NR12345", {"chassi": "9C2KC2200NR12345"}),
    ],
)
def test_resposta_curta_no_contexto(aguardando, frase, esperado):
    assert campos(frase, aguardando) == esperado
    assert ler(frase, aguardando).soltos == []


def test_resposta_curta_fora_do_contexto_nao_vale():
    assert ler("11500").campos == {}
    assert ler("zero").campos == {}
    assert ler("Zontes").campos == {}


def test_valor_baixo_demais_na_resposta_curta():
    lido = ler("9", "valor_compra")
    assert lido.campos == {} and "9 mil" in lido.erros[0]


# ---------- Robustez ----------


@pytest.mark.parametrize(
    "frase",
    [
        "",
        "   ",
        "R$",
        "mil",
        "e",
        "/",
        "r$ r$ r$",
        "1/2/3/4",
        "placa",
        "chassi",
        "ano",
        "km km km",
        "§§§",
        "moto " * 150,
        "9" * 400,
        "11.500.00,00.1",
        "a" * 1000,
        "biz\n125\t2021\r\nbranca",
        "ＢＩＺ １２５",
        "😀🏍️ biz 125 🚗",
    ],
)
def test_nunca_quebra(frase):
    for aguardando in (None, "valor_compra", "marca", "modelo", "placa", "chassi", "confirmacao"):
        ler(frase, aguardando)
