"""IA de perguntas sobre o negócio: ferramentas, permissões, laço de tool use, provedores
(Groq e Anthropic) e roteamento.

Nenhum teste usa a rede: o provedor é injetado (`provedores.provedor_ia`) com transporte
falso — `httpx.MockTransport` para o Groq e o equivalente do SDK para a Anthropic — e as
respostas são roteirizadas no formato de cada API (pedido de ferramenta → resultado → texto).
"""

import json
import logging
from datetime import UTC, datetime, timedelta

import anthropic
import httpx
import httpx2
import pytest
from sqlalchemy import func, select

from app.config import obter_config
from app.ia import agente, ferramentas, provedores
from app.main import app
from app.models import Aporte, AuditLog, Perfil, Usuario, Veiculo
from tests.conftest import cliente_logado, criar_usuario, nova_venda, novo_veiculo
from tests.test_assistente_conversa import FRASE, Conversa, ficha

# ---------------------------------------------------------------------------------------
# Groq falso (formato OpenAI)
# ---------------------------------------------------------------------------------------

USO = {"prompt_tokens": 1200, "completion_tokens": 80}


def texto(t: str) -> dict:
    mensagem = {"role": "assistant", "content": t, "reasoning": "raciocínio interno"}
    return {"choices": [{"message": mensagem, "finish_reason": "stop"}], "usage": USO}


def pedir(*chamadas: tuple[str, dict] | tuple[str, dict, str]) -> dict:
    tool_calls = [
        {
            "id": c[2] if len(c) > 2 else f"call_{i}",
            "type": "function",
            "function": {"name": c[0], "arguments": json.dumps(c[1])},
        }
        for i, c in enumerate(chamadas)
    ]
    mensagem = {
        "role": "assistant",
        "content": None,
        "reasoning": "raciocínio interno",
        "tool_calls": tool_calls,
    }
    return {"choices": [{"message": mensagem, "finish_reason": "tool_calls"}], "usage": USO}


def erro_http(codigo: int, code: str = "erro") -> httpx.Response:
    return httpx.Response(codigo, json={"error": {"message": "falhou", "code": code}})


class GroqFalso:
    """Responde `/openai/v1/chat/completions` com o roteiro e guarda os corpos enviados."""

    def __init__(self):
        self.roteiro: list = []
        self.corpos: list[dict] = []
        self.cabecalhos: list[httpx.Headers] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        assert pedido.url == provedores.GROQ_URL
        self.corpos.append(json.loads(pedido.content))
        self.cabecalhos.append(pedido.headers)
        proxima = self.roteiro.pop(0) if self.roteiro else texto("(fim do roteiro)")
        if isinstance(proxima, Exception):
            raise proxima
        if isinstance(proxima, httpx.Response):
            return proxima
        return httpx.Response(200, json=proxima)

    def resultados(self, chamada: int = -1) -> list[dict]:
        """Mensagens `role: tool` enviadas na chamada indicada (a última, por padrão)."""
        mensagens = self.corpos[chamada]["messages"]
        ultima_do_modelo = max(i for i, m in enumerate(mensagens) if m["role"] == "assistant")
        return [m for m in mensagens[ultima_do_modelo + 1 :] if m["role"] == "tool"]

    def resultado(self, chamada: int = -1) -> dict:
        return json.loads(self.resultados(chamada)[0]["content"])

    def ferramentas_oferecidas(self) -> list[str]:
        return [t["function"]["name"] for t in self.corpos[0]["tools"]]

    def sistema(self, chamada: int = 0) -> str:
        return self.corpos[chamada]["messages"][0]["content"]


@pytest.fixture
def ia():
    """Liga a IA com o adaptador do Groq sobre um transporte falso."""
    falso = GroqFalso()
    http = httpx.Client(transport=httpx.MockTransport(falso))
    provedor = provedores.Groq("chave-falsa", "openai/gpt-oss-120b", http)
    app.dependency_overrides[provedores.provedor_ia] = lambda: provedor
    yield falso
    app.dependency_overrides.pop(provedores.provedor_ia, None)


def perguntar(api, mensagem: str, estado=None) -> dict:
    r = api.post("/assistente/mensagem", json={"mensagem": mensagem, "estado": estado})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------------------
# Dados: duas vendas em outubro (uma do vendedor), uma em setembro, dois no estoque
# ---------------------------------------------------------------------------------------


@pytest.fixture
def loja(dono, usuario_vendedor):
    cg = novo_veiculo(dono)  # moto, compra 11.500
    uno = novo_veiculo(
        dono,
        tipo="carro",
        marca="Fiat",
        modelo="Uno Way",
        placa="QWE1R23",
        valor_compra="24000.00",
        preco_venda="31900.00",
    )
    biz = novo_veiculo(dono, marca="Honda", modelo="Biz 125", placa="BIZ1A25", valor_compra="9000")
    novo_veiculo(dono, marca="Yamaha", modelo="Fazer 250", placa="FAZ2B50", valor_compra="15000")
    novo_veiculo(dono, marca="Honda", modelo="Pop 110i", placa="POP1C10", situacao="compra")
    nova_venda(
        dono, cg["id"], valor="14500.00", data_venda="2026-10-05", vendedor_id=usuario_vendedor.id
    )
    nova_venda(dono, uno["id"], valor="31000.00", data_venda="2026-10-20")
    nova_venda(dono, biz["id"], valor="12000.00", data_venda="2026-09-10")
    return dono


def usuario(db, perfil: Perfil) -> Usuario:
    return db.scalar(select(Usuario).where(Usuario.perfil == perfil))


def rodar(db, quem: Usuario, nome: str, entrada: dict) -> tuple[dict, bool]:
    conteudo, erro = ferramentas.executar(db, quem, nome, entrada)
    return json.loads(conteudo), erro


OUTUBRO = {"inicio": "2026-10-01", "fim": "2026-10-31"}


def chaves(dados) -> set[str]:
    """Todas as chaves de um JSON aninhado."""
    if isinstance(dados, dict):
        return set(dados) | set().union(*(chaves(v) for v in dados.values()))
    if isinstance(dados, list):
        return set().union(*(chaves(v) for v in dados)) if dados else set()
    return set()


# ---------------------------------------------------------------------------------------
# Ferramentas e permissões
# ---------------------------------------------------------------------------------------


def test_vendas_do_dono_com_lucro_e_divisoes(loja, db):
    dados, erro = rodar(db, usuario(db, Perfil.dono), "consultar_vendas", OUTUBRO)
    assert not erro
    assert dados["periodo"] == "01/10/2026 a 31/10/2026"
    assert dados["escopo"] == "todas as vendas da loja"
    assert dados["vendas"] == 2
    assert dados["faturamento"] == "R$ 45.500,00"
    assert dados["ticket_medio"] == "R$ 22.750,00"
    assert dados["lucro"] == "R$ 10.000,00"  # (14.500 − 11.500) + (31.000 − 24.000)
    assert dados["por_tipo"]["moto"]["vendas"] == 1
    assert dados["por_tipo"]["carro"]["faturamento"] == "R$ 31.000,00"
    assert dados["por_forma_pagamento"] == {"à vista": {"vendas": 2, "faturamento": "R$ 45.500,00"}}
    assert {v["vendedor"] for v in dados["por_vendedor"]} == {"Dono", "Vendedor"}
    assert [v["data"] for v in dados["lista"]] == ["20/10/2026", "05/10/2026"]

    so_motos, _ = rodar(
        db, usuario(db, Perfil.dono), "consultar_vendas", {**OUTUBRO, "tipo": "moto"}
    )
    assert so_motos["vendas"] == 1 and list(so_motos["por_tipo"]) == ["moto"]
    do_vendedor, _ = rodar(
        db, usuario(db, Perfil.dono), "consultar_vendas", {**OUTUBRO, "vendedor": "vend"}
    )
    assert do_vendedor["vendas"] == 1 and do_vendedor["faturamento"] == "R$ 14.500,00"


def test_vendedor_ve_so_as_proprias_vendas_e_sem_lucro(loja, db):
    vendedor = usuario(db, Perfil.vendedor)
    # mesmo pedindo as vendas do dono, recebe só as próprias
    dados, erro = rodar(db, vendedor, "consultar_vendas", {**OUTUBRO, "vendedor": "Dono"})
    assert not erro
    assert dados["escopo"] == "só as vendas de quem pergunta"
    assert dados["vendas"] == 1 and dados["faturamento"] == "R$ 14.500,00"
    assert not chaves(dados) & {"lucro", "lucro_liquido", "imposto_estimado", "por_vendedor"}


def test_financeiro_ve_todas_as_vendas_mas_sem_custos(loja, db):
    criar_usuario(Perfil.financeiro)
    dados, _ = rodar(db, usuario(db, Perfil.financeiro), "consultar_vendas", OUTUBRO)
    assert dados["vendas"] == 2 and dados["faturamento"] == "R$ 45.500,00"
    assert not chaves(dados) & {"lucro", "lucro_liquido", "imposto_estimado"}


def test_periodo_invalido_volta_como_erro_da_ferramenta(loja, db):
    dono = usuario(db, Perfil.dono)
    dados, erro = rodar(db, dono, "consultar_vendas", {"inicio": "2026-10-31", "fim": "2026-10-01"})
    assert erro and "anterior" in dados["erro"]
    dados, erro = rodar(db, dono, "consultar_vendas", {"inicio": "outubro", "fim": "2026-10-01"})
    assert erro and "AAAA-MM-DD" in dados["erro"]
    dados, erro = rodar(db, dono, "consultar_comissoes", {"mes": "2026-13"})
    assert erro and "AAAA-MM" in dados["erro"]
    dados, erro = rodar(db, dono, "nao_existe", {})
    assert erro and "indisponível" in dados["erro"]


def test_estoque_por_perfil_busca_e_parados(loja, db):
    dono, vendedor = usuario(db, Perfil.dono), usuario(db, Perfil.vendedor)
    dados, _ = rodar(db, dono, "consultar_estoque", {})
    assert dados["quantidade"] == 2  # Fazer à venda e Pop em compra
    assert dados["por_situacao"] == {"à venda": 1, "compra": 1}
    assert dados["investido_compra_mais_custos"] == "R$ 26.500,00"
    assert dados["valor_anunciado_a_venda"] == "R$ 14.900,00"
    assert "custo_total" in dados["lista"][0]

    dados, _ = rodar(db, vendedor, "consultar_estoque", {})
    assert dados["quantidade"] == 2
    assert not chaves(dados) & {"custo_total", "lucro_previsto", "investido_compra_mais_custos"}

    dados, _ = rodar(db, vendedor, "consultar_estoque", {"busca": "FAZ-2B50"})
    assert [v["veiculo"] for v in dados["lista"]] == ["Yamaha Fazer 250 2022 (FAZ2B50)"]
    dados, _ = rodar(db, dono, "consultar_estoque", {"grupo": "vendidos", "tipo": "carro"})
    assert dados["quantidade"] == 1 and dados["lista"][0]["situacao"] == "vendido"

    fazer = db.scalar(select(Veiculo).where(Veiculo.placa == "FAZ2B50"))
    fazer.situacao_desde = datetime.now(UTC) - timedelta(days=60)
    db.commit()
    dados, _ = rodar(db, dono, "consultar_estoque", {"parado_ha_dias": 45})
    assert dados["quantidade"] == 1 and dados["lista"][0]["dias_na_situacao"] == 60


def test_comissoes_vendedor_ve_so_as_proprias(loja, db, gerente):
    vendedor = usuario(db, Perfil.vendedor)
    outro = criar_usuario(
        Perfil.vendedor, "outro@teste.com", nome="Outro", comissao_regra="valor_fixo",
        comissao_valor=500,
    )  # fmt: skip
    pop = db.scalar(select(Veiculo).where(Veiculo.placa == "POP1C10"))
    gerente.patch(f"/veiculos/{pop.id}", json={"situacao": "a_venda"})
    nova_venda(gerente, pop.id, valor="9000.00", data_venda="2026-10-25", vendedor_id=outro.id)

    dados, _ = rodar(db, vendedor, "consultar_comissoes", {"mes": "2026-10"})
    assert dados["escopo"] == "só as comissões de quem pergunta"
    assert dados["total"] == "R$ 300,00"  # 10% de 3.000 de lucro
    assert {v["vendedor"] for v in dados["por_vendedor"]} == {"Vendedor"}
    assert {c["vendedor"] for c in dados["lista"]} == {"Vendedor"}

    dados, _ = rodar(db, usuario(db, Perfil.gerente), "consultar_comissoes", {"mes": "2026-10"})
    assert dados["total"] == "R$ 800,00"
    assert {v["vendedor"] for v in dados["por_vendedor"]} == {"Vendedor", "Outro"}


def test_painel_e_aportes_so_para_quem_pode(loja, db):
    dono, vendedor = usuario(db, Perfil.dono), usuario(db, Perfil.vendedor)
    db.add(Aporte(data=datetime(2026, 10, 2).date(), valor=5000, descricao="Capital de giro"))
    db.commit()

    dados, erro = rodar(db, dono, "consultar_painel", {})
    assert not erro and dados["estoque"]["em_estoque"] == 2
    assert "capital_investido" in dados["estoque"]
    dados, erro = rodar(db, dono, "consultar_aportes", OUTUBRO)
    assert not erro and dados["total"] == "R$ 5.000,00" and dados["quantidade"] == 1

    for nome in ("consultar_painel", "consultar_aportes"):
        dados, erro = rodar(db, vendedor, nome, {})
        assert erro and "erro" in dados and "total" not in dados

    criar_usuario(Perfil.gerente)  # gerente sem aportes habilitados
    gerente = usuario(db, Perfil.gerente)
    assert rodar(db, gerente, "consultar_aportes", {})[1] is True
    gerente.acesso_aportes = True  # o dono habilitou
    db.commit()
    assert rodar(db, gerente, "consultar_aportes", {})[1] is False


def test_ferramentas_oferecidas_por_perfil(db):
    nomes = {
        perfil: [f.nome for f in ferramentas.disponiveis(criar_usuario(perfil))]
        for perfil in Perfil
    }
    todas = [f.nome for f in ferramentas.FERRAMENTAS]
    assert nomes[Perfil.dono] == todas
    assert "consultar_painel" in nomes[Perfil.gerente]
    assert "consultar_aportes" not in nomes[Perfil.gerente]
    sem_painel = ["consultar_vendas", "consultar_estoque", "consultar_comissoes"]
    assert nomes[Perfil.financeiro] == sem_painel
    assert nomes[Perfil.vendedor] == sem_painel


# ---------------------------------------------------------------------------------------
# Laço de tool use pela rota (adaptador do Groq)
# ---------------------------------------------------------------------------------------


def test_pergunta_usa_ferramenta_e_responde(loja, ia, caplog):
    caplog.set_level(logging.INFO, logger="rcmotos.ia")
    ia.roteiro = [
        pedir(("consultar_vendas", {**OUTUBRO, "tipo": "moto"}, "call_a")),
        texto("Em outubro de 2026 vocês venderam **1 moto**, por R$ 14.500,00."),
    ]
    r = perguntar(loja, "quantas motos vendemos em outubro?")
    assert r["resposta"] == "Em outubro de 2026 vocês venderam 1 moto, por R$ 14.500,00."
    assert "raciocínio" not in r["resposta"]
    assert r["origem"] == "ia" and r["acao"] == "nenhuma" and r["ficha"] == []
    assert r["estado"]["historico"] == [
        {"pergunta": "quantas motos vendemos em outubro?", "resposta": r["resposta"]}
    ]

    primeira = ia.corpos[0]
    assert ia.cabecalhos[0]["authorization"] == "Bearer chave-falsa"
    assert primeira["model"] == "openai/gpt-oss-120b"
    assert primeira["max_completion_tokens"] <= 2048
    assert primeira["reasoning_effort"] == "low" and primeira["tool_choice"] == "auto"
    assert [m["role"] for m in primeira["messages"]] == ["system", "user"]
    assert primeira["messages"][1]["content"] == "quantas motos vendemos em outubro?"
    assert "Hoje é" in ia.sistema() and "perfil dono" in ia.sistema()
    assert ia.ferramentas_oferecidas() == [f.nome for f in ferramentas.FERRAMENTAS]
    vendas = primeira["tools"][0]["function"]
    assert vendas["parameters"]["required"] == ["inicio", "fim"]

    # o pedido volta com o raciocínio (só dentro desta pergunta), seguido do resultado
    modelo = ia.corpos[1]["messages"][-2]
    assert modelo["role"] == "assistant" and modelo["reasoning"] == "raciocínio interno"
    assert modelo["tool_calls"][0]["id"] == "call_a"
    (resultado,) = ia.resultados()
    assert resultado["tool_call_id"] == "call_a"
    assert ia.resultado()["vendas"] == 1

    registro = next(m for m in caplog.messages if m.startswith("IA pergunta"))
    assert "provedor=groq" in registro and "modelo=openai/gpt-oss-120b" in registro
    assert "rodadas=2" in registro and "tokens_entrada=2400" in registro
    assert "tokens_saida=160" in registro and "ferramentas=consultar_vendas" in registro
    assert "tempo=" in registro


def test_pergunta_de_seguimento_leva_o_historico(loja, ia):
    ia.roteiro = [texto("Em outubro de 2026 foram 2 vendas."), texto("Em setembro, 1 venda.")]
    r1 = perguntar(loja, "quantas vendas em outubro?")
    r2 = perguntar(loja, "e em setembro?", r1["estado"])
    assert r2["resposta"] == "Em setembro, 1 venda."
    assert ia.corpos[1]["messages"][1:] == [  # sem raciocínio nem aviso entre perguntas
        {"role": "user", "content": "quantas vendas em outubro?"},
        {"role": "assistant", "content": "Em outubro de 2026 foram 2 vendas."},
        {"role": "user", "content": "e em setembro?"},
    ]
    assert len(r2["estado"]["historico"]) == 2


def test_historico_guarda_so_as_ultimas_trocas(dono, ia):
    estado = {"historico": [{"pergunta": f"p{i}", "resposta": f"r{i}"} for i in range(6)]}
    ia.roteiro = [texto("ok")]
    r = perguntar(dono, "qual o faturamento do mês?", estado)
    historico = r["estado"]["historico"]
    assert len(historico) == 6
    assert historico[0]["pergunta"] == "p1" and historico[-1]["resposta"] == "ok"


@pytest.mark.parametrize(
    "historico",
    [
        [{"pergunta": f"p{i}", "resposta": f"r{i}"} for i in range(7)],  # trocas demais
        [{"pergunta": "p", "resposta": "x" * 2001}],  # resposta longa demais
        [{"pergunta": "x" * 1001, "resposta": "r"}],
        [{"pergunta": "p"}],
        [{"pergunta": "", "resposta": "r"}],
        "não é lista",
    ],
)
def test_historico_adulterado_da_422(dono, ia, historico):
    r = dono.post(
        "/assistente/mensagem",
        json={"mensagem": "quanto vendemos?", "estado": {"historico": historico}},
    )
    assert r.status_code == 422
    assert ia.corpos == []


def test_vendedor_pergunta_e_ferramentas_respeitam_o_perfil(loja, ia, usuario_vendedor):
    vendedor = cliente_logado(usuario_vendedor)
    ia.roteiro = [
        pedir(
            ("consultar_vendas", OUTUBRO, "call_a"),
            ("consultar_aportes", {}, "call_b"),  # não oferecida: o modelo inventou
        ),
        texto("Em outubro você vendeu 1 moto."),
    ]
    r = perguntar(vendedor, "quanto eu vendi em outubro?")
    assert r["resposta"] == "Em outubro você vendeu 1 moto." and r["origem"] == "ia"
    assert ia.ferramentas_oferecidas() == [
        "consultar_vendas",
        "consultar_estoque",
        "consultar_comissoes",
    ]
    assert "perfil vendedor" in ia.sistema()
    vendas, aportes = ia.resultados()
    assert json.loads(vendas["content"])["vendas"] == 1
    assert "lucro" not in json.loads(vendas["content"])
    assert "erro" in json.loads(aportes["content"]) and "total" not in aportes["content"]


def test_argumentos_invalidos_voltam_como_erro_para_o_modelo(dono, ia):
    chamada = pedir(("consultar_estoque", {}, "call_x"))
    chamada["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "{quebrado"
    ia.roteiro = [chamada, texto("Não consegui consultar.")]
    perguntar(dono, "quantas motos temos?")
    assert "inválidos" in ia.resultado()["erro"]


def test_sem_acao_por_mensagem_e_sem_ia_o_assistente_continua_fechado(financeiro, vendedor):
    r = financeiro.post("/assistente/mensagem", json={"mensagem": "quanto vendemos?"})
    assert r.status_code == 403
    # o vendedor registra venda por mensagem: o assistente abre, a pergunta fica sem IA
    r = vendedor.post("/assistente/mensagem", json={"mensagem": "quanto vendemos?"})
    assert r.status_code == 200 and r.json()["origem"] == "regras"


def test_financeiro_pergunta_com_a_ia_ligada(financeiro, ia):
    ia.roteiro = [texto("Não há vendas neste mês.")]
    r = perguntar(financeiro, "quanto faturamos este mês?")
    assert r["resposta"] == "Não há vendas neste mês." and r["origem"] == "ia"
    ia.roteiro = [texto("Quem cuida do estoque faz o cadastro.")]
    r = perguntar(financeiro, "chegou uma biz 125 2021, comprei por 9 mil")
    assert r["ficha"] == [] and r["acao"] == "nenhuma"  # não cadastra, nem rascunho
    assert "não cadastra veículo" in ia.sistema(1)


def test_limite_de_rodadas(dono, ia):
    ia.roteiro = [pedir(("consultar_estoque", {}, f"call_{i}")) for i in range(10)]
    r = perguntar(dono, "quantas motos temos?")
    assert len(ia.corpos) == agente.MAX_RODADAS
    assert r["resposta"] == agente.SEM_RESPOSTA
    assert r["estado"]["historico"] == []  # falha não vira contexto


def test_resposta_vazia_e_cortada(dono, ia):
    ia.roteiro = [texto("")]
    assert perguntar(dono, "qual o lucro do mês?")["resposta"] == agente.SEM_RESPOSTA
    cortada = texto("O lucro de novembro foi")
    cortada["choices"][0]["finish_reason"] = "length"
    ia.roteiro = [cortada]
    assert perguntar(dono, "qual o lucro do mês?")["resposta"] == "O lucro de novembro foi…"


@pytest.mark.parametrize(
    ("falha", "trecho"),
    [
        (erro_http(429, "rate_limit_exceeded"), "Muitas perguntas seguidas"),
        (erro_http(401, "invalid_api_key"), "chave de acesso"),
        (erro_http(503), "fora do ar"),
        (erro_http(498, "capacity_exceeded"), "fora do ar"),
        (erro_http(400, "tool_use_failed"), "problema na IA"),
        (httpx.Response(200, text="não é json"), "problema na IA"),
        (httpx.ReadTimeout("lento"), "demorou demais"),
        (httpx.ConnectError("sem rede"), "falha de conexão"),
    ],
)
def test_erro_do_groq_vira_resposta_amigavel(dono, ia, falha, trecho):
    ia.roteiro = [falha]
    r = perguntar(dono, "quantas motos vendemos em outubro?")
    assert trecho in r["resposta"]
    assert r["acao"] == "nenhuma" and r["estado"]["historico"] == []


def test_erro_no_meio_do_laco_tambem_vira_frase(loja, ia):
    ia.roteiro = [pedir(("consultar_vendas", OUTUBRO)), erro_http(429)]
    r = perguntar(loja, "quanto vendemos em outubro?")
    assert "Muitas perguntas seguidas" in r["resposta"]


def test_erro_inesperado_vira_frase(dono, ia, monkeypatch):
    def quebra(*_):
        raise RuntimeError("bug")

    monkeypatch.setattr(ferramentas, "executar", quebra)
    ia.roteiro = [pedir(("consultar_estoque", {}))]
    assert "problema na IA" in perguntar(dono, "quantas motos temos?")["resposta"]


def test_dados_de_demonstracao_sao_avisados(dono, ia, monkeypatch):
    monkeypatch.setattr(obter_config(), "dados_demo", True)
    ia.roteiro = [texto("Foram 2 vendas.")]
    r = perguntar(dono, "quantas vendas este mês?")
    assert r["resposta"] == f"Foram 2 vendas.\n{agente.AVISO_DEMO}"
    # o histórico guarda só a resposta, sem o aviso
    assert r["estado"]["historico"][0]["resposta"] == "Foram 2 vendas."


def test_pergunta_nao_vai_para_o_historico_de_acoes(loja, ia, db):
    antes = db.scalar(select(func.count(AuditLog.id)))
    ia.roteiro = [pedir(("consultar_estoque", {})), texto("Há 2 veículos no estoque.")]
    perguntar(loja, "quantos veículos temos no estoque?")
    assert db.scalar(select(func.count(AuditLog.id))) == antes


# ---------------------------------------------------------------------------------------
# Adaptador da Anthropic (SDK com transporte falso)
# ---------------------------------------------------------------------------------------


def _msg(*conteudo, stop: str = "end_turn") -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": list(conteudo),
        "stop_reason": stop,
        "stop_sequence": None,
        "usage": {
            "input_tokens": 300,
            "output_tokens": 40,
            "cache_read_input_tokens": 900,
            "cache_creation_input_tokens": 0,
        },
    }


PENSOU = {"type": "thinking", "thinking": "", "signature": "assinatura"}


@pytest.fixture
def claude():
    """Liga a IA com o adaptador da Anthropic; o roteiro são respostas da Messages API."""
    estado = {"roteiro": [], "corpos": []}

    def responder(pedido: httpx2.Request) -> httpx2.Response:
        estado["corpos"].append(json.loads(pedido.content))
        proxima = estado["roteiro"].pop(0)
        if isinstance(proxima, httpx2.Response):
            return proxima
        return httpx2.Response(200, json=proxima)

    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(responder))
    cliente = anthropic.Anthropic(api_key="chave-falsa", http_client=http, max_retries=0)
    provedor = provedores.Anthropic(cliente, "claude-haiku-5-5")
    app.dependency_overrides[provedores.provedor_ia] = lambda: provedor
    yield estado
    app.dependency_overrides.pop(provedores.provedor_ia, None)


def test_anthropic_laco_completo(loja, claude, caplog):
    caplog.set_level(logging.INFO, logger="rcmotos.ia")
    claude["roteiro"] = [
        _msg(
            PENSOU,
            {"type": "tool_use", "id": "toolu_1", "name": "consultar_vendas", "input": OUTUBRO},
            stop="tool_use",
        ),
        _msg({"type": "text", "text": "Em outubro de 2026 foram 2 vendas."}),
    ]
    r = perguntar(loja, "quantas vendas em outubro?")
    assert r["resposta"] == "Em outubro de 2026 foram 2 vendas." and r["origem"] == "ia"

    primeira, segunda = claude["corpos"]
    assert primeira["model"] == "claude-haiku-5-5" and primeira["max_tokens"] <= 2048
    assert primeira["output_config"] == {"effort": "medium"}
    # Haiku 5.5: sem budget_tokens, sem temperature/top_p e sem prefill do assistente
    assert not {"thinking", "temperature", "top_p", "top_k"} & set(primeira)
    assert primeira["messages"] == [{"role": "user", "content": "quantas vendas em outubro?"}]
    assert primeira["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "perfil dono" in primeira["system"][1]["text"]
    assert primeira["tools"][0]["input_schema"]["required"] == ["inicio", "fim"]
    # o raciocínio volta sem mudança, seguido do tool_result
    assert segunda["messages"][1]["content"][0] == PENSOU
    resultado = segunda["messages"][2]["content"][0]
    assert resultado["type"] == "tool_result" and resultado["tool_use_id"] == "toolu_1"
    assert json.loads(resultado["content"])["vendas"] == 2

    registro = next(m for m in caplog.messages if m.startswith("IA pergunta"))
    assert "provedor=anthropic" in registro and "cache_lida=1800" in registro


@pytest.mark.parametrize(
    ("codigo", "corpo", "trecho"),
    [
        (429, {"type": "rate_limit_error"}, "Muitas perguntas seguidas"),
        (402, {"type": "billing_error"}, "sem crédito"),
        (400, {"type": "invalid_request_error", "message": "Your credit balance is too low"},
         "sem crédito"),
        (401, {"type": "authentication_error"}, "chave de acesso"),
        (529, {"type": "overloaded_error"}, "fora do ar"),
        (404, {"type": "not_found_error"}, "problema na IA"),
    ],
)  # fmt: skip
def test_anthropic_erros_viram_frase(dono, claude, codigo, corpo, trecho):
    claude["roteiro"] = [
        httpx2.Response(codigo, json={"type": "error", "error": {"message": "x", **corpo}})
    ]
    assert trecho in perguntar(dono, "quantas vendas em outubro?")["resposta"]


def test_anthropic_recusa_vira_frase(dono, claude):
    claude["roteiro"] = [_msg(stop="refusal")]
    r = perguntar(dono, "qual o lucro do mês?")
    assert r["resposta"] == agente.RECUSA and r["estado"]["historico"] == []


# ---------------------------------------------------------------------------------------
# Escolha do provedor pela configuração
# ---------------------------------------------------------------------------------------


def test_provedor_pela_configuracao(monkeypatch):
    cfg = obter_config()
    assert cfg.ia_provedor == "groq" and provedores.provedor_ia() is None
    assert not provedores.ia_ligada()

    monkeypatch.setattr(cfg, "groq_api_key", "chave-groq")
    groq = provedores.provedor_ia()
    assert isinstance(groq, provedores.Groq) and groq.modelo == "openai/gpt-oss-120b"
    monkeypatch.setattr(cfg, "ia_modelo", "qwen/qwen3.8-27b")
    assert provedores.provedor_ia().modelo == "qwen/qwen3.8-27b"

    monkeypatch.setattr(cfg, "ia_modelo", "")
    monkeypatch.setattr(cfg, "ia_provedor", "anthropic")
    assert provedores.provedor_ia() is None  # a chave do Groq não liga a Anthropic
    monkeypatch.setattr(cfg, "anthropic_api_key", "chave-anthropic")
    claude = provedores.provedor_ia()  # só cria o cliente: nenhuma chamada
    assert isinstance(claude, provedores.Anthropic) and claude.modelo == "claude-haiku-5-5"


def test_eu_diz_se_a_ia_esta_ligada(dono, monkeypatch):
    assert dono.get("/auth/eu").json()["ia_ligada"] is False
    monkeypatch.setattr(obter_config(), "groq_api_key", "chave-de-teste")
    assert dono.get("/auth/eu").json()["ia_ligada"] is True


# ---------------------------------------------------------------------------------------
# Roteamento: o motor de regras decide primeiro; o cadastro não muda
# ---------------------------------------------------------------------------------------


def test_sem_chave_diz_que_perguntas_estao_desligadas_e_cadastra(dono):
    conversa = Conversa(dono)
    r = conversa.dizer("quantas motos vendemos em outubro?")
    assert r["resposta"].startswith(agente.DESLIGADA) and r["origem"] == "regras"
    assert conversa.dizer(FRASE)["acao"] == "confirmar"
    assert conversa.dizer("sim")["acao"] == "criado"


def test_pergunta_no_meio_do_cadastro_preserva_o_rascunho(dono, ia):
    conversa = Conversa(dono)
    r = conversa.dizer("biz 125 2021 branca")
    assert r["estado"]["aguardando"] == "valor_compra"
    antes = ficha(r)

    ia.roteiro = [texto("Há 1 moto à venda.")]
    r = conversa.dizer("quantas motos temos à venda?")
    assert r["resposta"].startswith("Há 1 moto à venda.")
    assert "valor de compra" in r["resposta"]  # a pendência do cadastro é repetida
    assert ficha(r) == antes and r["estado"]["aguardando"] == "valor_compra"
    assert r["origem"] == "ia" and len(r["estado"]["historico"]) == 1

    r = conversa.dizer("comprei por 9 mil")
    assert ficha(r)["valor_compra"] == "R$ 9.000,00"
    assert len(r["estado"]["historico"]) == 1  # o histórico segue junto do rascunho
    assert conversa.dizer("pode cadastrar")["acao"] == "criado"


def test_pergunta_com_confirmacao_pendente_mantem_os_botoes(dono, ia):
    conversa = Conversa(dono)
    antes = ficha(conversa.dizer(FRASE))
    ia.roteiro = [texto("O lucro de novembro é R$ 0,00.")]
    r = conversa.dizer("qual o lucro do mês?")
    assert r["resposta"].startswith("O lucro de novembro é R$ 0,00.")
    assert r["acao"] == "confirmar" and ficha(r) == antes
    assert conversa.dizer("sim")["acao"] == "criado"


def test_registrar_venda_continua_com_o_motor(dono, ia):
    r = perguntar(dono, "vendi a cg pro joão por 14 mil")
    # o motor abre a venda (aqui não há CG à venda: ele pergunta qual veículo); a IA não entra
    assert "Qual veículo foi vendido?" in r["resposta"] and r["origem"] == "regras"
    assert r["estado"]["modo"] == "venda" and ia.corpos == []
    ia.roteiro = [texto("Em outubro você vendeu 1 moto.")]
    r = perguntar(dono, "quantas motos vendi em outubro?")  # "vendi", mas é pergunta
    assert r["origem"] == "ia"


def test_mensagem_nao_entendida_vai_para_a_ia_so_sem_rascunho(dono, ia):
    ia.roteiro = [texto("Em setembro de 2026 não houve vendas.")]
    r = perguntar(dono, "e em setembro")
    assert r["origem"] == "ia" and r["resposta"].startswith("Em setembro")

    conversa = Conversa(dono)
    conversa.dizer("biz 125")
    r = conversa.dizer("hein")
    assert "Não entendi" in r["resposta"] and r["origem"] == "regras"
    assert len(ia.corpos) == 1


def test_texto_simples_tira_markdown():
    assert (
        agente.texto_simples("## Vendas\n**2 motos**\n* CG\n* Biz\nR$\u202f6.000,00\u200b")
        == "Vendas\n2 motos\n- CG\n- Biz\nR$ 6.000,00"
    )
