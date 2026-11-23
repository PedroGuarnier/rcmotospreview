"""Provedor de procedência: API da Consultar Placa (https://docs.consultarplaca.com.br).

São quatro consultas avulsas por placa, cada uma debitada dos créditos pré-pagos da conta.
A consulta básica (centavos) vai primeiro: se a placa não existe, para ali e não gasta as
outras três. A placa AAA0000 devolve dados fictícios sem consumir crédito.

O `detalhe` de cada item é para a equipe (o site público troca por uma frase genérica). O
retorno completo do provedor fica guardado em `bruto`, dentro do laudo.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx

from app.config import obter_config
from app.models import Veiculo
from app.procedencia import ITENS, ProcedenciaFalhou

URL = "https://api.consultarplaca.com.br/v2"
PLACA_DE_TESTE = "AAA0000"

_ROTA_CADASTRO = "consultarPlaca"
_ROTAS = {
    "roubo_furto": "consultarHistoricoRouboFurto",
    "leilao": "consultarRegistroLeilaoPrime",
    "renajud": "consultarRenajud",
}
# Quando há oferta de leilão o provedor processa imagens e pede espera de até 300 s.
_ESPERA = {"consultarRegistroLeilaoPrime": 300.0}
_ESPERA_PADRAO = 60.0

# tipo da falha -> (status HTTP da nossa API, mensagem para a tela)
_MENSAGENS = {
    "placa_invalida": (422, "A Consultar Placa recusou a placa. Confira a digitação."),
    "placa_nao_encontrada": (
        404,
        "Placa não encontrada no cadastro nacional. Confira a digitação; se estiver certa, "
        "tente de novo mais tarde.",
    ),
    "sem_credito": (
        503,
        "Os créditos da conta da loja na Consultar Placa acabaram. Recarregue no site deles "
        "para voltar a consultar.",
    ),
    "credenciais": (
        503,
        "A Consultar Placa recusou o acesso. Confira CONSULTARPLACA_EMAIL e "
        "CONSULTARPLACA_API_KEY.",
    ),
    "indisponivel": (
        502,
        "A Consultar Placa não respondeu agora. Tente de novo em alguns minutos.",
    ),
}
_NAO_VERIFICADO = {
    "sem_credito": "Não verificado: os créditos da conta no provedor acabaram.",
    "credenciais": "Não verificado: o provedor recusou o acesso.",
}
_NAO_VERIFICADO_PADRAO = "Não foi possível verificar agora. Refaça a consulta mais tarde."
_RESTRICOES = {"circulacao": "circulação", "transferencia": "transferência"}
_CLASSES_LEILAO = {
    "A": "sem dano (financeira ou banco)",
    "B": "pequenos danos (financeira ou banco)",
    "C": "danos acima de duas peças (seguradora ou órgão público)",
    "D": "danificado, sem mecânica funcionando",
}
_PARECER = {
    "registro_vistorias_negadas": "vistoria negada",
    "registro_frota_locadora": "frota de locadora",
    "registro_indicios_acidentes": "indícios de acidente",
    "registro_veiculo_importado": "veículo importado",
}


class _Falha(Exception):
    def __init__(self, tipo: str, mensagem: str = ""):
        super().__init__(tipo)
        self.tipo = tipo
        self.mensagem = mensagem


def configurado() -> bool:
    cfg = obter_config()
    return bool(cfg.consultarplaca_email.strip() and cfg.consultarplaca_api_key.strip())


def _cliente() -> httpx.Client:
    cfg = obter_config()
    return httpx.Client(
        base_url=URL, auth=(cfg.consultarplaca_email.strip(), cfg.consultarplaca_api_key.strip())
    )


def _chamar(cliente: httpx.Client, rota: str, placa: str) -> dict:
    try:
        resposta = cliente.get(
            f"/{rota}", params={"placa": placa}, timeout=_ESPERA.get(rota, _ESPERA_PADRAO)
        )
        corpo = resposta.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise _Falha("indisponivel") from exc
    if not isinstance(corpo, dict):
        raise _Falha("indisponivel")
    if resposta.status_code == 200 and corpo.get("status") == "ok":
        dados = corpo.get("dados")
        return dados if isinstance(dados, dict) else {}
    tipo = corpo.get("tipo_do_erro")
    if resposta.status_code in (401, 403):
        raise _Falha("credenciais")
    if resposta.status_code == 402 or tipo == "credito_insuficiente":
        raise _Falha("sem_credito")
    if tipo == "placa_nao_encontrada":
        raise _Falha("placa_nao_encontrada")
    if resposta.status_code == 400:
        raise _Falha("placa_invalida", str(corpo.get("mensagem") or ""))
    raise _Falha("indisponivel")


def _publica(falha: _Falha) -> ProcedenciaFalhou:
    status, mensagem = _MENSAGENS[falha.tipo]
    return ProcedenciaFalhou(falha.mensagem or mensagem, status)


def _sim(valor) -> bool | None:
    """'sim' -> True, 'nao' -> False; qualquer outra coisa ('indisponivel') -> None."""
    texto = str(valor or "").strip().lower()
    if texto == "sim":
        return True
    return False if texto in ("nao", "não") else None


def _inteiro(valor) -> int | None:
    try:
        return int(str(valor).strip())
    except ValueError:
        return None


def _quando(texto) -> datetime:
    try:
        return datetime.strptime(str(texto), "%d/%m/%Y")
    except ValueError:
        return datetime.min


def _lista(valor) -> list[dict]:
    return [x for x in valor if isinstance(x, dict)] if isinstance(valor, list) else []


def _tipo(texto: str) -> str | None:
    texto = texto.lower()
    if "moto" in texto or "ciclo" in texto:
        return "moto"
    if any(p in texto for p in ("auto", "camin", "camio", "utilit")):
        return "carro"
    return None


def _cadastro(dados: dict, veiculo: Veiculo | None) -> tuple[dict, tuple[str, str]]:
    info = dados.get("informacoes_veiculo") or {}
    v = info.get("dados_veiculo") or {}
    tecnicos = info.get("dados_tecnicos") or {}
    marca, modelo = str(v.get("marca") or "").strip(), str(v.get("modelo") or "").strip()
    descricao = {
        "marca_modelo": modelo if marca.lower() in modelo.lower() else f"{marca} {modelo}",
        "ano_fabricacao": _inteiro(v.get("ano_fabricacao")),
        "ano_modelo": _inteiro(v.get("ano_modelo")),
        "cor": str(v.get("cor") or "").strip() or None,
    }
    if v.get("municipio"):
        descricao["municipio"] = str(v["municipio"]).title()
        descricao["uf"] = str(v.get("uf_municipio") or "")
    if v.get("chassi"):
        descricao["chassi"] = str(v["chassi"]).upper()
    tipo = _tipo(f"{v.get('segmento')} {tecnicos.get('tipo_veiculo')}")
    if tipo:
        descricao["tipo"] = tipo

    if veiculo is None:
        return descricao, ("ok", "Placa localizada no cadastro nacional. Confira com o documento.")
    diferem = []
    if veiculo.chassi and descricao.get("chassi") and veiculo.chassi.upper() != descricao["chassi"]:
        diferem.append("chassi")
    for campo, rotulo in (("ano_fabricacao", "ano de fabricação"), ("ano_modelo", "ano do modelo")):
        if (
            getattr(veiculo, campo)
            and descricao[campo]
            and getattr(veiculo, campo) != descricao[campo]
        ):
            diferem.append(rotulo)
    if diferem:
        return descricao, (
            "atencao",
            f"Não confere com o cadastro da loja: {', '.join(diferem)}. Confira o documento.",
        )
    return descricao, ("ok", "Dados do cadastro nacional conferem com o cadastro da loja.")


def _roubo_furto(dados: dict) -> tuple[str, str] | None:
    bloco = (dados.get("historico_roubo_furto") or {}).get("registros_roubo_furto") or {}
    tem = _sim(bloco.get("possui_registro"))
    if tem is None:
        return None
    if not tem:
        return "ok", "Nada consta nas bases de roubo e furto."
    registros = sorted(
        _lista(bloco.get("registros")), key=lambda r: _quando(r.get("data_boletim_ocorrencia"))
    )
    if not registros:
        return "alerta", "Consta registro de roubo ou furto."
    resumo = "; ".join(
        f"{r.get('tipo_ocorrencia') or 'Ocorrência'} em {r.get('data_boletim_ocorrencia') or '?'}"
        + (f" ({r['uf_ocorrencia']})" if r.get("uf_ocorrencia") else "")
        for r in registros[-3:]
    )
    ultimo = str(registros[-1].get("tipo_ocorrencia") or "").lower()
    if "devolv" in ultimo or "recuper" in ultimo:
        return "atencao", f"Histórico de roubo ou furto já encerrado: {resumo}."
    return "alerta", f"Consta registro de roubo ou furto: {resumo}."


def _leilao(dados: dict) -> tuple[str, str] | None:
    leilao = dados.get("informacoes_sobre_leilao") or {}
    remarketing = dados.get("informacoes_sobre_remarketing") or {}
    tem = _sim(leilao.get("possui_registro"))
    if tem is None:
        return None
    if tem:
        classe = str((leilao.get("registro_sobre_oferta") or {}).get("classificacao") or "").upper()
        datas = sorted(
            {
                r["data_leilao"]
                for r in _lista((leilao.get("registro_leiloes") or {}).get("registros"))
                if r.get("data_leilao")
            },
            key=_quando,
        )
        texto = "Consta oferta em leilão" + (f" em {datas[-1]}" if datas else "")
        if classe in _CLASSES_LEILAO:
            texto += f". Classificação {classe}: {_CLASSES_LEILAO[classe]}"
        return ("alerta" if classe in ("C", "D") else "atencao"), texto + "."
    pontos = []
    if _sim((leilao.get("registro_sinistros_acidentes") or {}).get("possui_registro")):
        pontos.append("registro de sinistro ou acidente")
    detalhes = (leilao.get("parecer_tecnico") or {}).get("detalhes") or {}
    pontos += [rotulo for campo, rotulo in _PARECER.items() if _sim(detalhes.get(campo))]
    if _sim(remarketing.get("possui_registro")):
        pontos.append("oferta em venda entre lojistas (remarketing)")
    if pontos:
        return "atencao", f"Sem registro de leilão, mas consta: {', '.join(pontos)}."
    return "ok", "Sem registro de passagem por leilão."


def _renajud(dados: dict) -> tuple[str, str] | None:
    bloco = dados.get("registro_de_bloqueio_judicial_renajud") or {}
    tem = _sim(bloco.get("possui_bloqueio"))
    if tem is None:
        return None
    if not tem:
        return "ok", "Sem restrição judicial."
    tipos, processos = [], []
    for bloqueio in _lista(bloco.get("bloqueios")):
        nome = re.sub(r"^\d+\s*-\s*", "", str(bloqueio.get("tipo_restricao") or "")).strip().lower()
        nome = _RESTRICOES.get(nome, nome)
        if nome and nome not in tipos:
            tipos.append(nome)
        processo = " ".join(
            str(bloqueio[c]) for c in ("tribunal", "processo") if bloqueio.get(c)
        ).strip()
        if processo and processo not in processos:
            processos.append(processo)
    texto = "Restrição judicial ativa" + (f": {', '.join(tipos)}" if tipos else "")
    if processos:
        texto += f" (processo {'; '.join(processos)})"
    return "alerta", texto + "."


_LEITORES = {"roubo_furto": _roubo_furto, "leilao": _leilao, "renajud": _renajud}


def _enxugar(chave: str, dados: dict) -> dict:
    """Tira do retorno guardado o dicionário fixo de classificações de leilão (texto longo)."""
    if chave != "leilao":
        return dados
    leilao = dict(dados.get("informacoes_sobre_leilao") or {})
    oferta = dict(leilao.get("registro_sobre_oferta") or {})
    oferta.pop("dicionario_classificacoes", None)
    leilao["registro_sobre_oferta"] = oferta
    return {**dados, "informacoes_sobre_leilao": leilao}


def consultar(placa: str, veiculo: Veiculo | None) -> dict:
    with _cliente() as cliente:
        try:
            cadastro = _chamar(cliente, _ROTA_CADASTRO, placa)
        except _Falha as falha:
            raise _publica(falha) from falha
        with ThreadPoolExecutor(max_workers=len(_ROTAS)) as fila:
            pedidos = {
                chave: fila.submit(_chamar, cliente, rota, placa) for chave, rota in _ROTAS.items()
            }
    respostas: dict[str, dict] = {"cadastro": cadastro}
    falhas: dict[str, _Falha] = {}
    for chave, pedido in pedidos.items():
        try:
            respostas[chave] = pedido.result()
        except _Falha as falha:
            falhas[chave] = falha
    if len(falhas) == len(_ROTAS):
        # Nada além do cadastro voltou: não vale guardar um laudo vazio.
        raise _publica(next(iter(falhas.values())))

    descricao, resultado_cadastro = _cadastro(cadastro, veiculo)
    resultados: dict[str, tuple[str, str] | None] = {"cadastro": resultado_cadastro}
    for chave, leitor in _LEITORES.items():
        resultados[chave] = leitor(respostas[chave]) if chave in respostas else None

    itens = []
    for chave, titulo in ITENS:
        item = {"chave": chave, "titulo": titulo}
        if resultados[chave] is None:
            falha = falhas.get(chave)
            detalhe = _NAO_VERIFICADO.get(falha.tipo if falha else "", _NAO_VERIFICADO_PADRAO)
            item |= {"situacao": "atencao", "detalhe": detalhe, "pendente": True}
        else:
            item |= {"situacao": resultados[chave][0], "detalhe": resultados[chave][1]}
        itens.append(item)
    return {
        "veiculo": descricao,
        "itens": itens,
        "bruto": {chave: _enxugar(chave, dados) for chave, dados in respostas.items()},
        "ilustrativo": placa == PLACA_DE_TESTE,
    }
