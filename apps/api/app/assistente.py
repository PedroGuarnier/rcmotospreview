"""Assistente de cadastro de veículo por mensagem (motor de regras, sem IA).

Duas camadas:

- `interpretar(mensagem, aguardando)`: função pura, sem banco, que transforma a frase em
  campos do veículo. É a única parte que um modelo de linguagem substituiria no futuro:
  basta devolver a mesma `Interpretacao`.
- `conversar(db, usuario, mensagem, estado)`: junta o que foi entendido ao rascunho, decide
  o que perguntar, pede confirmação e cria o veículo pelo mesmo caminho do formulário
  (`criar_veiculo`), com as mesmas regras e o mesmo audit log.

Não há estado no servidor: o cliente devolve o `estado` a cada mensagem e tudo é
revalidado com `schemas.VeiculoCriar` antes de gravar.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas, validacao
from app.models import Situacao, TipoVeiculo, Usuario, Veiculo
from app.permissoes import P, pode
from app.rotas.veiculos import criar_veiculo
from app.servicos import aliquota_imposto, calcular_imposto
from app.tempo import hoje

EXEMPLO = (
    "Honda CG 160 Fan 2022 vermelha, placa ABC1D23, 18.500 km, "
    "comprei por 11.500 e vou vender por 14.900"
)
EXEMPLO_CURTO = "chegou uma Biz 125 2021 branca, 22 mil km, comprei por 9 mil"

ANO_MINIMO = 1950
CENTAVO = Decimal("0.01")

# ---------------------------------------------------------------------------------------
# Vocabulário
# ---------------------------------------------------------------------------------------

# tipo, marca, modelos separados por vírgula. Marcas no fim do nome:
#   "#"  só vale seguido de cilindrada ou logo depois da marca (Fazer 250, Yamaha Fazer);
#   "@"  só vale logo depois da marca (Fiat Tipo, Peugeot 208, Volkswagen Bora);
#   "="  separa outras grafias (HR-V=HRV).
_CATALOGO: tuple[tuple[str, str, str], ...] = (
    (
        "moto",
        "Honda",
        "CG, Biz, Pop, NXR, XRE, CB, CBR, CBX, PCX, ADV, CRF, Twister, Hornet, Falcon, Sahara, "
        "Africa Twin, Transalp, Elite#, Lead#, Dream#, Shadow#, Tornado#, XR#, NX#, NC#, SH#, XL#, "
        "XLR#",
    ),
    (
        "moto",
        "Yamaha",
        "Factor, Crosser, Lander, NMax, XMax, XTZ, YBR, MT-03, MT-07, MT-09, Neo, Fluo, "
        "Ténéré=Tenere, XJ6, R3, R15, R1, Crypton, FZ25, FZ15, Virago, Drag Star, Fazer#, MT#, "
        "XT#, FZ#, YS#, TT-R=TTR",
    ),
    (
        "moto",
        "Suzuki",
        "Intruder, Burgman, GSR, GSX, V-Strom=VStrom, Bandit, Hayabusa, Katana, Boulevard, "
        "Yes#, EN#",
    ),
    (
        "moto",
        "Shineray",
        "Phoenix, Jef, Jet#, Worker#, Urban#, Storm#, Denver#, XY#, SHI#, Rio@, Free@, Flash@",
    ),
    ("moto", "Haojue", "Chopper Road, Lindy, Master Ride, DK#, DR#, NK#, DL#"),
    (
        "moto",
        "Dafra",
        "Apache, Riva, Citycom, Zig, Kansas, Horizon, Cruisym, Maxsym, Speed#, Next#, Laser#, "
        "NH#, Super@, Smart@",
    ),
    ("moto", "Avelloz", "AZ1, AZ#"),
    (
        "moto",
        "Kawasaki",
        "Ninja, Versys, Vulcan, Z300, Z400, Z650, Z750, Z800, Z900, Z1000, ER-6N=ER6N, KLX#",
    ),
    ("moto", "Kasinski", "Comet, Mirage, Win#, Seta#, Prima#, CRZ#"),
    ("moto", "Sundown", "Web#, Hunter#, Future#, STX#, Max@"),
    ("moto", "Traxx", "Star#, Sky#, Fly#, JL#"),
    ("moto", "Mottu", "Sport@"),
    ("moto", "Bajaj", "Dominar#, Pulsar#"),
    ("moto", "KTM", "Duke"),
    ("moto", "Triumph", "Tiger, Street Triple, Speed Triple, Bonneville, Trident, Scrambler@"),
    ("moto", "Royal Enfield", "Himalayan, Interceptor, Meteor#, Scram#, Classic@, Hunter@"),
    ("moto", "Harley-Davidson", "Sportster, Fat Boy, Softail, Road King, Street Glide, Iron@"),
    ("moto", "Ducati", "Multistrada, Panigale, Diavel, Monster#, Scrambler@"),
    ("moto", "BMW", "G 310=G310@, F 800=F800@, F 850=F850@, R 1200=R1200@, R 1250=R1250@, GS@"),
    ("moto", "Voltz", "EV1, EVS"),
    (
        "carro",
        "Fiat",
        "Uno, Palio, Strada, Mobi, Argo, Siena, Grand Siena, Toro, Cronos, Punto, Idea, "
        "Doblò=Doblo, Fiorino, Linea, Pulse, Fastback, Tempra, Stilo, Marea, Ducato, Bravo#, "
        "Brava@, Premio@, Elba@, Tipo@, 500@",
    ),
    (
        "carro",
        "Volkswagen",
        "Gol, Fox, Polo, Saveiro, Voyage, Golf, Jetta, Virtus, Nivus, T-Cross=TCross, Amarok, "
        "Kombi, Fusca, Parati, Passat, Tiguan, CrossFox=Cross Fox, SpaceFox=Space Fox, Taos, "
        "Logus, Up@, Bora@, Santana@",
    ),
    (
        "carro",
        "Chevrolet",
        "Onix, Celta, Corsa, Prisma, S10, Cruze, Cobalt, Spin, Tracker, Montana, Agile, Astra, "
        "Vectra, Meriva, Zafira, Captiva, Equinox, Trailblazer, Blazer, Kadett, Monza, Chevette, "
        "Opala, Omega, D20, Classic@, Joy@, Ipanema@",
    ),
    (
        "carro",
        "Ford",
        "Ka, Fiesta, Ranger, EcoSport=Eco Sport, Focus, Fusion, Escort, Courier, Edge, "
        "Territory, Bronco, Maverick, F-250=F250, F-1000=F1000, Pampa, Del Rey, Verona@",
    ),
    (
        "carro",
        "Hyundai",
        "HB20, HB20S, HB20X, Creta, Tucson, ix35, i30, Azera, Elantra, Santa Fe, Veloster, "
        "Sonata, HR@",
    ),
    (
        "carro",
        "Renault",
        "Kwid, Sandero, Logan, Duster, Clio, Captur, Oroch, Mégane=Megane, Scénic=Scenic, "
        "Fluence, Symbol, Kangoo, Kardian, Master@",
    ),
    (
        "carro",
        "Toyota",
        "Corolla, Corolla Cross, Hilux, Etios, Yaris, SW4, RAV4, Camry, Prius, Bandeirante, "
        "Fielder",
    ),
    ("carro", "Honda", "Civic, Fit, City, HR-V=HRV, CR-V=CRV, WR-V=WRV, ZR-V=ZRV, Accord"),
    ("carro", "Jeep", "Renegade, Compass, Commander, Wrangler, Cherokee, Grand Cherokee"),
    ("carro", "Nissan", "March, Versa, Kicks, Sentra, Frontier, Tiida, Livina"),
    ("carro", "Peugeot", "Partner, Hoggar, 206@, 207@, 208@, 2008@, 3008@, 307@, 308@, 408@"),
    ("carro", "Citroën", "C3, C4, C4 Cactus, C3 Aircross, Aircross, Picasso, Xsara, Berlingo"),
    ("carro", "Mitsubishi", "L200, Pajero, ASX, Outlander, Lancer, Eclipse Cross, Triton"),
    ("carro", "Kia", "Picanto, Cerato, Sportage, Sorento, Soul, Bongo, Rio@"),
    ("carro", "Chery", "QQ, Tiggo, Arrizo, Celer"),
    ("carro", "JAC", "J2, J3, J5, J6, T40, T50"),
    ("carro", "BYD", "Dolphin, Dolphin Mini, Song@, Yuan@, Seal@, King@"),
    ("carro", "Mercedes-Benz", "Classe A, Classe C, C180, C200, A200, GLA, Sprinter"),
    ("carro", "Audi", "A3, A4, A5, Q3, Q5"),
    ("carro", "BMW", "320i, 118i, 120i, 328i, X1, X3, X5, X6"),
    ("carro", "Volvo", "XC40, XC60, XC90"),
    ("carro", "Land Rover", "Evoque, Discovery, Freelander, Defender"),
    ("carro", "Suzuki", "Vitara, Grand Vitara, Jimny, Swift"),
    ("carro", "Subaru", "Forester, Impreza"),
    ("carro", "Dodge", "Journey, Dakota"),
    ("carro", "RAM", "Rampage"),
    ("carro", "Troller", "T4"),
    ("carro", "Mini", "Cooper"),
)

# Outras grafias de marca que aparecem em mensagem de celular.
_APELIDOS_MARCA = {
    "Volkswagen": "vw, volks, volkswagem, wolkswagen, wolks",
    "Chevrolet": "gm, chevy, chevrolett, chevrole",
    "Hyundai": "hiundai, hyunday, hiunday, hundai",
    "Renault": "renalt, renaut",
    "Peugeot": "peugeout, pegeout, pegeot",
    "Citroën": "citroen",
    "Mercedes-Benz": "mercedes, mercedes benz",
    "Harley-Davidson": "harley, harley davidson",
    "Mitsubishi": "mitsubish, mitsubichi",
    "Chery": "caoa chery",
    "Shineray": "shinerai, xineray",
    "Haojue": "haoju, haojue",
    "Kawasaki": "kawazaki",
    "Yamaha": "yamara, iamaha",
}

# Apelidos de família: "fan 160" é a CG 160 Fan; "bros 160" é a NXR 160 Bros.
# (família, nome, exige cilindrada)
_FAMILIAS = {
    "titan": ("CG", "Titan", False),
    "fan": ("CG", "Fan", True),
    "start": ("CG", "Start", True),
    "cargo": ("CG", "Cargo", True),
    "bros": ("NXR", "Bros", False),
}

_VERSOES_TEXTO = (
    "Fan Titan Start Cargo Bros ES ESD ESDi EX KS KSE Mix Flex FlexOne Sport CBS ABS UBS SED ED "
    "DLX Rally Adventure Trail BlueFlex Racing Limited Special Edition Twister Tornado Falcon "
    "Connected Hybrid Custom Street Evo Cross Way Vivace Attractive Fire Economy Mille Trekking "
    "Sporting Essence Drive Like Endurance Freedom Volcano Ranch Ultra Working Hard Weekend "
    "Precision HGT ELX EL LX LXS LXL EXL EXR DX Touring Si LT LTZ LS Premier RS Joy Plus Activ "
    "Advantage Maxx Spirit Life Wind Comfortline Trendline Highline Sportline Track Rallye Rock "
    "Power City Trend TSI MPI MSI TDI GTI GTS GT GL GLS GLX CL CLi SE SEL SL SV SR SRV SRX STD "
    "XEi GLi XLi XRS XS XL XLS XLT Altis Titanium Freestyle Storm Black Wildtrak Zen Intense "
    "Iconic Outsider Authentique Expression Dynamique Stepway Longitude Trailhawk Overland "
    "Sense Vision Comfort Evolution Launch Platinum Diamond Smart Style Unique Premium Prestige "
    "Exclusive Advance Sedan Hatch Turbo Diesel AT CVT CD CS CE Classic Feline Allure Griffe "
    "Active Shine Live Feel Strada Factor Crosser Lander Tenere Aircross Cactus LXR EXS SXT XLE "
    "HLX GTX ESDD EXi Locker Country Tropical Runner GS"
)
_VERSOES = {palavra.lower(): palavra for palavra in _VERSOES_TEXTO.split()}
_VERSOES.update({"automatico": "Automático", "automatica": "Automática", "aut": "Aut."})
_CABINES = {"dupla": "Cabine Dupla", "simples": "Cabine Simples", "estendida": "Cabine Estendida"}

_CILINDRADAS = {
    50, 70, 90, 100, 110, 115, 120, 125, 135, 150, 155, 160, 180, 190, 200, 220, 225, 230, 250,
    300, 310, 350, 390, 400, 420, 450, 500, 550, 600, 650, 660, 690, 700, 750, 765, 790, 800,
    850, 883, 890, 900, 990, 1000, 1050, 1100, 1200, 1250, 1290, 1300, 1600, 1800,
}  # fmt: skip

_TIPOS = {
    "moto": TipoVeiculo.moto,
    "motocicleta": TipoVeiculo.moto,
    "motoca": TipoVeiculo.moto,
    "motinha": TipoVeiculo.moto,
    "motoneta": TipoVeiculo.moto,
    "scooter": TipoVeiculo.moto,
    "carro": TipoVeiculo.carro,
    "automovel": TipoVeiculo.carro,
    "caminhonete": TipoVeiculo.carro,
    "camionete": TipoVeiculo.carro,
    "picape": TipoVeiculo.carro,
    "pickup": TipoVeiculo.carro,
    "suv": TipoVeiculo.carro,
}

_CORES = {
    "vermelho": "Vermelho",
    "vermelha": "Vermelha",
    "preto": "Preto",
    "preta": "Preta",
    "branco": "Branco",
    "branca": "Branca",
    "prata": "Prata",
    "prateado": "Prateado",
    "prateada": "Prateada",
    "cinza": "Cinza",
    "azul": "Azul",
    "verde": "Verde",
    "amarelo": "Amarelo",
    "amarela": "Amarela",
    "dourado": "Dourado",
    "dourada": "Dourada",
    "vinho": "Vinho",
    "laranja": "Laranja",
    "marrom": "Marrom",
    "bege": "Bege",
    "grafite": "Grafite",
    "chumbo": "Chumbo",
    "rosa": "Rosa",
    "roxo": "Roxo",
    "roxa": "Roxa",
    "lilas": "Lilás",
    "bordo": "Bordô",
    "creme": "Creme",
    "champagne": "Champagne",
    "champanhe": "Champanhe",
    "turquesa": "Turquesa",
}
_TONS = {
    "escuro": "escuro",
    "escura": "escura",
    "claro": "claro",
    "clara": "clara",
    "metalico": "metálico",
    "metalica": "metálica",
    "perolizado": "perolizado",
    "perolizada": "perolizada",
    "perola": "pérola",
    "fosco": "fosco",
    "fosca": "fosca",
    "marinho": "marinho",
    "musgo": "musgo",
    "chumbo": "chumbo",
    "grafite": "grafite",
    "celeste": "celeste",
    "royal": "royal",
    "bebe": "bebê",
    "neon": "neon",
    "limao": "limão",
    "militar": "militar",
    "petroleo": "petróleo",
    "cereja": "cereja",
    "solido": "sólido",
    "solida": "sólida",
}
# Palavra antes da cor que mostra que ela não é a cor do veículo ("dona Rosa", "placa preta").
_ANTES_NAO_E_COR = {
    "dona", "seu", "sr", "sra", "senhor", "senhora", "dr", "dra", "placa", "sinal", "semaforo",
    "laudo", "farol", "procedencia", "faixa", "tarja",
}  # fmt: skip

# Palavra antes de um ano que mostra que ele não é o ano do veículo.
_ANTES_NAO_E_ANO = {
    "ipva", "licenciamento", "licenciado", "licenciada", "dpvat", "crlv", "documento", "doc",
    "exercicio", "multa", "multas", "seguro", "em", "desde", "ate",
}  # fmt: skip

_UNIDADES_KM = {
    "km", "kms", "quilometro", "quilometros", "kilometro", "kilometros", "rodado", "rodados",
    "rodada", "rodadas",
}  # fmt: skip
_ROTULOS_KM = {
    "km", "kms", "quilometragem", "kilometragem", "hodometro", "odometro", "rodou", "andou",
    "rodagem",
}  # fmt: skip

_COMPRA, _VENDA = "valor_compra", "preco_venda"
# Expressões que dizem de que valor se trata. As mais longas são testadas primeiro.
_FRASES_VALOR: tuple[tuple[str, str], ...] = tuple(
    sorted(
        [
            ("valor de compra", _COMPRA),
            ("valor da compra", _COMPRA),
            ("preco de compra", _COMPRA),
            ("preco da compra", _COMPRA),
            ("custo de compra", _COMPRA),
            ("valor pago", _COMPRA),
            ("entrada na loja", _COMPRA),
            ("entrou na loja", _COMPRA),
            ("comprei", _COMPRA),
            ("comprado", _COMPRA),
            ("comprada", _COMPRA),
            ("compramos", _COMPRA),
            ("comprou", _COMPRA),
            ("compra", _COMPRA),
            ("paguei", _COMPRA),
            ("pagamos", _COMPRA),
            ("pagou", _COMPRA),
            ("custou", _COMPRA),
            ("custo", _COMPRA),
            ("peguei", _COMPRA),
            ("pegamos", _COMPRA),
            ("pegou", _COMPRA),
            ("adquiri", _COMPRA),
            ("adquirido", _COMPRA),
            ("adquirida", _COMPRA),
            ("dei", _COMPRA),
            ("investi", _COMPRA),
            ("entrou", _COMPRA),
            ("valor de venda", _VENDA),
            ("valor da venda", _VENDA),
            ("preco de venda", _VENDA),
            ("preco da venda", _VENDA),
            ("por quanto sai", _VENDA),
            ("sai por", _VENDA),
            ("saindo por", _VENDA),
            ("vender", _VENDA),
            ("vendo", _VENDA),
            ("vende", _VENDA),
            ("vendendo", _VENDA),
            ("venda", _VENDA),
            ("revender", _VENDA),
            ("revenda", _VENDA),
            ("anunciar", _VENDA),
            ("anuncia", _VENDA),
            ("anuncio", _VENDA),
            ("anunciando", _VENDA),
            ("anunciado", _VENDA),
            ("anunciada", _VENDA),
            ("preco", _VENDA),
            ("pedindo", _VENDA),
            ("peco", _VENDA),
            ("pedir", _VENDA),
        ],
        key=lambda item: -len(item[0].split()),
    )
)
# Palavrinhas que podem ficar entre o rótulo e o número ("comprei por R$ 11.500").
_LIGACOES = {
    "por", "de", "a", "foi", "e", "eh", ":", "=", "-", "uns", "so", "apenas", "na", "no",
    "o", "ela", "ele", "nela", "nele", "nessa", "nesse", "valor", "total", "agora", "ficou",
    "fica", "sera", "vai", "ser", "pra", "para", "esta", "ta", "com", "sao", "atual", "tem",
    "ficar", "muda", "mudar", "trocar", "troca", "certo", "correto", "novo", "nova", "errado",
    "errada",
}  # fmt: skip
_DEPOIS_DO_VALOR = {"de", "da", "na", "no", "a", "o", "foi", "pra", "para", "e", "eh"}
_MOEDA_DEPOIS = {"reais", "real", "conto", "contos", "pila", "pilas"}

_UNIDADES = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "quatorze": 14, "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17,
    "dezoito": 18, "dezenove": 19,
}  # fmt: skip
_DEZENAS = {
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70,
    "oitenta": 80, "noventa": 90,
}  # fmt: skip
_CENTENAS = {
    "cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300, "quatrocentos": 400,
    "quinhentos": 500, "seiscentos": 600, "setecentos": 700, "oitocentos": 800,
    "novecentos": 900,
}  # fmt: skip

# "onze e quinhentos", "onze e meio": jeito falado de dizer 11.500
_DEPOIS_DO_E = {**_CENTENAS, "meio": 500}

# Palavras comuns que nunca são marca nem modelo (para marca/modelo fora do catálogo).
_COMUNS = set(
    "a o as os um uma uns umas de do da dos das e ou em no na nos nas por pra para pro com sem "
    "que se eu ele ela me meu minha ja nao sim foi eh esta ta tem ter era ser vai vou novo nova "
    "usado usada seminovo seminova top linda lindo boa bom bem muito muita mais menos so tambem "
    "ano cor placa km chassi renavam preco valor compra venda modelo marca tipo cadastra "
    "cadastrar cadastre cadastro chegou hoje ontem agora aqui la loja cliente veiculo documento "
    "doc ok obs zero mil reais unico unica dono dona estado conservada conservado revisada "
    "revisado completo completa original financiado financiada quitado quitada essa esse este "
    "isso aquela aquele outra outro tudo nada demais show bonita bonito barato barata cara caro "
    "adiciona adicionar registra registrar inclui incluir lanca lancar bota coloca poe quero "
    "preciso favor oi ola verdade ainda nunca sempre aquilo dela dele".split()
)

_CAMPOS_REMOVIVEIS = {
    "placa": ("placa",),
    "chassi": ("chassi",),
    "renavam": ("renavam",),
    "cor": ("cor",),
    "km": ("km",),
    "quilometragem": ("km",),
    "ano": ("ano_fabricacao", "ano_modelo"),
    "ano de fabricacao": ("ano_fabricacao",),
    "ano modelo": ("ano_modelo",),
    "ano do modelo": ("ano_modelo",),
    "ano de modelo": ("ano_modelo",),
    "preco": ("preco_venda",),
    "preco de venda": ("preco_venda",),
    "valor de venda": ("preco_venda",),
    "valor de compra": ("valor_compra",),
    "observacao": ("observacoes",),
    "observacoes": ("observacoes",),
    "obs": ("observacoes",),
    "marca": ("marca",),
    "modelo": ("modelo",),
}
_REMOVER = re.compile(
    r"\b(?:sem|tirar?|tire|remover?|remova|apagar?|apague|retirar?|retire|excluir?|exclua|"
    r"limpar?|limpe|(?:ainda )?nao tem|nao possui|deixa sem)\s+"
    r"(?:o |a |os |as |esse |essa |este |esta )?(?:campo |dado )?(?:d[aeo] )?"
    r"(ano d[eo] modelo|ano de fabricacao|ano modelo|preco de venda|valor de venda|"
    r"valor de compra|placa|chassi|renavam|cor|km|quilometragem|ano|preco|observacoes|"
    r"observacao|obs|marca|modelo)\b"
)
_OBSERVACAO = re.compile(r"\b(?:obs|observacao|observacoes)\b\s*[:=\-]?\s*(\S.*)$", re.DOTALL)
_CHASSI_ROTULO = re.compile(
    r"\bchassis?\b(?:\s+(?:e|eh|numero|n|no))?\s*[:=]?\s*([a-z0-9]*\d[a-z0-9]*)"
)
_CHASSI_SOLTO = re.compile(r"\b(?=[a-z0-9]*[a-z])(?=[a-z0-9]*\d)[a-hj-npr-z0-9]{17}\b")
_RENAVAM_ROTULO = re.compile(r"\brenavam\b(?:\s+(?:e|eh|numero|n|no))?\s*[:=]?\s*(\d[\d.\-]*)")
_PLACA_ROTULO = re.compile(
    r"\bplacas?\b(?:\s+(?:nova|certa|correta|atual|agora|e|eh|para|pra|por))*\s*[:=\-]?\s*"
    r"([a-z0-9]+(?:[\- ]\d[a-z0-9]\d{2}\b)?)"
)
_DATA = re.compile(r"\b\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})\b")
_PLACA_SOLTA = re.compile(r"\b([a-z]{3})-?(\d[a-z0-9]\d{2})\b")
_PLACA_MERCOSUL_ESPACO = re.compile(r"\b([a-z]{3}) (\d[a-z]\d{2})\b")

_A_VENDA = (
    re.compile(
        r"\bpode (?:ja )?(?:ir |por |colocar |botar |subir |entrar )?"
        r"(?:pra|para|pro|na|a|no) (?:a )?(?:vitrine|venda|site|anuncio)\b"
    ),
    re.compile(r"\bpode (?:ja )?anunciar\b"),
    re.compile(
        r"\b(?:esta|ta|fica|ficou|vai|entra|coloca|colocar|bota|botar|poe|deixa|deixar) "
        r"(?:ja )?(?:a|na|pra|para) (?:venda|vitrine)\b"
    ),
    re.compile(r"\bja (?:a venda|na vitrine|anunciad[oa])\b"),
    re.compile(r"\bpront[oa] (?:pra|para) (?:a )?(?:venda|vender|anunciar|vitrine)\b"),
    re.compile(r"\bsituacao\s*[:=]?\s*(?:e |eh )?a venda\b"),
)
_OUTRAS_SITUACOES = re.compile(
    r"\b(?:em|na|esta em|ta em|vai pra|vai para|situacao\s*[:=]?(?: e| eh)?) "
    r"(preparacao|documentacao|oficina)\b"
)

_CANCELAR = re.compile(
    r"(?:nao |ah |entao |pode |quero |vamos |por favor )*"
    r"(?:cancelar?|cancele|esquece|esqueca|deixa (?:pra|para) la|deixa quieto|desisto|"
    r"desisti|recomecar|recomeca|recomece|comecar de novo|comeca de novo|apagar? tudo|"
    r"limpar?(?: tudo)?|zerar?(?: tudo)?)"
    r"(?: tudo| isso| ai| esse cadastro| o cadastro| o rascunho| por favor| de novo| do zero)*"
)
_SIM_NUCLEO = {
    "sim", "s", "ss", "confirmo", "confirmar", "confirma", "confirmado", "pode", "cadastrar",
    "cadastra", "cadastre", "isso", "ok", "okay", "certo", "certinho", "fechou", "fechado",
    "bora", "simbora", "beleza", "blz", "show", "perfeito", "correto", "exato", "salvar",
    "salva", "claro", "positivo", "joia", "otimo", "manda", "uhum", "aham", "yes",
}  # fmt: skip
_SIM_ENFEITE = {
    "mesmo", "ta", "esta", "tudo", "ver", "ai", "assim", "ser", "bom", "e", "eh", "por",
    "favor", "pf", "pfv", "obrigado", "obrigada", "obg", "vamos", "agora", "ja", "la", "vai",
    "a", "o", "moto", "carro", "veiculo", "ela", "ele", "tambem", "entao", "pra", "mim",
}  # fmt: skip
_NAO_NUCLEO = {
    "nao", "n", "nn", "nops", "nope", "errado", "errada", "espera", "espere", "pera", "perai",
    "calma", "incorreto", "negativo", "ops", "segura", "aguarda", "aguarde",
}  # fmt: skip
_NAO_ENFEITE = {
    "ainda", "tem", "erro", "ta", "esta", "nada", "disso", "pode", "opa", "um", "momento",
    "minuto", "ai", "e", "eh", "isso", "assim", "certo", "pouco",
}  # fmt: skip
_SAUDACAO = re.compile(
    r"(?:oi+e?|ola+|opa|e ai|eae|salve|hey|hello|bom dia|boa tarde|boa noite|tudo bem|"
    r"tudo bom|blz|beleza)(?: (?:tudo bem|tudo bom|blz|beleza|pessoal|assistente|robo))*"
)
_AJUDA = re.compile(
    r"\b(?:ajuda|ajudar|ajude|help|socorro|como funciona|como (?:eu )?(?:uso|usar|faco|fazer)|"
    r"o que (?:voce|vc|tu) (?:faz|sabe|pode)|(?:pra|para) que (?:voce |vc )?serve|exemplos?|"
    r"instrucoes|como (?:eu )?cadastr\w+|quero cadastrar|cadastrar (?:um |uma )?"
    r"(?:veiculo|moto|carro)|nov[oa] (?:veiculo|moto|carro|cadastro)|cadastrar outr[oa])\b"
)
_OBRIGADO = re.compile(
    r"(?:muito |opa |ah |ok |show |beleza )*(?:obrigad[oa]|brigad[oa]|obg|valeu|vlw|thanks|tmj)"
    r"(?: demais| mesmo| ai| viu| pela ajuda)*"
)
_FORA_FORTE = re.compile(
    r"\b(?:vendi|vendemos|vendeu|venderam|vendid[oa]s?|dar baixa|baixa de venda|"
    r"registrar? (?:a |uma )?venda|comissao|comissoes|faturamento|inadimpl\w*|parcelas?|"
    r"cobranca|boletos?|carne|relatorios?|quantas vendas|quantos vendidos)\b"
)
_VENDA_REGISTRO = re.compile(r"\b(?:vendi|dar baixa|baixa de venda|registrar? (?:a |uma )?venda)\b")
_PERGUNTA = re.compile(
    r"^(?:quant[oa]s?|qual|quais|quem|quando|onde|cade|me mostra|mostra|mostrar|mostre|"
    r"lista|listar|liste|relatorio|resumo|tem quant)\b"
)


@dataclass(frozen=True)
class _Modelo:
    nome: str
    marca: str
    tipo: TipoVeiculo
    exige: str  # "" | "#" | "@"
    colado: bool  # "s10", "c3": letra única só vale grudada no número


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acento, mantendo o tamanho (os índices valem no texto original)."""
    saida = []
    for c in texto:
        if c in "–—−":
            saida.append("-")
        elif c == "§":
            saida.append(" ")
        else:
            base = unicodedata.normalize("NFD", c)[0].lower()
            saida.append(base if len(base) == 1 else " ")
    return "".join(saida)


_PEDACO = re.compile(r"r\$|\d+(?:[.,]\d+)*|[a-z]+|[^\sa-z0-9]")


def _chave(texto: str) -> tuple[str, ...]:
    return tuple(p for p in _PEDACO.findall(_normalizar(texto)) if p != "-")


def _montar_catalogo() -> tuple[dict, dict, dict]:
    modelos: dict[tuple[str, ...], list[_Modelo]] = {}
    marcas: dict[tuple[str, ...], str] = {}
    tipos_da_marca: dict[str, set[TipoVeiculo]] = {}
    for tipo_txt, marca, lista in _CATALOGO:
        tipo = TipoVeiculo(tipo_txt)
        tipos_da_marca.setdefault(marca, set()).add(tipo)
        marcas[_chave(marca)] = marca
        for item in lista.split(","):
            item = item.strip()
            exige = item[-1] if item[-1] in "#@" else ""
            grafias = item.rstrip("#@").split("=")
            nome = grafias[0]
            for grafia in grafias:
                chave = _chave(grafia)
                colado = " " not in grafia and "-" not in grafia and len(chave[0]) == 1
                modelos.setdefault(chave, []).append(_Modelo(nome, marca, tipo, exige, colado))
    for marca, apelidos in _APELIDOS_MARCA.items():
        for apelido in apelidos.split(","):
            marcas[_chave(apelido)] = marca
    return modelos, marcas, tipos_da_marca


_MODELOS, _MARCAS, _TIPOS_DA_MARCA = _montar_catalogo()
_MAIOR_CHAVE = max(len(chave) for chave in (*_MODELOS, *_MARCAS))
# Palavras de três letras do vocabulário: "gol2014" é modelo e ano, não placa.
_PALAVRAS_DE_3 = {
    p
    for p in (
        *(parte for chave in (*_MODELOS, *_MARCAS) for parte in chave),
        *_VERSOES,
        *_FAMILIAS,
        *_CORES,
        *_COMUNS,
    )
    if len(p) == 3 and p.isalpha()
}
_PARADAS = (
    _COMUNS
    | set(_CORES)
    | set(_TIPOS)
    | _UNIDADES_KM
    | _ROTULOS_KM
    | _MOEDA_DEPOIS
    | {palavra for frase, _ in _FRASES_VALOR for palavra in frase.split()}
)


# ---------------------------------------------------------------------------------------
# Leitura da frase
# ---------------------------------------------------------------------------------------


@dataclass
class Interpretacao:
    """O que foi entendido de uma mensagem. Nada aqui toca o banco."""

    # cadastro | afirmacao | negacao | cancelar | ajuda | agradecimento | fora_escopo | nada
    intencao: str = "nada"
    campos: dict[str, Any] = field(default_factory=dict)
    remover: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)  # suposições feitas
    erros: list[str] = field(default_factory=list)  # o que veio inválido e não entrou
    # números que apareceram sem pista do que são: (valor, tem cara de dinheiro)
    soltos: list[tuple[Decimal, bool]] = field(default_factory=list)
    # pedido de registrar venda (para a resposta apontar a tela certa)
    venda: bool = False


@dataclass
class _Tok:
    t: str
    ini: int
    fim: int
    num: bool
    colado: bool  # sem espaço depois do anterior: "110i", "hb20", "18500km", "f-250"
    usado: bool = False

    @property
    def palavra(self) -> bool:
        return self.t.isalpha()


@dataclass
class _Qtd:
    valor: Decimal
    i: int  # primeiro token
    j: int  # token depois do último
    dinheiro: bool = False  # veio com R$, "reais", centavos, "mil" ou "k"
    cifrao: bool = False  # só R$, "reais" ou centavos: é dinheiro sem dúvida
    simples: bool = False  # um inteiro puro ("2022", "11500"): pode ser ano
    rotulo: str | None = None


def _tokenizar(norm: str) -> list[_Tok]:
    toks: list[_Tok] = []
    grudar = False
    for m in _PEDACO.finditer(norm):
        t, ini, fim = m.group(), m.start(), m.end()
        colado = bool(toks) and toks[-1].fim == ini
        if t == "-" and colado and fim < len(norm) and norm[fim].isalnum():
            grudar = True  # hífen de "hr-v", "f-250", "2021-2022": some e gruda as partes
            continue
        toks.append(_Tok(t, ini, fim, t[0].isdigit(), colado or grudar))
        grudar = False
    return toks


def _ler_numero(texto: str, multiplicado: bool = False) -> Decimal | None:
    """Número no jeito brasileiro: 11.500 = onze mil e quinhentos; 11,5 = onze e meio."""
    if len(texto) > 18:
        return None  # dígitos demais para ser km ou dinheiro de verdade
    if texto.isdigit():
        return Decimal(texto)
    if multiplicado and re.fullmatch(r"\d+[.,]\d{1,2}", texto):
        return Decimal(texto.replace(",", "."))  # "11,5 mil", "11.5k"
    if m := re.fullmatch(r"(\d{1,3}(?:\.\d{3})+)(?:,(\d{1,2}))?", texto):
        return Decimal(f"{m[1].replace('.', '')}.{m[2] or '0'}")  # 11.500 / 11.500,00
    if m := re.fullmatch(r"(\d+),(\d{1,2})", texto):
        return Decimal(f"{m[1]}.{m[2]}")  # 11500,00
    if m := re.fullmatch(r"(\d{1,3}(?:,\d{3})+)(?:\.(\d{1,2}))?", texto):
        return Decimal(f"{m[1].replace(',', '')}.{m[2] or '0'}")  # 11,500 (milhar com vírgula)
    if re.fullmatch(r"\d+\.\d{1,2}", texto):
        return Decimal(texto)  # 1.6 / 24000.50
    return None


def _por_extenso(toks: list[_Tok], i: int) -> tuple[int, int] | None:
    """Número até 999 escrito por extenso a partir do token i: (valor, próximo token)."""
    total, j, achou = 0, i, False

    def t(k: int) -> str:
        return toks[k].t if k < len(toks) and not toks[k].usado else ""

    if t(j) in _CENTENAS:
        total, j, achou = _CENTENAS[t(j)], j + 1, True
        if t(j) == "e" and (t(j + 1) in _DEZENAS or t(j + 1) in _UNIDADES):
            j += 1
        else:
            return total, j
    if t(j) in _DEZENAS:
        total, j, achou = total + _DEZENAS[t(j)], j + 1, True
        if t(j) == "e" and t(j + 1) in _UNIDADES and 0 < _UNIDADES[t(j + 1)] < 10:
            total, j = total + _UNIDADES[t(j + 1)], j + 2
        return total, j
    if t(j) in _UNIDADES:
        return total + _UNIDADES[t(j)], j + 1
    return (total, j) if achou else None


def _quantidades(toks: list[_Tok]) -> list[_Qtd]:
    """Junta número, "mil", "k", R$ e números por extenso em quantidades."""
    qtds: list[_Qtd] = []
    n = len(toks)

    def t(k: int) -> str:
        return toks[k].t if 0 <= k < n and not toks[k].usado else ""

    def resto_do_mil(j: int) -> tuple[Decimal, int]:
        """ "11 mil e 500", "onze mil e quinhentos", "onze mil quinhentos"."""
        k = j + 1 if t(j) == "e" else j
        if k < n and toks[k].num and not toks[k].usado and toks[k].t.isdigit():
            seguinte = t(k + 1)
            if k > j and int(toks[k].t) < 1000 and seguinte not in ("mil", "k"):
                return Decimal(toks[k].t), k + 1
            return Decimal(0), j
        extenso = _por_extenso(toks, k)
        if extenso and 0 < extenso[0] < 1000 and t(extenso[1]) != "mil":
            if k > j or t(k) in _CENTENAS:
                return Decimal(extenso[0]), extenso[1]
        return Decimal(0), j

    i = 0
    while i < n:
        tok = toks[i]
        if tok.usado:
            i += 1
            continue
        inicio = i
        cifrao = tok.t in ("r$", "rs") and i + 1 < n and toks[i + 1].num and not toks[i + 1].usado
        if cifrao:
            i += 1
            tok = toks[i]
        valor: Decimal | None = None
        dinheiro = cifrao
        simples = False
        j = i
        if tok.num:
            seguinte = t(i + 1)
            if seguinte == "mil" or (seguinte == "k" and toks[i + 1].colado):
                base = _ler_numero(tok.t, multiplicado=True)
                if base is not None and base < 1000:
                    valor, j, dinheiro = base * 1000, i + 2, True
                    if seguinte == "mil":
                        extra, j = resto_do_mil(j)
                        valor += extra
            if valor is None:
                valor = _ler_numero(tok.t)
                j = i + 1
                if valor is not None:
                    falado = tok.t.isdigit() and valor < 1000 and t(j) == "e"
                    if falado and t(j + 1) in _DEPOIS_DO_E:
                        valor = valor * 1000 + _DEPOIS_DO_E[t(j + 1)]  # "11 e quinhentos"
                        j, dinheiro = j + 2, True
                    else:
                        simples = tok.t.isdigit() and not cifrao
                        if re.search(r",\d{2}$", tok.t):
                            dinheiro = cifrao = True  # centavos: "24.000,00"
                    if t(j) == "mil":  # "11.500 mil": o "mil" sobra
                        j += 1
        elif tok.palavra and not cifrao:
            extenso = _por_extenso(toks, i)
            if extenso and t(extenso[1]) == "mil" and extenso[0] > 0:
                valor, j = Decimal(extenso[0]) * 1000, extenso[1] + 1
                extra, j = resto_do_mil(j)
                valor, dinheiro = valor + extra, True
            elif extenso and 0 < extenso[0] < 100 and t(extenso[1]) == "e":
                if t(extenso[1] + 1) in _DEPOIS_DO_E:  # "onze e quinhentos"
                    valor = Decimal(extenso[0]) * 1000 + _DEPOIS_DO_E[t(extenso[1] + 1)]
                    j, dinheiro = extenso[1] + 2, True
            elif tok.t == "mil" and not (i > 0 and toks[i - 1].num):
                valor, j, dinheiro = Decimal(1000), i + 1, True
                extra, j = resto_do_mil(j)
                valor += extra
        if valor is None:
            i = inicio + 1
            continue
        if t(j) in _MOEDA_DEPOIS:
            j, dinheiro, cifrao, simples = j + 1, True, True, False
        qtds.append(_Qtd(valor, inicio, j, dinheiro=dinheiro, cifrao=cifrao, simples=simples))
        i = j
    return qtds


def _bonito(palavra: str) -> str:
    """Grafia de palavra fora do catálogo: Comet, GT, NX4, e o que veio com maiúscula no meio."""
    if any(c.isupper() for c in palavra[1:]) and any(c.islower() for c in palavra):
        return palavra
    chave = _normalizar(palavra)
    if chave in _VERSOES:
        return _VERSOES[chave]
    if any(c.isdigit() for c in palavra) or len(palavra) <= 3:
        return palavra.upper()
    return palavra.capitalize()


def _inteiro(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _moeda(valor: Decimal) -> str:
    texto = f"{valor.quantize(CENTAVO):,.2f}"
    return "R$ " + texto.replace(",", "§").replace(".", ",").replace("§", ".")


def _numero_curto(valor: Decimal) -> str:
    if valor == valor.to_integral_value():
        return _inteiro(int(valor))
    return _moeda(valor)[3:].rstrip("0").rstrip(",")


def _expandir_ano(dois_digitos: int, ano_atual: int) -> int:
    seculo = (ano_atual + 1) // 100 * 100
    return seculo + dois_digitos if dois_digitos <= (ano_atual + 1) % 100 else 1900 + dois_digitos


class _Leitor:
    """Uma passada pela mensagem. Cada etapa marca os tokens que usou."""

    def __init__(self, mensagem: str, aguardando: str | None, ano_atual: int):
        self.original = mensagem
        self.aguardando = aguardando
        self.ano_atual = ano_atual
        self.ano_maximo = ano_atual + 1
        self.r = Interpretacao()
        self.norm = _normalizar(mensagem)
        self.buf = list(self.norm)
        self.toks: list[_Tok] = []
        self.qtds: list[_Qtd] = []
        self.frases: list[list] = []  # palavras de compra e venda: [início, fim, campo, usada]
        self.fim_modelo: int | None = None  # token logo depois do modelo ("cg 160 fan 22")
        self.ano_unico: int | None = None  # um ano só, valendo para fabricação e modelo

    # ----- utilidades -----

    def texto(self) -> str:
        return "".join(self.buf)

    def apagar(self, ini: int, fim: int) -> None:
        """Tira o trecho já entendido e deixa um marco que nenhuma regra atravessa."""
        for k in range(ini, fim):
            self.buf[k] = " "
        if fim > ini:
            self.buf[ini] = "§"

    def t(self, k: int) -> str:
        return self.toks[k].t if 0 <= k < len(self.toks) and not self.toks[k].usado else ""

    def usar(self, i: int, j: int) -> None:
        for k in range(i, j):
            self.toks[k].usado = True

    def trecho(self, i: int, j: int) -> str:
        return self.original[self.toks[i].ini : self.toks[j - 1].fim]

    def ano_plausivel(self, ano: int) -> bool:
        return ANO_MINIMO <= ano <= self.ano_maximo

    # ----- etapas sobre o texto -----

    def remocoes(self) -> None:
        for m in list(_REMOVER.finditer(self.texto())):
            for campo in _CAMPOS_REMOVIVEIS[m[1]]:
                if campo not in self.r.remover:
                    self.r.remover.append(campo)
            self.apagar(m.start(), m.end())

    def observacoes(self) -> None:
        m = _OBSERVACAO.search(self.texto())
        if m:
            texto = self.original[m.start(1) :].strip()
            if texto:
                self.r.campos["observacoes"] = texto
            self.apagar(m.start(), len(self.buf))

    def datas(self) -> None:
        """Datas (10/11/2026) não são ano do veículo nem valor: ficam fora da leitura."""
        for m in list(_DATA.finditer(self.texto())):
            self.apagar(m.start(), m.end())

    def documentos(self) -> None:
        m = _CHASSI_ROTULO.search(self.texto())
        if m:
            try:
                self.r.campos["chassi"] = validacao.normalizar_chassi(m[1])
            except ValueError as erro:
                self.r.erros.append(str(erro))
            self.apagar(m.start(), m.end())
        else:
            m = _CHASSI_SOLTO.search(self.texto())
            tentativa = re.sub(r"[^a-z0-9]", "", self.texto())
            if m:
                self.r.campos["chassi"] = m[0].upper()
                self.apagar(m.start(), m.end())
            elif self.aguardando == "chassi" and any(c.isdigit() for c in tentativa):
                if 6 <= len(tentativa) <= 17:
                    self.r.campos["chassi"] = tentativa.upper()
                    self.apagar(0, len(self.buf))
        m = _RENAVAM_ROTULO.search(self.texto())
        if m:
            try:
                self.r.campos["renavam"] = validacao.normalizar_renavam(m[1])
            except ValueError as erro:
                self.r.erros.append(str(erro))
            self.apagar(m.start(), m.end())

    def placa(self) -> None:
        achadas: list[tuple[int, int, str]] = []
        texto = self.texto()
        for m in _PLACA_ROTULO.finditer(texto):
            tentativa = re.sub(r"[^a-z0-9]", "", m[1])
            if not any(c.isdigit() for c in tentativa):
                continue  # "placa de Teresina": não é uma placa escrita
            try:
                achadas.append((m.start(), m.end(), validacao.normalizar_placa(tentativa)))
            except ValueError:
                self.r.erros.append(
                    f"Não reconheci a placa “{tentativa.upper()}”. "
                    "Use o formato ABC1234 ou ABC1D23."
                )
                achadas.append((m.start(), m.end(), ""))
        for ini, fim, _ in achadas:
            self.apagar(ini, fim)
        texto = self.texto()
        for padrao in (_PLACA_SOLTA, _PLACA_MERCOSUL_ESPACO):
            for m in padrao.finditer(texto):
                letras, resto = m[1], m[2]
                if resto.isdigit() and letras in _PALAVRAS_DE_3 and self.ano_plausivel(int(resto)):
                    continue  # "gol2014", "fan2022"
                achadas.append((m.start(), m.end(), (letras + resto).upper()))
        validas = sorted((a for a in achadas if a[2]), key=lambda a: a[0])
        for ini, fim, _ in validas:
            self.apagar(ini, fim)
        if validas:
            self.r.campos["placa"] = validas[-1][2]  # a última informação vale
        elif self.aguardando == "placa" and not achadas:
            tentativa = re.sub(r"[^a-z0-9]", "", texto)
            if 5 <= len(tentativa) <= 8 and any(c.isdigit() for c in tentativa):
                try:
                    self.r.campos["placa"] = validacao.normalizar_placa(tentativa)
                    self.apagar(0, len(self.buf))
                except ValueError as erro:
                    self.r.erros.append(str(erro))

    def situacao(self) -> None:
        texto = self.texto()
        achado: tuple[int, Situacao] | None = None
        for padrao in _A_VENDA:
            for m in padrao.finditer(texto):
                if achado is None or m.start() >= achado[0]:
                    achado = (m.start(), Situacao.a_venda)
        # "à venda" com crase é situação mesmo sem verbo antes
        for m in re.finditer(r"\ba venda\b", texto):
            if self.original[m.start()] in "àÀ" and (achado is None or m.start() >= achado[0]):
                achado = (m.start(), Situacao.a_venda)
        for m in _OUTRAS_SITUACOES.finditer(texto):
            if achado is None or m.start() >= achado[0]:
                destino = Situacao.documentacao if m[1] == "documentacao" else Situacao.preparacao
                achado = (m.start(), destino)
        if achado is None:
            return
        antes = texto[max(0, achado[0] - 22) : achado[0]]
        negado = re.search(r"\b(?:nao|nem)\b[^.,;!?§]*$", antes) is not None
        self.r.campos["situacao"] = Situacao.compra if negado else achado[1]

    # ----- etapas sobre os tokens -----

    def _marca_em(self, i: int) -> tuple[str, int] | None:
        for tamanho in range(min(_MAIOR_CHAVE, len(self.toks) - i), 0, -1):
            chave = tuple(self.t(k) for k in range(i, i + tamanho))
            if chave in _MARCAS:
                return _MARCAS[chave], tamanho
        return None

    def _eh_versao_num(self, j: int) -> bool:
        tok = self.toks[j]
        if not tok.num or tok.usado:
            return False
        seguinte = self.t(j + 1)
        if seguinte in ("mil", "reais") or seguinte in _UNIDADES_KM:
            return False
        if seguinte == "k" and self.toks[j + 1].colado:
            return False
        if re.fullmatch(r"\d[.,]\d", tok.t):
            return Decimal("0.6") <= Decimal(tok.t.replace(",", ".")) <= Decimal("7.0")
        return tok.t.isdigit() and int(tok.t) in _CILINDRADAS

    def _ler_versao_num(self, j: int) -> tuple[str, int]:
        texto = self.toks[j].t.replace(",", ".")
        k = j + 1
        if k < len(self.toks) and self.toks[k].colado and not self.toks[k].usado:
            sufixo = self.toks[k].t
            if sufixo in ("cc", "cilindradas"):
                return texto, k + 1
            if len(sufixo) == 1 and sufixo.isalpha() and sufixo != "k":
                return texto + (sufixo if sufixo == "i" else sufixo.upper()), k + 1
        if self.t(k) in ("cc", "cilindradas"):
            return texto, k + 1
        return texto, k

    def _versoes(self, j: int, tem_cilindrada: bool = False) -> tuple[list[str], int]:
        """Versão e motor depois do modelo: "160 Fan", "1.0", "Way", "16V", "4x4".

        Só uma cilindrada e um motor por modelo: em "titan 150 800" o 800 já é outra coisa.
        """
        partes: list[str] = []
        n = len(self.toks)
        vistos = {"inteiro": tem_cilindrada, "decimal": False}
        while j < n and len(partes) < 7:
            tok = self.toks[j]
            if tok.usado:
                break
            if tok.num:
                especie = "inteiro" if tok.t.isdigit() else "decimal"
                if self._eh_versao_num(j) and not vistos[especie]:
                    vistos[especie] = True
                    texto, j = self._ler_versao_num(j)
                    if texto.isdigit() and self.t(j) in ("z", "s", "x", "r", "f", "l"):
                        texto, j = f"{texto} {self.t(j).upper()}", j + 1
                    partes.append(texto)
                    continue
                grudado = j + 1 < n and self.toks[j + 1].colado
                if tok.t in ("8", "12", "16", "20", "24") and grudado and self.t(j + 1) == "v":
                    partes.append(f"{tok.t}V")
                    j += 2
                    continue
                if tok.t == "4" and grudado and self.t(j + 1) == "x" and self.t(j + 2) in "24":
                    if self.t(j + 2) and self.toks[j + 2].colado:
                        partes.append(f"4x{self.t(j + 2)}")
                        j += 3
                        continue
                break
            if tok.t in _VERSOES:
                partes.append(_VERSOES[tok.t])
                j += 1
                continue
            if tok.t == "cabine" and self.t(j + 1) in _CABINES:
                partes.append(_CABINES[self.t(j + 1)])
                j += 2
                continue
            if (  # "g5", "g6": letra e número grudados
                tok.palavra
                and len(tok.t) <= 2
                and tok.t not in _PARADAS
                and j + 1 < n
                and self.toks[j + 1].num
                and self.toks[j + 1].colado
                and self.toks[j + 1].t.isdigit()
                and len(self.toks[j + 1].t) <= 2
                and not self.toks[j + 1].usado
            ):
                partes.append((tok.t + self.toks[j + 1].t).upper())
                j += 2
                continue
            break
        return partes, j

    def _modelo_em(self, i: int, marca_antes: str | None) -> tuple[str, _Modelo, int] | None:
        """Modelo do catálogo começando no token i: (nome completo, entrada, próximo token)."""
        n = len(self.toks)
        primeiro = self.t(i)
        if primeiro in _FAMILIAS:
            familia, nome, exige_numero = _FAMILIAS[primeiro]
            entrada = _Modelo(familia, "Honda", TipoVeiculo.moto, "", False)
            if i + 1 < n and self._eh_versao_num(i + 1):
                numero, j = self._ler_versao_num(i + 1)
                versoes, j = self._versoes(j, tem_cilindrada=True)
                return " ".join([familia, numero, nome, *versoes]), entrada, j
            if not exige_numero:
                return f"{familia} {nome}", entrada, i + 1
            return None
        for tamanho in range(min(_MAIOR_CHAVE, n - i), 0, -1):
            chave = tuple(self.t(k) for k in range(i, i + tamanho))
            candidatos = _MODELOS.get(chave)
            if not candidatos:
                continue
            j = i + tamanho
            validos = []
            for c in candidatos:
                if c.colado and not all(self.toks[k].colado for k in range(i + 1, j)):
                    continue
                if c.exige == "@" and marca_antes != c.marca:
                    continue
                if c.exige == "#" and marca_antes != c.marca:
                    if not (j < n and self._eh_versao_num(j)):
                        continue
                validos.append(c)
            if not validos:
                continue
            escolhido = next((c for c in validos if c.marca == marca_antes), validos[0])
            versoes, j = self._versoes(j)
            return " ".join([escolhido.nome, *versoes]), escolhido, j
        return None

    def _modelo_livre(self, i: int, limite: int = 3) -> tuple[str, int]:
        """Modelo fora do catálogo: até três palavras e a cilindrada ("Comet GT 250")."""
        partes: list[str] = []
        j, n = i, len(self.toks)
        while j < n and len(partes) < limite + 1:
            tok = self.toks[j]
            if tok.usado:
                break
            if tok.num:
                if self._eh_versao_num(j):
                    texto, j = self._ler_versao_num(j)
                    partes.append(texto)
                break
            if not tok.palavra or tok.t in _PARADAS or len(partes) == limite:
                break
            if self._marca_em(j):
                break
            k = j + 1
            while k < n and self.toks[k].colado and not self.toks[k].usado:
                if not (self.toks[k].num and self.toks[k].t.isdigit()) and not self.toks[k].palavra:
                    break
                k += 1
            partes.append(_bonito(self.trecho(j, k)))
            fechou = k > j + 1
            j = k
            if fechou:
                break
        return " ".join(partes), j

    def _completar(self, modelo: str, fim: int) -> tuple[str, int]:
        """Quando a pessoa está dizendo o modelo ("modelo Civic LXR"), a versão que não está
        no catálogo também entra."""
        extra, fim_extra = self._modelo_livre(fim)
        return (f"{modelo} {extra}", fim_extra) if extra else (modelo, fim)

    def _negado(self, i: int) -> bool:
        return "nao" in (self.t(i - 1), self.t(i - 2), self.t(i - 3))

    def veiculo(self) -> None:
        toks, campos = self.toks, self.r.campos
        n = len(toks)
        depois_do_tipo: int | None = None
        for i, tok in enumerate(toks):
            if not tok.usado and tok.t in _TIPOS and not self._negado(i):
                campos["tipo"] = _TIPOS[tok.t]
                tok.usado = True
                depois_do_tipo = i + 1

        marca: str | None = None
        modelo: str | None = None
        entrada: _Modelo | None = None

        # Rótulos explícitos: "marca Honda", "modelo Biz 125"
        for i, tok in enumerate(toks):
            if tok.usado or tok.t not in ("marca", "modelo"):
                continue
            j = i + 1
            while self.t(j) in (":", "=", "e", "eh", "da", "do", "de", "-"):
                j += 1
            if j >= n or toks[j].usado:
                continue
            if tok.t == "marca":
                achada = self._marca_em(j)
                if achada:
                    marca = achada[0]
                    self.usar(i, j + achada[1])
                elif toks[j].palavra and toks[j].t not in _PARADAS:
                    marca = _bonito(self.trecho(j, j + 1))
                    self.usar(i, j + 1)
            elif not (toks[j].num and toks[j].t.isdigit() and len(toks[j].t) in (2, 4)):
                achado = self._modelo_em(j, marca)
                if achado:
                    modelo, entrada, fim = achado
                    modelo, fim = self._completar(modelo, fim)
                else:
                    modelo, fim = self._modelo_livre(j)
                if modelo:
                    self.usar(i, fim)
                    self.fim_modelo = fim
                else:
                    modelo = None

        # Marca e modelo do catálogo, na ordem em que aparecem
        respondendo = self.aguardando in ("marca", "modelo")
        marca_solta: tuple[str, int, int] | None = None  # (nome, início, fim)
        i = 0
        while i < n and modelo is None:
            if toks[i].usado:
                i += 1
                continue
            achada = self._marca_em(i)
            if achada:
                nome, tamanho = achada
                depois = self._modelo_em(i + tamanho, nome)
                if depois:
                    modelo, entrada, fim = depois
                    if respondendo:
                        modelo, fim = self._completar(modelo, fim)
                    marca = marca or nome
                    self.usar(i, fim)
                    self.fim_modelo = fim
                    break
                if marca_solta is None:
                    marca_solta = (nome, i, i + tamanho)
                i += tamanho
                continue
            achado = self._modelo_em(i, None)
            if achado:
                modelo, entrada, fim = achado
                if respondendo:
                    modelo, fim = self._completar(modelo, fim)
                self.usar(i, fim)
                self.fim_modelo = fim
                break
            i += 1

        if marca_solta and marca is None:
            nome, ini, fim = marca_solta
            marca = nome
            self.usar(ini, fim)
            if modelo is None:  # marca conhecida, modelo fora do catálogo
                livre, fim_livre = self._modelo_livre(fim)
                if livre:
                    modelo = livre
                    self.usar(fim, fim_livre)
                    self.fim_modelo = fim_livre
        if marca is None and entrada is not None:
            marca = entrada.marca

        # "moto Kasinski Comet 250": depois de moto/carro, marca e modelo fora do catálogo
        if marca is None and modelo is None and depois_do_tipo is not None:
            j = depois_do_tipo
            while self.t(j) in ("da", "marca", ":", ","):
                j += 1
            if j < n and toks[j].palavra and not toks[j].usado and toks[j].t not in _PARADAS:
                livre, fim_livre = self._modelo_livre(j + 1)
                if livre and len(toks[j].t) >= 2:
                    marca, modelo = _bonito(self.trecho(j, j + 1)), livre
                    self.usar(j, fim_livre)
                    self.fim_modelo = fim_livre

        if marca:
            campos["marca"] = marca
        if modelo:
            campos["modelo"] = modelo
        if "tipo" not in campos:
            if entrada is not None and (marca is None or marca == entrada.marca):
                campos["tipo"] = entrada.tipo
            elif marca and len(_TIPOS_DA_MARCA.get(marca, ())) == 1:
                campos["tipo"] = next(iter(_TIPOS_DA_MARCA[marca]))
            elif entrada is not None:
                campos["tipo"] = entrada.tipo

    def quilometragem(self) -> None:
        toks = self.toks
        ordem: list[tuple[int, int]] = []  # (posição, km)
        for i, tok in enumerate(toks):  # "zero km", "zerokm"
            if tok.usado:
                continue
            if tok.t == "zerokm" or (tok.t == "zero" and self.t(i + 1) in _UNIDADES_KM):
                ordem.append((i, 0))
                self.usar(i, i + (1 if tok.t == "zerokm" else 2))
        for q in self.qtds:
            if q.rotulo or any(toks[k].usado for k in range(q.i, q.j)) or q.cifrao:
                continue
            j = q.j
            if self.t(j) == "de" and self.t(j + 1) in _UNIDADES_KM:
                j += 1
            if self.t(j) in _UNIDADES_KM and not self._ano_antes_do_km(q, j):
                fim = j + 1
                while self.t(fim) in _UNIDADES_KM:
                    fim += 1
                q.rotulo = "km"
                self.usar(q.i, fim)
                ordem.append((q.i, int(q.valor)))
                continue
            k = self._voltar(q.i)
            if k >= 0 and self.t(k) in _ROTULOS_KM:
                q.rotulo = "km"
                self.usar(k, q.j)
                ordem.append((q.i, int(q.valor)))
        todos = sorted(ordem)
        if not todos:
            return
        self.r.campos["km"] = todos[-1][1]
        if len({valor for _, valor in todos}) > 1:
            self.r.avisos.append(
                f"Você falou de km mais de uma vez; fiquei com o último: "
                f"{_inteiro(todos[-1][1])} km."
            )

    def _ano_antes_do_km(self, q: _Qtd, j: int) -> bool:
        """ "xre 300 2021 km 15000": aqui "km" é rótulo do número seguinte, e 2021 é o ano."""
        if not (q.simples and len(self.toks[q.i].t) == 4 and self.ano_plausivel(int(q.valor))):
            return False
        k = j + 1
        while self.t(k) in (":", "=", "e", "eh", "de", "-"):
            k += 1
        return any(outra.i == k for outra in self.qtds)

    def _voltar(self, i: int) -> int:
        """Anda para trás a partir do token i, pulando palavrinhas de ligação, e devolve o
        índice de onde parou: é ali que pode estar o rótulo ("km é", "comprei por R$")."""
        k, passos = i - 1, 0
        while k >= 0 and passos < 4:
            if self.t(k) in _LIGACOES:
                k, passos = k - 1, passos + 1
            elif self.t(k) == "," and self.t(k - 1) in ("errado", "errada"):
                k, passos = k - 2, passos + 1  # "km errado, é 20.500"
            else:
                break
        return k

    def _livre(self, q: _Qtd) -> bool:
        return q.rotulo is None and not any(self.toks[k].usado for k in range(q.i, q.j))

    def _frase_valor_antes(self, i: int) -> bool:
        """Há palavra de compra ou venda colada antes do token i? ("paguei 2000" não é ano)"""
        k = self._voltar(i)
        return k >= 0 and any(k == f[1] - 1 for f in self.frases)

    def _inteiro_em(self, k: int, digitos: tuple[int, ...]) -> int | None:
        toks = self.toks
        if 0 <= k < len(toks) and toks[k].num and not toks[k].usado and toks[k].t.isdigit():
            if len(toks[k].t) in digitos:
                return int(toks[k].t)
        return None

    def _ano_em(self, k: int) -> int | None:
        """Ano escrito com quatro dígitos ou com dois ("22" é 2022; "98" é 1998)."""
        valor = self._inteiro_em(k, (2, 4))
        if valor is None or len(self.toks[k].t) == 4:
            return valor
        return _expandir_ano(valor, self.ano_atual)

    def anos_marcados(self) -> None:
        """Ano em par (2021/2022) ou com rótulo ("ano 2023", "fabricação 2021 modelo 2022")."""
        toks, campos = self.toks, self.r.campos
        n = len(toks)

        # 2021/2022, 2021/22, 21/22
        for i in range(n - 2):
            if self.t(i + 1) != "/" or self.t(i + 3) == "/" or self.t(i - 1) == "/":
                continue
            fabricacao, segundo = self._ano_em(i), self._inteiro_em(i + 2, (2, 4))
            if fabricacao is None or segundo is None:
                continue
            if len(toks[i + 2].t) == 4:
                modelo = segundo
            elif len(toks[i].t) == 4:
                modelo = fabricacao // 100 * 100 + segundo
                if modelo < fabricacao:
                    modelo += 100
            else:
                modelo = _expandir_ano(segundo, self.ano_atual)
            if not (self.ano_plausivel(fabricacao) and self.ano_plausivel(modelo)):
                continue
            if 0 <= modelo - fabricacao <= 1:
                campos["ano_fabricacao"], campos["ano_modelo"] = fabricacao, modelo
            else:
                self.r.erros.append(
                    f"Não entendi o ano {self.trecho(i, i + 3)}: o ano do modelo costuma ser "
                    "igual ao de fabricação ou um a mais."
                )
            self.usar(i, i + 3)
            if self.t(i - 1) in ("ano", "modelo"):
                self.usar(i - 1, i)

        partes = {"fabricacao", "fabricada", "fabricado", "fab", "modelo"}
        for i, tok in enumerate(toks):
            if tok.usado or (tok.t != "ano" and tok.t not in partes):
                continue
            alvo = None if tok.t == "ano" else ("modelo" if tok.t == "modelo" else "fabricacao")
            j = i + 1
            while self.t(j) in ("de", "do", "da", "e", "eh", "em", ":", "=", *partes):
                if self.t(j) in partes:
                    alvo = "modelo" if self.t(j) == "modelo" else "fabricacao"
                j += 1
            ano = self._ano_em(j)
            if ano is None or self.t(j + 1) in ("mil", "/"):
                continue
            self.usar(i, j + 1)
            if not self.ano_plausivel(ano):
                self.r.erros.append(
                    f"O ano {ano} está fora da faixa que eu aceito "
                    f"({ANO_MINIMO} a {self.ano_maximo})."
                )
                continue
            if alvo != "modelo":
                campos["ano_fabricacao"] = ano
            if alvo != "fabricacao":
                campos["ano_modelo"] = ano
            self.ano_unico = ano if alvo is None else None

    def anos_soltos(self) -> None:
        """Ano sem rótulo: quatro dígitos em qualquer lugar ou dois logo depois do modelo."""
        toks, campos = self.toks, self.r.campos
        so_um_numero = len([q for q in self.qtds if self._livre(q)]) == 1
        esperando_numero = self.aguardando in (_COMPRA, _VENDA, "km")
        soltos: list[tuple[int, int]] = []
        for q in self.qtds:
            if not self._livre(q) or not q.simples or q.j != q.i + 1:
                continue
            if len(toks[q.i].t) != 4 or not self.ano_plausivel(int(q.valor)):
                continue
            if self._frase_valor_antes(q.i) or (esperando_numero and so_um_numero):
                continue
            if self.t(q.i - 1) in _ANTES_NAO_E_ANO:  # "IPVA 2026 pago", "comprada em 2023"
                self.usar(q.i, q.j)
                continue
            soltos.append((q.i, int(q.valor)))
        if soltos:
            for i, _ in soltos:
                self.usar(i, i + 1)
            ultimo_i, ultimo = soltos[-1]
            anterior = soltos[-2] if len(soltos) >= 2 else None
            if anterior and anterior[0] == ultimo_i - 1 and 0 <= ultimo - anterior[1] <= 1:
                campos["ano_fabricacao"], campos["ano_modelo"] = anterior[1], ultimo
                self.ano_unico = None
            elif "ano_modelo" in campos or "ano_fabricacao" in campos:
                # já veio com rótulo ("fabricação 2021"): o ano solto completa o que falta
                campos.setdefault("ano_fabricacao", ultimo)
                campos.setdefault("ano_modelo", ultimo)
            else:
                campos["ano_fabricacao"] = campos["ano_modelo"] = self.ano_unico = ultimo
                if len({ano for _, ano in soltos}) > 1:
                    self.r.avisos.append(f"Vi mais de um ano; fiquei com o último: {ultimo}.")
        unico = self.ano_unico
        if unico is not None and campos.get("ano_fabricacao") == campos.get("ano_modelo"):
            self.r.avisos.append(f"Considerei {unico} como ano de fabricação e do modelo.")

        # "cg 160 fan 22": dois dígitos logo depois do modelo
        if "ano_modelo" in campos or "ano_fabricacao" in campos:
            return
        candidatos = [self.fim_modelo] if self.fim_modelo is not None else []
        if self.aguardando in ("ano_fabricacao", "ano_modelo") and len(self.qtds) == 1:
            candidatos.append(self.qtds[0].i)
        for i in candidatos:
            dois = self._inteiro_em(i, (2,))
            if dois is None:
                continue
            seguinte = self.t(i + 1)
            if seguinte in ("mil", "k", "/", "x", "v", "cv", "hp", "valvulas", "portas", "lugares"):
                continue
            if seguinte in _UNIDADES_KM or seguinte in _MOEDA_DEPOIS:
                continue
            ano = _expandir_ano(dois, self.ano_atual)
            if not self.ano_plausivel(ano):
                continue
            self.usar(i, i + 1)
            campos["ano_fabricacao"] = campos["ano_modelo"] = ano
            self.r.avisos.append(
                f"Considerei “{toks[i].t}” como o ano {ano}, de fabricação e do modelo."
            )
            break

    def cor(self) -> None:
        toks = self.toks
        n = len(toks)

        def cor_em(i: int) -> tuple[str, int] | None:
            if self.t(i) not in _CORES:
                return None
            nome, j = _CORES[self.t(i)], i + 1
            if self.t(j) in _TONS:
                nome, j = f"{nome} {_TONS[self.t(j)]}", j + 1
            return nome, j

        achada: str | None = None
        i = 0
        while i < n:
            lida = cor_em(i)
            if lida is None:
                i += 1
                continue
            nome, j = lida
            antes = self.t(i - 1)
            if antes in _ANTES_NAO_E_COR or (antes == "em" and toks[i].t in ("branco", "branca")):
                i = j
                continue
            if self.t(j) in ("e", "com", "/"):  # "vermelha e preta"
                segunda = cor_em(j + 1)
                if segunda:
                    nome, j = f"{nome} e {segunda[0].lower()}", segunda[1]
            self.usar(i, j)
            if self.t(i - 1) == "cor":
                self.usar(i - 1, i)
            achada = nome
            i = j
        if achada is None:
            for i, tok in enumerate(toks):  # "cor abóbora": cor fora da lista, com rótulo
                if tok.usado or tok.t != "cor":
                    continue
                j = i + 1
                while self.t(j) in (":", "=", "e", "eh", "da", "do", "para", "pra", "agora"):
                    j += 1
                if j < n and toks[j].palavra and not toks[j].usado and toks[j].t not in _PARADAS:
                    achada = self.trecho(j, j + 1).capitalize()
                    self.usar(i, j + 1)
                    break
        if achada:
            self.r.campos["cor"] = achada

    def _frases_de_valor(self) -> list[list]:
        """Onde aparecem palavras de compra e venda: [início, fim, campo, usada]."""
        frases: list[list] = []
        i, n = 0, len(self.toks)
        while i < n:
            for frase, campo in _FRASES_VALOR:
                partes = frase.split()
                if [self.t(k) for k in range(i, i + len(partes))] == partes:
                    frases.append([i, i + len(partes), campo, False])
                    i += len(partes) - 1
                    break
            i += 1
        return frases

    def _rotular(self, candidatos: list[_Qtd], depois_primeiro: bool) -> tuple[dict, int]:
        """Liga cada valor à palavra de compra/venda mais próxima. Devolve (ligações, sobras)."""
        frases = [list(f) for f in self.frases]
        ligacoes: dict[int, str] = {}

        def antes(q: _Qtd) -> str | None:
            k = self._voltar(q.i)
            for f in frases:
                if not f[3] and f[1] - 1 == k:
                    f[3] = True
                    return f[2]
            return None

        def depois(q: _Qtd, exige_ligacao: bool) -> str | None:
            k, passos = q.j, 0
            while passos < 2 and self.t(k) in _DEPOIS_DO_VALOR:
                k, passos = k + 1, passos + 1
            if exige_ligacao and passos == 0:
                return None
            for f in frases:
                if not f[3] and f[0] == k:
                    f[3] = True
                    return f[2]
            return None

        for posicao, q in enumerate(candidatos):
            if depois_primeiro:
                campo = depois(q, False) or antes(q)
            else:
                campo = antes(q) or depois(q, True)
            if campo:
                ligacoes[posicao] = campo
        # Palavra distante: "comprei uma CG 160 vermelha por 11.500". Sem "por" nem R$ o
        # número pode ser km ("comprei uma biz 2021 22 mil"): aí fica para a pergunta.
        for indice, f in enumerate(frases):
            if f[3]:
                continue
            limite = frases[indice + 1][0] if indice + 1 < len(frases) else len(self.toks)
            entre = [
                p
                for p, q in enumerate(candidatos)
                if p not in ligacoes and f[1] <= q.i < limite and self._parece_dinheiro(q)
            ]
            entre = [
                p for p in entre if candidatos[p].cifrao or self.t(candidatos[p].i - 1) == "por"
            ]
            if len(entre) == 1:
                ligacoes[entre[0]] = f[2]
                f[3] = True
        sobras = sum(1 for f in frases if not f[3]) + sum(
            1 for p, q in enumerate(candidatos) if p not in ligacoes and self._parece_dinheiro(q)
        )
        return ligacoes, sobras

    @staticmethod
    def _parece_dinheiro(q: _Qtd) -> bool:
        return q.dinheiro or q.valor >= 1000

    def _descartado(self, q: _Qtd) -> bool:
        """ "o preço é 15.900 e não 14.900": o número depois de "e não" é o que não vale."""
        k, passos = q.i - 1, 0
        while k >= 0 and passos < 3 and self.t(k) in _LIGACOES - {"e"}:
            k, passos = k - 1, passos + 1
        return self.t(k) == "nao" and self.t(k - 1) == "e"

    def valores(self) -> None:
        candidatos = []
        for q in self.qtds:
            if not self._livre(q):
                continue
            if self._descartado(q):
                self.usar(q.i, q.j)
            else:
                candidatos.append(q)
        if not candidatos:
            return
        ligacoes, sobras = self._rotular(candidatos, depois_primeiro=False)
        if sobras:
            outras, outras_sobras = self._rotular(candidatos, depois_primeiro=True)
            if outras_sobras < sobras:
                ligacoes = outras
        if self.aguardando in (_COMPRA, _VENDA, "km"):  # resposta à pergunta que foi feita
            sem_rotulo = [p for p in range(len(candidatos)) if p not in ligacoes]
            fortes = [p for p in sem_rotulo if self._parece_dinheiro(candidatos[p])]
            if len(sem_rotulo) == 1 or len(fortes) == 1:
                ligacoes[fortes[0] if len(fortes) == 1 else sem_rotulo[0]] = self.aguardando
        vistos: dict[str, tuple[Decimal, bool]] = {}  # campo -> (valor, veio com R$/reais)
        for posicao, q in enumerate(candidatos):
            campo = ligacoes.get(posicao)
            self.usar(q.i, q.j)
            if campo is None:
                if self._parece_dinheiro(q):
                    self.r.soltos.append((q.valor, q.cifrao))
                continue
            if campo == "km":
                self.r.campos["km"] = int(q.valor)
                continue
            if campo in vistos and vistos[campo][0] != q.valor:
                nome = "valor de compra" if campo == _COMPRA else "preço de venda"
                self.r.avisos.append(
                    f"Vi mais de um {nome}; fiquei com o último: {_moeda(q.valor)}."
                )
            vistos[campo] = (q.valor, q.cifrao)
        for campo, (valor, explicito) in vistos.items():
            nome = "valor de compra" if campo == _COMPRA else "preço de venda"
            # abaixo de 100 nunca passa; abaixo de 1.000 só escrito com R$ ou "reais"
            if 0 < valor < 100 or (0 < valor < 1000 and not explicito):
                curto = _numero_curto(valor)
                frase = (
                    f"Entendi {_moeda(valor)} como {nome}, o que é pouco para um veículo. "
                    f"Se for {curto} mil, escreva “{curto} mil” ou o valor completo."
                )
                if valor >= 100:
                    frase += f" Se for isso mesmo, escreva “{curto} reais”."
                self.r.erros.append(frase)
                continue
            self.r.campos[campo] = valor.quantize(CENTAVO)

    def resposta_curta(self) -> None:
        """A pessoa respondeu só o que foi perguntado: "zero" para o km, "abóbora" para a cor."""
        campos, alvo = self.r.campos, self.aguardando
        if alvo is None or alvo in campos or alvo == "confirmacao":
            return
        livres = [k for k, tok in enumerate(self.toks) if not tok.usado]
        while livres and self.toks[livres[0]].t in ("e", "eh", "uma", "um", "a", "o", ":", "da"):
            livres.pop(0)
        while livres and not (self.toks[livres[-1]].palavra or self.toks[livres[-1]].num):
            livres.pop()
        if alvo == "km":
            if [self.toks[k].t for k in livres] in (["zero"], ["zerada"], ["zerado"]):
                campos["km"] = 0
                self.usar(livres[0], livres[0] + 1)
            return
        if alvo == "renavam":
            digitos = validacao.so_digitos(self.texto())
            if 9 <= len(digitos) <= 11:
                campos["renavam"] = validacao.normalizar_renavam(digitos)
                self.usar(0, len(self.toks))
            return
        if not livres or len(livres) > 6:
            return
        seguidos = livres == list(range(livres[0], livres[-1] + 1))
        primeiro = self.toks[livres[0]]
        if not seguidos or not primeiro.palavra or primeiro.t in _PARADAS:
            return
        if alvo == "cor" and len(livres) <= 3:
            campos["cor"] = self.trecho(livres[0], livres[-1] + 1).capitalize()
            self.usar(livres[0], livres[-1] + 1)

    def veiculo_respondido(self) -> None:
        """Perguntei marca ou modelo e a resposta não está no catálogo: "Zontes Tactic 400"."""
        campos, alvo, toks = self.r.campos, self.aguardando, self.toks
        if alvo not in ("marca", "modelo") or "marca" in campos or "modelo" in campos:
            return
        if "?" in self.norm:
            return
        i = 0
        while i < len(toks) and (
            toks[i].usado or toks[i].t in ("e", "eh", "uma", "um", "a", "o", ":", "da", "do")
        ):
            i += 1
        if i >= len(toks) or not toks[i].palavra or toks[i].t in _PARADAS:
            return
        if alvo == "marca":
            campos["marca"] = _bonito(self.trecho(i, i + 1))
            self.usar(i, i + 1)
            i += 1
        modelo, fim = self._modelo_livre(i, limite=4)
        if modelo:
            campos["modelo"] = modelo
            self.usar(i, fim)
            self.fim_modelo = fim

    # ----- tudo junto -----

    def ler(self) -> Interpretacao:
        r = self.r
        limpo = " ".join(re.findall(r"[a-z0-9]+", self.norm))
        palavras = limpo.split()
        if not palavras:
            return r
        if _CANCELAR.fullmatch(limpo):
            r.intencao = "cancelar"
            return r
        sim = all(p in _SIM_NUCLEO or p in _SIM_ENFEITE for p in palavras) and (
            any(p in _SIM_NUCLEO for p in palavras)
            or limpo in ("ta bom", "esta bom", "tudo bom", "ta otimo", "vai la")
        )
        nao = all(p in _NAO_NUCLEO or p in _NAO_ENFEITE for p in palavras) and any(
            p in _NAO_NUCLEO for p in palavras
        )
        if _FORA_FORTE.search(limpo):
            r.intencao = "fora_escopo"
            r.venda = _VENDA_REGISTRO.search(limpo) is not None
            return r

        self.remocoes()
        self.observacoes()
        self.datas()
        self.documentos()
        self.placa()
        self.situacao()
        self.toks = _tokenizar(self.texto())
        self.veiculo()
        self.veiculo_respondido()
        self.qtds = _quantidades(self.toks)
        self.frases = self._frases_de_valor()
        self.anos_marcados()
        self.quilometragem()
        self.anos_soltos()
        self.cor()
        self.valores()
        self.resposta_curta()

        pergunta = "?" in self.norm or _PERGUNTA.match(limpo) is not None
        tem_dados = bool(r.campos or r.remover or r.erros or r.soltos)
        pede_ajuda = _SAUDACAO.fullmatch(limpo) or _AJUDA.search(limpo)
        if nao and not tem_dados:
            r.intencao = "negacao"
        elif sim and not (pede_ajuda and self.aguardando != "confirmacao"):
            r.intencao = "afirmacao"
        elif (
            pergunta
            and not r.remover
            and (
                set(r.campos) <= {"situacao", "tipo"}
                or (
                    _PERGUNTA.match(limpo)
                    and set(r.campos) <= {"situacao", "tipo", "marca", "modelo"}
                )
            )
        ):
            # pergunta sem dado de veículo: não é cadastro ("tem moto à venda?")
            r.intencao = "ajuda" if pede_ajuda else "fora_escopo"
            r.campos.clear()
            r.erros.clear()
            r.soltos.clear()
        elif tem_dados:
            r.intencao = "cadastro"
        elif pede_ajuda:
            r.intencao = "ajuda"
        elif _OBRIGADO.fullmatch(limpo):
            r.intencao = "agradecimento"
        return r


def interpretar(
    mensagem: str, aguardando: str | None = None, *, ano_atual: int | None = None
) -> Interpretacao:
    """Lê uma mensagem e devolve o que deu para entender. Função pura: não consulta o banco.

    `aguardando` é o campo que a conversa acabou de perguntar: com ele, uma resposta curta
    ("11500", "Honda Biz 125", "vermelha") é lida no contexto certo.
    """
    return _Leitor(mensagem, aguardando, ano_atual or hoje().year).ler()


# ---------------------------------------------------------------------------------------
# Conversa
# ---------------------------------------------------------------------------------------

_ROTULOS = {
    "tipo": "Tipo",
    "marca": "Marca",
    "modelo": "Modelo",
    "ano": "Ano",
    "ano_fabricacao": "Ano de fabricação",
    "ano_modelo": "Ano do modelo",
    "cor": "Cor",
    "km": "Km",
    "placa": "Placa",
    "chassi": "Chassi",
    "renavam": "RENAVAM",
    "valor_compra": "Valor de compra",
    "preco_venda": "Preço de venda",
    "situacao": "Situação",
    "observacoes": "Observações",
}
_NOME_NA_FRASE = {
    "tipo": "o tipo",
    "marca": "a marca",
    "modelo": "o modelo",
    "ano_fabricacao": "o ano de fabricação",
    "ano_modelo": "o ano",
    "cor": "a cor",
    "km": "o km",
    "placa": "a placa",
    "chassi": "o chassi",
    "renavam": "o RENAVAM",
    "valor_compra": "o valor de compra",
    "preco_venda": "o preço de venda",
    "observacoes": "a observação",
}
_SITUACOES = {
    Situacao.compra: "Compra",
    Situacao.documentacao: "Documentação",
    Situacao.preparacao: "Preparação",
    Situacao.a_venda: "À venda",
}
_TIPO = {TipoVeiculo.moto: "Moto", TipoVeiculo.carro: "Carro"}
_ORDEM_OBRIGATORIOS = ("marca", "modelo", "tipo", "valor_compra")
_SUGERIDOS = ("ano_modelo", "km", "placa", "preco_venda")
_LIMITES_TEXTO = {"marca": 60, "modelo": 120, "cor": 40}


def _sem_artigo(campo: str) -> str:
    return _NOME_NA_FRASE[campo].split(" ", 1)[1]


def _placa_formatada(placa: str) -> str:
    return f"{placa[:3]}-{placa[3:]}"


def _ano_formatado(rascunho: dict) -> str | None:
    fabricacao, modelo = rascunho.get("ano_fabricacao"), rascunho.get("ano_modelo")
    if fabricacao and modelo:
        return f"{fabricacao}/{modelo}"
    if modelo:
        return f"{modelo} (modelo)"
    if fabricacao:
        return f"{fabricacao} (fabricação)"
    return None


def _valor_formatado(campo: str, rascunho: dict) -> str:
    valor = rascunho[campo]
    if campo == "tipo":
        return _TIPO[valor]
    if campo == "km":
        return f"{_inteiro(valor)} km"
    if campo == "placa":
        return _placa_formatada(valor)
    if campo in (_COMPRA, _VENDA):
        return _moeda(valor)
    if campo == "situacao":
        return _SITUACOES[valor]
    return str(valor)


def _lista(itens: list[str]) -> str:
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _percentual(valor: Decimal) -> str:
    return f"{valor.normalize():f}".replace(".", ",") + "%"


def _ficha(db: Session, usuario: Usuario, rascunho: dict) -> list[schemas.AssistenteItemFicha]:
    itens: list[schemas.AssistenteItemFicha] = []

    def item(campo: str, valor: str, calculado: bool = False, rotulo: str | None = None) -> None:
        itens.append(
            schemas.AssistenteItemFicha(
                campo=campo, rotulo=rotulo or _ROTULOS[campo], valor=valor, calculado=calculado
            )
        )

    for campo in ("tipo", "marca", "modelo"):
        if campo in rascunho:
            item(campo, _valor_formatado(campo, rascunho))
    ano = _ano_formatado(rascunho)
    if ano:
        item("ano", ano)
    for campo in ("cor", "km", "placa", "chassi", "renavam", _COMPRA, _VENDA):
        if campo in rascunho:
            item(campo, _valor_formatado(campo, rascunho))
    if rascunho:
        item("situacao", _SITUACOES[rascunho.get("situacao", Situacao.compra)])
    if "observacoes" in rascunho:
        item("observacoes", rascunho["observacoes"])
    if _COMPRA in rascunho and _VENDA in rascunho and pode(usuario, P.custos_ver):
        compra, venda = rascunho[_COMPRA], rascunho[_VENDA]
        item("lucro_previsto", _moeda(venda - compra), True, "Lucro previsto")
        aliquota = aliquota_imposto(db)
        if aliquota > 0:
            item(
                "imposto_previsto",
                _moeda(calcular_imposto(venda, compra, aliquota)),
                True,
                f"Imposto estimado ({_percentual(aliquota)})",
            )
    return itens


def _conferir(campo: str, valor: Any, ano_maximo: int) -> str | None:
    """Mesmos limites do cadastro, com a frase pronta para a conversa. None = pode entrar."""
    if campo in _LIMITES_TEXTO:
        if not str(valor).strip():
            return f"Não entendi {_NOME_NA_FRASE[campo]}."
        if len(str(valor)) > _LIMITES_TEXTO[campo]:
            return f"{_ROTULOS[campo]}: texto longo demais (até {_LIMITES_TEXTO[campo]} letras)."
    elif campo in ("ano_fabricacao", "ano_modelo"):
        if not ANO_MINIMO <= valor <= ano_maximo:
            return f"O ano {valor} está fora da faixa que eu aceito ({ANO_MINIMO} a {ano_maximo})."
    elif campo == "km":
        if not 0 <= valor <= 9_999_999:
            return f"{_inteiro(valor)} km é quilometragem demais; confira o número."
    elif campo == _COMPRA:
        if valor < 0 or valor >= Decimal("10000000000"):
            return "Não consegui usar esse valor de compra; confira o número."
    elif campo == _VENDA:
        if valor <= 0:
            return "O preço de venda precisa ser maior que zero."
        if valor >= Decimal("10000000000"):
            return "Não consegui usar esse preço de venda; confira o número."
    return None


def _duplicado(db: Session, rascunho: dict) -> schemas.AssistenteDuplicado | None:
    for campo, coluna in (("placa", Veiculo.placa), ("chassi", Veiculo.chassi)):
        valor = rascunho.get(campo)
        if not valor:
            continue
        outro = db.scalar(select(Veiculo).where(coluna == valor))
        if outro is not None:
            return schemas.AssistenteDuplicado(id=outro.id, descricao=outro.descricao, campo=campo)
    return None


def _faltando(rascunho: dict) -> list[str]:
    faltam = [campo for campo in _ORDEM_OBRIGATORIOS if campo not in rascunho]
    if rascunho.get("situacao") == Situacao.a_venda and _VENDA not in rascunho:
        faltam.append(_VENDA)  # mesma regra do formulário: à venda exige preço
    return faltam


def _pergunta(campo: str, faltam: list[str]) -> str:
    if campo == "marca":
        if "modelo" in faltam:
            return "Qual é a marca e o modelo? Por exemplo: Honda Biz 125."
        return "Qual é a marca? Por exemplo: Honda."
    if campo == "modelo":
        return "Qual é o modelo? Por exemplo: CG 160 Fan."
    if campo == "tipo":
        return "É moto ou carro?"
    if campo == _COMPRA:
        return (
            "Qual foi o valor de compra? Pode responder só o número, "
            "por exemplo: 11.500 ou 11,5 mil."
        )
    if campo == _VENDA:
        return "Para já ficar à venda preciso do preço. Por quanto vai anunciar? Exemplo: 14.900."
    if campo == "placa":
        return "Se a placa estiver errada, me mande a certa."
    return "Se o chassi estiver errado, me mande o certo."


def _resumo_do_que_mudou(mudou: list[str], rascunho: dict) -> str:
    partes: list[str] = []
    if any(campo in mudou for campo in ("tipo", "marca", "modelo", "ano_fabricacao", "ano_modelo")):
        veiculo = [
            _TIPO[rascunho["tipo"]] if "tipo" in rascunho else None,
            rascunho.get("marca"),
            rascunho.get("modelo"),
            _ano_formatado(rascunho),
        ]
        partes.append(" ".join(str(parte) for parte in veiculo if parte))
    if "cor" in mudou:
        partes.append(f"cor {rascunho['cor'].lower()}")
    if "km" in mudou:
        partes.append(_valor_formatado("km", rascunho))
    if "placa" in mudou:
        partes.append(f"placa {_placa_formatada(rascunho['placa'])}")
    if "chassi" in mudou:
        partes.append(f"chassi {rascunho['chassi']}")
    if "renavam" in mudou:
        partes.append(f"RENAVAM {rascunho['renavam']}")
    if _COMPRA in mudou:
        partes.append(f"compra por {_moeda(rascunho[_COMPRA])}")
    if _VENDA in mudou:
        partes.append(f"venda por {_moeda(rascunho[_VENDA])}")
    if "situacao" in mudou:
        partes.append(f"situação {_SITUACOES[rascunho['situacao']].lower()}")
    if "observacoes" in mudou:
        partes.append("observação anotada")
    return ", ".join(partes)


def _frase_soltos(soltos: list[tuple[Decimal, bool]]) -> str:
    if all(dinheiro for _, dinheiro in soltos):
        valores = _lista([_moeda(valor) for valor, _ in soltos])
        return (
            f"Vi {valores}, mas não sei se é valor de compra ou preço de venda. "
            "Escreva, por exemplo: “comprei por 9 mil” ou “vendo por 12 mil”."
        )
    numeros = _lista([_numero_curto(valor) for valor, _ in soltos])
    oque = "o número" if len(soltos) == 1 else "os números"
    return (
        f"Vi {oque} {numeros}, mas não sei se é km, valor de compra ou preço de venda. "
        "Escreva, por exemplo: “18.500 km”, “comprei por 9 mil” ou “vendo por 12 mil”."
    )


def _texto_ajuda() -> str:
    return (
        "Olá! Eu cadastro veículo novo no estoque por mensagem: escreva os dados do jeito que "
        "você fala, em qualquer ordem, e eu monto a ficha.\n"
        f"Exemplo: {EXEMPLO}.\n"
        "Antes de gravar eu mostro a ficha e peço a sua confirmação."
    )


def conversar(
    db: Session,
    usuario: Usuario,
    mensagem: str,
    estado: schemas.AssistenteEstado | None,
) -> schemas.AssistenteResposta:
    """Uma rodada da conversa: entende a mensagem, atualiza o rascunho e responde."""
    ano_maximo = hoje().year + 1
    rascunho: dict[str, Any] = estado.rascunho.model_dump(exclude_none=True) if estado else {}
    if rascunho.get("situacao") not in _SITUACOES:
        rascunho.pop("situacao", None)  # o estado vem do navegador: só valem etapas de estoque
    aguardando = estado.aguardando if estado else None
    tinha_rascunho = bool(rascunho)
    lido = interpretar(mensagem, aguardando)

    paragrafos: list[str] = []
    avisos: list[str] = []
    acao = "nenhuma"
    veiculo_criado: schemas.AssistenteVeiculo | None = None

    def responder(proximo: str | None) -> schemas.AssistenteResposta:
        faltam = _faltando(rascunho)
        duplicado = _duplicado(db, rascunho)
        if _COMPRA in rascunho and _VENDA in rascunho and rascunho[_VENDA] < rascunho[_COMPRA]:
            avisos.append("O preço de venda está abaixo do valor de compra.")
        return schemas.AssistenteResposta(
            resposta="\n".join(p for p in paragrafos if p),
            estado=schemas.AssistenteEstado(
                rascunho=schemas.AssistenteRascunho(**rascunho), aguardando=proximo
            ),
            ficha=_ficha(db, usuario, rascunho),
            faltando=[_campo(c) for c in faltam],
            sugeridos=[_campo(c) for c in _SUGERIDOS if rascunho and _campo_vazio(rascunho, c)],
            pronto=bool(rascunho) and not faltam and duplicado is None,
            acao=acao,
            veiculo=veiculo_criado,
            duplicado=duplicado,
            avisos=avisos,
        )

    def seguir() -> schemas.AssistenteResposta:
        """Depois de mexer no rascunho: pergunta o que falta ou pede a confirmação."""
        nonlocal acao
        if not rascunho:
            return responder(None)
        duplicado = _duplicado(db, rascunho)
        if duplicado is not None:
            artigo = "esta placa" if duplicado.campo == "placa" else "este chassi"
            paragrafos.append(
                f"Já existe um veículo com {artigo} no sistema: {duplicado.descricao}. "
                f"{_pergunta(duplicado.campo, [])} Se for o mesmo veículo, ele já está "
                "cadastrado: responda “cancela”."
            )
            return responder(duplicado.campo)
        faltam = _faltando(rascunho)
        if faltam:
            paragrafos.append(_pergunta(faltam[0], faltam))
            return responder(faltam[0])
        acao = "confirmar"
        sugeridos = [_sem_artigo(c) for c in _SUGERIDOS if _campo_vazio(rascunho, c)]
        if sugeridos:
            paragrafos.append(
                f"Faltou {_lista(sugeridos)}. Quer acrescentar ou posso cadastrar assim?"
            )
        else:
            paragrafos.append("Confira a ficha. Posso cadastrar?")
        return responder("confirmacao")

    def lembrar_pendencia() -> schemas.AssistenteResposta:
        """Resposta que não mexe no rascunho: repete o que estava pendente."""
        nonlocal acao
        if not rascunho:
            return responder(None)
        pode_confirmar = not _faltando(rascunho) and _duplicado(db, rascunho) is None
        if aguardando == "confirmacao" and pode_confirmar:
            acao = "confirmar"
            paragrafos.append(
                "Sobre o cadastro em andamento: responda “sim” para gravar, diga o que "
                "corrigir (por exemplo: “o km é 20 mil”) ou “cancela” para desistir."
            )
            return responder("confirmacao")
        return seguir()

    # 1. Cancelar
    if lido.intencao == "cancelar":
        rascunho.clear()
        acao = "cancelado"
        paragrafos.append(
            "Pronto, descartei o rascunho. Quando quiser cadastrar outro veículo, é só mandar "
            "os dados."
            if tinha_rascunho
            else "Não havia cadastro em andamento. Quando quiser, é só mandar os dados do veículo."
        )
        return responder(None)

    # 2. Confirmação
    muda_algo = bool(lido.remover) or any(rascunho.get(c) != v for c, v in lido.campos.items())
    if lido.intencao == "afirmacao" and not muda_algo:
        if aguardando == "confirmacao" and not _faltando(rascunho):
            duplicado = _duplicado(db, rascunho)
            if duplicado is not None:
                return seguir()
            try:
                dados = schemas.VeiculoCriar.model_validate(rascunho)
                veiculo = criar_veiculo(db, dados, usuario)
            except ValidationError as erro:
                paragrafos.append(f"Não consegui gravar: {_frase_validacao(erro)}")
                return lembrar_pendencia()
            except HTTPException as erro:
                db.rollback()
                paragrafos.append(f"Não consegui gravar: {erro.detail}")
                return lembrar_pendencia()
            acao = "criado"
            veiculo_criado = schemas.AssistenteVeiculo(
                id=veiculo.id, descricao=veiculo.descricao, placa=veiculo.placa
            )
            etapa = _SITUACOES[veiculo.situacao]
            passos = "adicione as fotos na página do veículo"
            if veiculo.placa:
                passos += " e consulte a procedência pela placa"
            paragrafos.append(
                f"Pronto! {veiculo.descricao} entrou no estoque, na etapa {etapa}.\n"
                f"Próximos passos: {passos}."
            )
            rascunho.clear()
            return responder(None)
        if not rascunho:
            paragrafos.append(
                "Ainda não há cadastro em andamento, então não gravei nada. "
                f"Mande os dados do veículo, por exemplo: {EXEMPLO_CURTO}."
            )
            return responder(None)
        faltam = _faltando(rascunho)
        if faltam:
            nomes = _lista([_NOME_NA_FRASE[c] for c in faltam])
            paragrafos.append(f"Ainda não dá para cadastrar: falta {nomes}.")
        return seguir()

    if lido.intencao == "negacao":
        if aguardando == "confirmacao" and rascunho:
            paragrafos.append(
                "Sem problema, não gravei nada. O que precisa corrigir? Por exemplo: "
                "“o km é 20 mil”, “a placa é ABC1D24” ou “tira o preço”."
            )
            return responder(None)
        if rascunho:
            paragrafos.append("Tudo bem, não gravei nada.")
            return seguir()
        paragrafos.append(
            f"Tudo bem. Quando quiser cadastrar um veículo, mande os dados: {EXEMPLO_CURTO}."
        )
        return responder(None)

    # 3. Ajuda e assuntos que ainda não são deste assistente
    if lido.intencao == "ajuda":
        paragrafos.append(_texto_ajuda())
        return lembrar_pendencia()
    if lido.intencao == "agradecimento":
        paragrafos.append(
            "De nada!"
            if rascunho
            else "De nada! Quando chegar outro veículo, é só mandar os dados."
        )
        return lembrar_pendencia()
    if lido.intencao == "fora_escopo":
        if lido.venda:
            paragrafos.append(
                "Registrar venda ainda não é comigo: por enquanto eu só cadastro veículo novo. "
                "Para dar baixa, use o botão Vender no veículo, na tela de Estoque."
            )
        else:
            paragrafos.append(
                "Isso ainda não é comigo: por enquanto eu só cadastro veículo novo no estoque. "
                "Consultas de vendas, estoque e financeiro ficam nas outras telas do menu."
            )
        return lembrar_pendencia()
    if lido.intencao == "nada":
        if rascunho:
            paragrafos.append("Não entendi essa mensagem.")
            return lembrar_pendencia()
        paragrafos.append(
            "Não entendi essa mensagem. Eu cadastro veículo novo no estoque: mande os dados "
            f"numa frase.\nExemplo: {EXEMPLO_CURTO}."
        )
        return responder(None)

    # 4. Dados do veículo: junta ao rascunho
    paragrafos.extend(lido.erros)
    removidos = [campo for campo in lido.remover if campo in rascunho]
    for campo in removidos:
        del rascunho[campo]
    mudou: list[str] = []
    for campo, valor in lido.campos.items():
        problema = _conferir(campo, valor, ano_maximo)
        if problema:
            paragrafos.append(problema)
            continue
        if rascunho.get(campo) != valor:
            mudou.append(campo)
        rascunho[campo] = valor
    try:  # a palavra final é sempre a do schema do cadastro
        schemas.AssistenteRascunho(**rascunho)
    except ValidationError as erro:
        for detalhe in erro.errors():
            campo = str(detalhe["loc"][0]) if detalhe["loc"] else ""
            if campo in rascunho:
                del rascunho[campo]
                mudou = [c for c in mudou if c != campo]
        paragrafos.append(f"Um dado não passou na conferência: {_frase_validacao(erro)}")
    avisos.extend(lido.avisos)

    resumo = _resumo_do_que_mudou(mudou, rascunho)
    if resumo:
        paragrafos.append(("Certo, atualizei: " if tinha_rascunho else "Anotei: ") + resumo + ".")
    if removidos:
        nomes = _lista(sorted({_sem_artigo(c) for c in removidos}))
        paragrafos.append(f"Tirei da ficha: {nomes}.")
    elif lido.remover and not mudou:
        paragrafos.append("Esse campo já estava vazio.")
    if lido.soltos:
        paragrafos.append(_frase_soltos(lido.soltos))
    if not paragrafos:
        paragrafos.append("Isso já estava na ficha.")
    return seguir()


def _campo(campo: str) -> schemas.AssistenteCampo:
    return schemas.AssistenteCampo(campo=campo, rotulo=_ROTULOS[campo])


def _campo_vazio(rascunho: dict, campo: str) -> bool:
    if campo == "ano_modelo":
        return "ano_modelo" not in rascunho and "ano_fabricacao" not in rascunho
    return campo not in rascunho


_MENSAGENS_VALIDACAO = {
    "missing": "campo obrigatório",
    "string_too_short": "campo obrigatório",
    "greater_than": "deve ser maior que zero",
    "greater_than_equal": "valor abaixo do mínimo",
    "less_than_equal": "valor acima do máximo",
    "decimal_max_places": "use no máximo 2 casas decimais",
    "decimal_max_digits": "valor grande demais",
}


def _frase_validacao(erro: ValidationError) -> str:
    frases = []
    for detalhe in erro.errors():
        campo = str(detalhe["loc"][0]) if detalhe["loc"] else ""
        if detalhe["type"] == "value_error":
            frases.append(detalhe["msg"].removeprefix("Value error, "))
        else:
            mensagem = _MENSAGENS_VALIDACAO.get(detalhe["type"], "valor inválido")
            frases.append(f"{_ROTULOS.get(campo, campo)}: {mensagem}")
    return "; ".join(frases)
