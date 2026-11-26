"""Acha no banco o veículo e a pessoa de que a mensagem fala (venda e alteração por mensagem).

A frase dá pistas (placa, final da placa, marca, modelo, ano, cor); aqui elas viram a lista
de candidatos. Mais de um candidato vira pergunta: o assistente nunca escolhe sozinho.
"""

import re
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import schemas
from app.assistente import _moeda
from app.models import Situacao, Usuario, Veiculo, Venda

SITUACOES = {
    Situacao.compra: "compra",
    Situacao.documentacao: "documentação",
    Situacao.preparacao: "preparação",
    Situacao.a_venda: "à venda",
    Situacao.vendido: "vendido",
    Situacao.pos_venda: "pós-venda",
    Situacao.concluido: "concluído",
}
_CARGA = (
    selectinload(Veiculo.custos),
    selectinload(Veiculo.vendas).selectinload(Venda.cliente),
)
MAXIMO_DE_OPCOES = 8


def _normal(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normal(texto))


def _raiz_da_cor(cor: str) -> str:
    """ "Branca" e "branco" são a mesma cor."""
    palavras = _palavras(cor)
    return palavras[0].rstrip("ao") if palavras else ""


def _combina_modelo(procurado: str, veiculo: Veiculo) -> bool:
    """ "CG 160" acha "CG 160 Fan"; "MT-03" acha "MT 03"."""
    pedidas = _palavras(procurado)
    nome = _palavras(f"{veiculo.marca} {veiculo.modelo}")
    return set(pedidas) <= set(nome) or "".join(pedidas) in "".join(nome)


def obter(db: Session, veiculo_id: int) -> Veiculo | None:
    return db.scalar(select(Veiculo).where(Veiculo.id == veiculo_id).options(*_CARGA))


def obter_travado(db: Session, veiculo_id: int) -> Veiculo | None:
    consulta = (
        select(Veiculo).where(Veiculo.id == veiculo_id).options(*_CARGA).with_for_update(of=Veiculo)
    )
    return db.scalar(consulta)


def buscar_veiculos(
    db: Session, ref: dict[str, Any], situacoes: tuple[Situacao, ...]
) -> list[Veiculo]:
    """Veículos que combinam com a referência. Placa completa acha em qualquer etapa; o resto,
    só nas `situacoes` pedidas."""
    if ref.get("placa"):
        consulta = select(Veiculo).where(Veiculo.placa == ref["placa"]).options(*_CARGA)
        return list(db.scalars(consulta))
    consulta = (
        select(Veiculo)
        .where(Veiculo.situacao.in_(situacoes))
        .options(*_CARGA)
        .order_by(Veiculo.situacao_desde.desc(), Veiculo.id.desc())
    )
    if ref.get("placa_final"):
        consulta = consulta.where(Veiculo.placa.like(f"%{ref['placa_final']}"))
    achados = []
    for veiculo in db.scalars(consulta):
        if ref.get("tipo") and veiculo.tipo != ref["tipo"]:
            continue
        if ref.get("marca") and _normal(ref["marca"]) != _normal(veiculo.marca):
            continue
        if ref.get("modelo") and not _combina_modelo(ref["modelo"], veiculo):
            continue
        if ref.get("ano") and ref["ano"] not in (veiculo.ano_modelo, veiculo.ano_fabricacao):
            continue
        if ref.get("cor") and _raiz_da_cor(ref["cor"]) != _raiz_da_cor(veiculo.cor or ""):
            continue
        if ref.get("texto"):
            tudo = set(_palavras(f"{veiculo.marca} {veiculo.modelo} {veiculo.cor or ''}"))
            if not set(_palavras(ref["texto"])) <= tudo:
                continue
        achados.append(veiculo)
    return achados


def descrever_referencia(ref: dict[str, Any]) -> str:
    """O que a pessoa disse do veículo, para a frase "não encontrei ..."."""
    if ref.get("placa"):
        return f"veículo com a placa {placa_formatada(ref['placa'])}"
    partes = [ref.get("marca") if not ref.get("modelo") else None, ref.get("modelo")]
    partes += [str(ref["ano"]) if ref.get("ano") else None]
    partes += [ref["cor"].lower() if ref.get("cor") else None]
    partes += [ref.get("texto")]
    texto = " ".join(p for p in partes if p)
    if ref.get("placa_final"):
        texto = f"{texto} com placa final {ref['placa_final']}".strip()
    return texto or "esse veículo"


def placa_formatada(placa: str) -> str:
    return f"{placa[:3]}-{placa[3:]}"


def linha_do_veiculo(veiculo: Veiculo, com_preco: bool = True) -> str:
    """ "Honda Biz 125 2021 · branca · ABC-1D23 · R$ 9.900,00 (à venda)" """
    ano = f" {veiculo.ano_modelo}" if veiculo.ano_modelo else ""
    partes = [f"{veiculo.marca} {veiculo.modelo}{ano}"]
    if veiculo.cor:
        partes.append(veiculo.cor.lower())
    partes.append(placa_formatada(veiculo.placa) if veiculo.placa else "sem placa")
    if com_preco and veiculo.preco_venda is not None:
        partes.append(_moeda(veiculo.preco_venda))
    return " · ".join(partes) + f" ({SITUACOES[veiculo.situacao]})"


def lista_para_escolher(veiculos: list[Veiculo]) -> tuple[str, list[schemas.AssistenteOpcao]]:
    linhas = [f"{n}. {linha_do_veiculo(v)}" for n, v in enumerate(veiculos, start=1)]
    opcoes = [
        schemas.AssistenteOpcao(
            rotulo=f"{n}. {linha_do_veiculo(v, com_preco=False)}", mensagem=str(n)
        )
        for n, v in enumerate(veiculos, start=1)
    ]
    return "\n".join(linhas), opcoes


# ---------- Pessoas ----------


def _sem_parenteses(nome: str) -> str:
    return re.sub(r"\([^)]*\)", " ", nome)


def buscar_usuarios(db: Session, nome: str) -> list[Usuario]:
    """Usuários ativos cujo nome tem todas as palavras ditas ("Carlos", "carlos souza")."""
    pedidas = set(_palavras(nome))
    if not pedidas:
        return []
    ativos = db.scalars(select(Usuario).where(Usuario.ativo).order_by(Usuario.nome)).all()
    exatos = [u for u in ativos if _palavras(_sem_parenteses(u.nome)) == _palavras(nome)]
    if exatos:
        return exatos
    return [u for u in ativos if pedidas <= set(_palavras(_sem_parenteses(u.nome)))]


def usuarios_ativos(db: Session) -> list[Usuario]:
    return list(db.scalars(select(Usuario).where(Usuario.ativo).order_by(Usuario.nome)))


def escolha_na_lista(mensagem: str, quantos: int) -> int | None:
    """ "2", "o 2", "a segunda", "número 3": posição (1, 2, ...) numa lista mostrada."""
    texto = " ".join(_palavras(mensagem))
    ordinais = {
        "primeir": 1, "segund": 2, "terceir": 3, "quart": 4, "quint": 5, "sext": 6,
        "setim": 7, "oitav": 8, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
        "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
    }  # fmt: skip
    m = re.fullmatch(
        r"(?:(?:e |eh |foi |quero |escolho |pode ser )?(?:o |a |opcao |numero |n )*)"
        r"(\d{1,2}|primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|sext[oa]|setim[oa]|"
        r"oitav[oa]|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito)"
        r"(?: (?:opcao|da lista|mesmo|mesma|ai|por favor))*",
        texto,
    )
    if not m:
        return None
    escolha = m[1]
    numero = int(escolha) if escolha.isdigit() else ordinais.get(escolha.rstrip("oa"))
    if numero is None:
        numero = ordinais.get(escolha)
    return numero if numero and 1 <= numero <= quantos else None
