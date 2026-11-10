"""Consulta de procedência pela placa (roubo/furto, leilão, Renajud, dados cadastrais).

O provedor é trocável. Hoje existe só o de demonstração, que devolve dados ILUSTRATIVOS e
determinísticos para a interface poder ser mostrada e testada. O provedor nacional (ex.:
Infosimples) entra como mais uma função em `_PROVEDORES` quando a conta da loja existir —
ele precisa devolver o mesmo formato de `dados`.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import obter_config
from app.models import LaudoProcedencia, Semaforo, Usuario, Veiculo

# situação de cada item: "ok" | "atencao" | "alerta"
ITENS = (
    ("roubo_furto", "Roubo e furto"),
    ("leilao", "Leilão"),
    ("renajud", "Restrição judicial (Renajud)"),
    ("cadastro", "Dados cadastrais"),
)


class ProcedenciaIndisponivel(Exception):
    """Não há provedor configurado (ou ele não pode ser usado neste ambiente)."""


def provedor_ativo() -> str | None:
    cfg = obter_config()
    nome = cfg.procedencia_provedor.strip().lower()
    if not nome and cfg.dados_demo:
        nome = "demonstracao"
    if nome == "demonstracao" and cfg.producao:
        return None  # laudo ilustrativo nunca entra em produção
    return nome if nome in _PROVEDORES else None


def classificar(itens: list[dict]) -> Semaforo:
    situacoes = {item["situacao"] for item in itens}
    if "alerta" in situacoes:
        return Semaforo.vermelho
    if "atencao" in situacoes:
        return Semaforo.amarelo
    return Semaforo.verde


def _demonstracao(placa: str, veiculo: Veiculo | None) -> dict:
    """Dados ilustrativos. Placas terminadas em 3 mostram atenção; em 7, alerta."""
    final = placa[-1]
    itens = {
        "roubo_furto": ("ok", "Nada consta nas bases de roubo e furto."),
        "leilao": ("ok", "Sem registro de passagem por leilão."),
        "renajud": ("ok", "Sem restrição judicial."),
        "cadastro": ("ok", "Marca, modelo, ano e cor conferem com o documento."),
    }
    if final == "3":
        itens["leilao"] = ("atencao", "Consta passagem por leilão em 2019 (financeira).")
    elif final == "7":
        itens["renajud"] = ("alerta", "Restrição judicial ativa: circulação e transferência.")
    if veiculo is not None:
        descricao = {
            "marca_modelo": f"{veiculo.marca} {veiculo.modelo}",
            "ano_fabricacao": veiculo.ano_fabricacao,
            "ano_modelo": veiculo.ano_modelo,
            "cor": veiculo.cor,
            "tipo": veiculo.tipo.value,
        }
    else:
        descricao = {
            "marca_modelo": "Veículo ilustrativo",
            "ano_fabricacao": 2021,
            "ano_modelo": 2022,
            "cor": "Prata",
            "tipo": "moto",
        }
    return {
        "veiculo": {**descricao, "municipio": "Teresina", "uf": "PI"},
        "itens": [
            {
                "chave": chave,
                "titulo": titulo,
                "situacao": itens[chave][0],
                "detalhe": itens[chave][1],
            }
            for chave, titulo in ITENS
        ],
    }


_PROVEDORES = {"demonstracao": _demonstracao}


def consultar(db: Session, placa: str, usuario: Usuario) -> LaudoProcedencia:
    """Consulta o provedor e guarda o laudo (ligado ao veículo, se a placa já está no estoque)."""
    nome = provedor_ativo()
    if nome is None:
        raise ProcedenciaIndisponivel
    veiculo = db.scalar(select(Veiculo).where(Veiculo.placa == placa))
    dados = _PROVEDORES[nome](placa, veiculo)
    dados["consultado_em"] = datetime.now(UTC).isoformat()
    laudo = LaudoProcedencia(
        veiculo=veiculo,
        placa=placa,
        provedor=nome,
        ilustrativo=nome == "demonstracao",
        semaforo=classificar(dados["itens"]),
        dados=dados,
        consultado_por_id=usuario.id,
    )
    db.add(laudo)
    return laudo


def ligar_laudos_ao_veiculo(db: Session, veiculo: Veiculo) -> None:
    """Placa consultada antes da compra: ao cadastrar o veículo, os laudos passam a ser dele."""
    if not veiculo.placa:
        return
    soltos = db.scalars(
        select(LaudoProcedencia).where(
            LaudoProcedencia.placa == veiculo.placa, LaudoProcedencia.veiculo_id.is_(None)
        )
    )
    for laudo in soltos:
        laudo.veiculo = veiculo
