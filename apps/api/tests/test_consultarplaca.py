"""Provedor Consultar Placa, com a API deles simulada (nenhum teste sai para a internet)."""

import httpx
import pytest

from app import consultarplaca
from app.config import obter_config
from tests.conftest import novo_veiculo

CADASTRO = {
    "informacoes_veiculo": {
        "dados_veiculo": {
            "placa": "ABC1D23",
            "chassi": "9C2KC1670GR000001",
            "ano_fabricacao": "2016",
            "ano_modelo": "2016",
            "marca": "HONDA",
            "modelo": "HONDA/CG 160 FAN",
            "cor": "Vermelha",
            "segmento": "Moto",
            "municipio": "TERESINA",
            "uf_municipio": "PI",
        },
        "dados_tecnicos": {"tipo_veiculo": "Motocicleta"},
    }
}
LIMPO = {
    "consultarPlaca": CADASTRO,
    "consultarHistoricoRouboFurto": {
        "historico_roubo_furto": {
            "registros_roubo_furto": {"possui_registro": "nao", "registros": []}
        }
    },
    "consultarRegistroLeilaoPrime": {
        "informacoes_sobre_leilao": {
            "possui_registro": "nao",
            "registro_sobre_oferta": {
                "classificacao": "",
                "dicionario_classificacoes": {"A": {"titulo": "texto longo"}},
            },
            "registro_leiloes": {"registros": []},
            "registro_sinistros_acidentes": {"possui_registro": "nao"},
            "parecer_tecnico": {"parecer": "favoravel", "detalhes": {}},
        },
        "informacoes_sobre_remarketing": {"possui_registro": "nao", "registros": None},
    },
    "consultarRenajud": {
        "registro_de_bloqueio_judicial_renajud": {"possui_bloqueio": "nao", "bloqueios": []}
    },
}
# Mesmo formato que a placa de teste do provedor (AAA0000) devolve.
COM_REGISTROS = {
    "consultarPlaca": CADASTRO,
    "consultarHistoricoRouboFurto": {
        "historico_roubo_furto": {
            "registros_roubo_furto": {
                "possui_registro": "sim",
                "registros": [
                    {
                        "boletim_ocorrencia": "9998",
                        "data_boletim_ocorrencia": "06/09/2019",
                        "tipo_ocorrencia": "Devolvido",
                        "uf_ocorrencia": "PR",
                    },
                    {
                        "boletim_ocorrencia": "9996",
                        "data_boletim_ocorrencia": "02/09/2019",
                        "tipo_ocorrencia": "Declaração de Roubo",
                        "uf_ocorrencia": "PR",
                    },
                ],
            }
        }
    },
    "consultarRegistroLeilaoPrime": {
        "informacoes_sobre_leilao": {
            "possui_registro": "sim",
            "registro_sobre_oferta": {"classificacao": "B", "dicionario_classificacoes": {}},
            "registro_leiloes": {
                "registros": [{"data_leilao": "16/11/2016"}, {"data_leilao": "22/11/2016"}]
            },
        },
        "informacoes_sobre_remarketing": {"possui_registro": "sim"},
    },
    "consultarRenajud": {
        "registro_de_bloqueio_judicial_renajud": {
            "possui_bloqueio": "sim",
            "bloqueios": [
                {"tribunal": "TJDF", "processo": "123", "tipo_restricao": "04-PENHORA"},
                {"tribunal": "TJDF", "processo": "123", "tipo_restricao": "03-CIRCULACAO"},
            ],
        }
    },
}


def _ok(dados: dict) -> tuple[int, dict]:
    return 200, {"status": "ok", "mensagem": "Consulta realizada com sucesso!", "dados": dados}


def _erro(status: int, tipo: str | None = None, mensagem: str = "erro") -> tuple[int, dict]:
    corpo = {"status": "erro", "mensagem": mensagem}
    return status, corpo | ({"tipo_do_erro": tipo} if tipo else {})


class Simulado:
    """Faz o papel da API do provedor: responde por rota e anota o que foi pedido."""

    def __init__(self, respostas: dict):
        self.respostas = {rota: _ok(dados) for rota, dados in respostas.items()}
        self.pedidos: list[httpx.Request] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        status, corpo = self.respostas[pedido.url.path.rsplit("/", 1)[-1]]
        return httpx.Response(status, json=corpo)

    @property
    def rotas(self) -> list[str]:
        return sorted(p.url.path.rsplit("/", 1)[-1] for p in self.pedidos)


@pytest.fixture
def provedor(monkeypatch):
    cfg = obter_config()
    monkeypatch.setattr(cfg, "procedencia_provedor", "consultarplaca")
    monkeypatch.setattr(cfg, "consultarplaca_email", "loja@exemplo.com")
    monkeypatch.setattr(cfg, "consultarplaca_api_key", "chave-de-teste")

    def ligar(respostas: dict) -> Simulado:
        simulado = Simulado(respostas)
        monkeypatch.setattr(
            consultarplaca,
            "_cliente",
            lambda: httpx.Client(
                base_url=consultarplaca.URL,
                auth=("loja@exemplo.com", "chave-de-teste"),
                transport=httpx.MockTransport(simulado),
            ),
        )
        return simulado

    return ligar


def _itens(laudo: dict) -> dict:
    return {item["chave"]: item for item in laudo["itens"]}


def test_sem_credenciais_a_consulta_fica_desligada(dono, monkeypatch):
    monkeypatch.setattr(obter_config(), "procedencia_provedor", "consultarplaca")
    assert dono.get("/procedencia/situacao").json() == {"disponivel": False, "ilustrativo": False}
    assert dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).status_code == 503


def test_placa_limpa_da_verde(dono, provedor):
    api = provedor(LIMPO)
    assert dono.get("/procedencia/situacao").json() == {"disponivel": True, "ilustrativo": False}
    r = dono.post("/procedencia/consultar", json={"placa": "abc-1d23"})
    assert r.status_code == 201, r.text
    laudo = r.json()
    assert laudo["semaforo"] == "verde" and not laudo["ilustrativo"]
    assert laudo["provedor"] == "consultarplaca"
    assert all(item["situacao"] == "ok" for item in laudo["itens"])
    assert laudo["dados_veiculo"] == {
        "marca_modelo": "HONDA/CG 160 FAN",
        "ano_fabricacao": 2016,
        "ano_modelo": 2016,
        "cor": "Vermelha",
        "municipio": "Teresina",
        "uf": "PI",
        "chassi": "9C2KC1670GR000001",
        "tipo": "moto",
    }
    assert api.rotas == sorted(LIMPO)
    assert all(p.url.params["placa"] == "ABC1D23" for p in api.pedidos)
    assert all(p.headers["authorization"].startswith("Basic ") for p in api.pedidos)


def test_registros_viram_atencao_e_alerta(dono, provedor):
    provedor(COM_REGISTROS)
    laudo = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    itens = _itens(laudo)
    assert laudo["semaforo"] == "vermelho"
    # o último registro (por data) é a devolução: histórico encerrado, não roubo em aberto
    assert itens["roubo_furto"]["situacao"] == "atencao"
    assert "Devolvido em 06/09/2019 (PR)" in itens["roubo_furto"]["detalhe"]
    assert itens["leilao"]["situacao"] == "atencao"
    assert (
        "22/11/2016" in itens["leilao"]["detalhe"]
        and "Classificação B" in (itens["leilao"]["detalhe"])
    )
    assert itens["renajud"]["situacao"] == "alerta"
    assert "penhora, circulação" in itens["renajud"]["detalhe"]


def test_roubo_em_aberto_e_leilao_de_seguradora_sao_alerta(dono, provedor):
    respostas = {rota: dict(dados) for rota, dados in COM_REGISTROS.items()}
    respostas["consultarHistoricoRouboFurto"] = {
        "historico_roubo_furto": {
            "registros_roubo_furto": {
                "possui_registro": "sim",
                "registros": [
                    {
                        "data_boletim_ocorrencia": "02/09/2019",
                        "tipo_ocorrencia": "Declaração de Roubo",
                    }
                ],
            }
        }
    }
    respostas["consultarRegistroLeilaoPrime"] = {
        "informacoes_sobre_leilao": {
            "possui_registro": "sim",
            "registro_sobre_oferta": {"classificacao": "C"},
        }
    }
    provedor(respostas)
    itens = _itens(dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json())
    assert itens["roubo_furto"]["situacao"] == "alerta"
    assert itens["leilao"]["situacao"] == "alerta"


def test_placa_inexistente_para_na_consulta_barata(dono, provedor):
    api = provedor(LIMPO)
    api.respostas["consultarPlaca"] = _erro(400, "placa_nao_encontrada")
    r = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"})
    assert r.status_code == 404 and "não encontrada" in r.json()["detail"]
    assert api.rotas == ["consultarPlaca"]  # as três consultas caras não foram feitas
    assert dono.get("/procedencia").json() == []


def test_placa_recusada_mostra_o_motivo_do_provedor(dono, provedor):
    api = provedor(LIMPO)
    api.respostas["consultarPlaca"] = _erro(400, mensagem="Placa informada é inválida.")
    r = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"})
    assert r.status_code == 422 and r.json()["detail"] == "Placa informada é inválida."


def test_sem_credito_e_chave_recusada(dono, provedor):
    api = provedor(LIMPO)
    api.respostas["consultarPlaca"] = _erro(402, "credito_insuficiente")
    r = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"})
    assert r.status_code == 503 and "créditos" in r.json()["detail"]
    api.respostas["consultarPlaca"] = _erro(401)
    r = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"})
    assert r.status_code == 503 and "CONSULTARPLACA_API_KEY" in r.json()["detail"]
    assert dono.get("/procedencia").json() == []


def test_item_que_falhou_fica_pendente_e_nao_da_verde(dono, provedor):
    api = provedor(LIMPO)
    api.respostas["consultarRegistroLeilaoPrime"] = _erro(500, "servico_indisponivel")
    laudo = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    itens = _itens(laudo)
    assert laudo["semaforo"] == "amarelo"
    assert itens["leilao"]["situacao"] == "atencao" and "verificar" in itens["leilao"]["detalhe"]
    assert itens["roubo_furto"]["situacao"] == "ok"

    # "indisponivel" dentro de uma resposta 200 também é item não verificado
    api.respostas["consultarRegistroLeilaoPrime"] = _ok(
        {"informacoes_sobre_leilao": {"possui_registro": "indisponivel"}}
    )
    outro = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    assert outro["id"] != laudo["id"]  # laudo incompleto não é reaproveitado
    assert _itens(outro)["leilao"]["situacao"] == "atencao"


def test_tudo_fora_do_ar_nao_guarda_laudo(dono, provedor):
    api = provedor(LIMPO)
    for rota in (
        "consultarHistoricoRouboFurto",
        "consultarRegistroLeilaoPrime",
        "consultarRenajud",
    ):
        api.respostas[rota] = _erro(500, "servico_indisponivel")
    r = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"})
    assert r.status_code == 502
    assert dono.get("/procedencia").json() == []


def test_consulta_repetida_reaproveita_o_laudo_pago(dono, gerente, provedor, monkeypatch):
    api = provedor(LIMPO)
    primeiro = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    de_novo = gerente.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    assert de_novo["id"] == primeiro["id"]
    assert len(api.pedidos) == 4  # só a primeira consulta foi ao provedor
    assert len(dono.get("/procedencia").json()) == 1

    monkeypatch.setattr(obter_config(), "procedencia_reuso_horas", 0)
    terceiro = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    assert terceiro["id"] != primeiro["id"] and len(api.pedidos) == 8


def test_cadastro_nacional_e_comparado_com_o_estoque(dono, provedor):
    provedor(LIMPO)
    veiculo = novo_veiculo(dono, placa="ABC1D23", chassi="9C2KC1670GR999999", ano_fabricacao=2016)
    laudo = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    cadastro = _itens(laudo)["cadastro"]
    assert laudo["veiculo_id"] == veiculo["id"] and laudo["semaforo"] == "amarelo"
    assert cadastro["situacao"] == "atencao" and "chassi" in cadastro["detalhe"]


def test_placa_de_teste_do_provedor_e_marcada_como_ilustrativa(dono, provedor):
    provedor(COM_REGISTROS)
    laudo = dono.post("/procedencia/consultar", json={"placa": "AAA0000"}).json()
    assert laudo["ilustrativo"] is True


def test_retorno_completo_fica_guardado_sem_o_dicionario_fixo(dono, provedor, db):
    from app.models import LaudoProcedencia

    provedor(LIMPO)
    criado = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    bruto = db.get(LaudoProcedencia, criado["id"]).dados["bruto"]
    assert set(bruto) == {"cadastro", "roubo_furto", "leilao", "renajud"}
    oferta = bruto["leilao"]["informacoes_sobre_leilao"]["registro_sobre_oferta"]
    assert "dicionario_classificacoes" not in oferta
