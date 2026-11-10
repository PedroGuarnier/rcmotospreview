import pytest

from app.config import obter_config
from tests.conftest import nova_venda, novo_veiculo


@pytest.fixture
def demonstracao(monkeypatch):
    """Liga o provedor de demonstração (como em DADOS_DEMO=true)."""
    cfg = obter_config()
    monkeypatch.setattr(cfg, "dados_demo", True)
    monkeypatch.setattr(cfg, "procedencia_provedor", "")
    return cfg


def test_sem_provedor_a_consulta_avisa(dono):
    assert dono.get("/procedencia/situacao").json() == {"disponivel": False, "ilustrativo": False}
    r = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"})
    assert r.status_code == 503
    assert "provedor" in r.json()["detail"]


def test_demonstracao_nunca_vale_em_producao(dono, demonstracao, monkeypatch):
    monkeypatch.setattr(demonstracao, "ambiente", "producao")
    assert dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).status_code == 503


def test_consulta_gera_laudo_com_semaforo(dono, demonstracao):
    assert dono.get("/procedencia/situacao").json() == {"disponivel": True, "ilustrativo": True}
    verde = dono.post("/procedencia/consultar", json={"placa": "abc-1d24"}).json()
    assert verde["placa"] == "ABC1D24" and verde["semaforo"] == "verde" and verde["ilustrativo"]
    assert [i["chave"] for i in verde["itens"]] == ["roubo_furto", "leilao", "renajud", "cadastro"]
    assert all(i["situacao"] == "ok" for i in verde["itens"])
    assert verde["veiculo_id"] is None

    amarelo = dono.post("/procedencia/consultar", json={"placa": "ABC1D23"}).json()
    assert amarelo["semaforo"] == "amarelo"
    vermelho = dono.post("/procedencia/consultar", json={"placa": "ABC1D27"}).json()
    assert vermelho["semaforo"] == "vermelho"
    assert dono.post("/procedencia/consultar", json={"placa": "12"}).status_code == 422
    assert [x["placa"] for x in dono.get("/procedencia").json()] == [
        "ABC1D27",
        "ABC1D23",
        "ABC1D24",
    ]


def test_laudo_fica_no_historico_do_veiculo(dono, gerente, demonstracao):
    # Consulta antes da compra: o laudo é ligado ao veículo quando ele é cadastrado
    antes = gerente.post("/procedencia/consultar", json={"placa": "QWE1234"}).json()
    assert antes["veiculo_id"] is None
    v = novo_veiculo(dono, placa="QWE1234", data_compra="2026-10-01")
    dono.post(
        f"/veiculos/{v['id']}/custos",
        json={
            "tipo": "manutencao",
            "descricao": "Troca de óleo",
            "valor": "90",
            "data": "2026-10-05",
        },
    )
    depois = gerente.post("/procedencia/consultar", json={"placa": "QWE1234"}).json()
    assert depois["veiculo_id"] == v["id"]
    assert depois["dados_veiculo"]["marca_modelo"] == "Honda CG 160 Fan"

    laudos = dono.get(f"/veiculos/{v['id']}/laudos").json()
    assert [x["id"] for x in laudos] == [depois["id"], antes["id"]]
    titulos = [m["titulo"] for m in laudos[0]["historico"]]
    assert titulos == [
        "Fabricação",
        "Chegou à RC Motos",
        "Revisão feita na loja",
        "Consulta de procedência",
    ]
    assert laudos[0]["historico"][2]["detalhe"] == "Troca de óleo"  # detalhe interno
    assert laudos[0]["historico"][1]["quando"] == "01/10/2026"

    eventos = dono.get(f"/veiculos/{v['id']}/historico").json()
    assert any(e["entidade"] == "laudo" and e["usuario_nome"] == "Gerente" for e in eventos)


def test_so_dono_e_gerente_consultam(financeiro, vendedor, demonstracao, dono):
    for api in (financeiro, vendedor):
        assert api.post("/procedencia/consultar", json={"placa": "ABC1D23"}).status_code == 403
        assert api.get("/procedencia").status_code == 403
    v = novo_veiculo(dono)
    assert vendedor.get(f"/veiculos/{v['id']}/laudos").status_code == 200  # ver, pode


def test_catalogo_publico_mostra_so_o_que_esta_a_venda(anonimo, dono, demonstracao):
    a_venda = novo_veiculo(dono, placa="AAA1A11", chassi="9C2KC1670NR000001", renavam="123456789")
    novo_veiculo(dono, placa="BBB2B22", situacao="preparacao")
    vendido = novo_veiculo(dono, placa="CCC3C33")
    nova_venda(dono, vendido["id"])
    novo_veiculo(dono, placa="DDD4D44", tipo="carro", marca="Fiat", modelo="Uno")
    dono.post("/procedencia/consultar", json={"placa": "AAA1A11"})

    catalogo = anonimo.get("/publico/veiculos").json()
    assert catalogo["ilustrativo"] is True
    assert {v["placa_mascarada"] for v in catalogo["veiculos"]} == {"AAA•••1", "DDD•••4"}
    assert [
        v["modelo"] for v in anonimo.get("/publico/veiculos?tipo=carro").json()["veiculos"]
    ] == ["Uno"]
    item = next(v for v in catalogo["veiculos"] if v["id"] == a_venda["id"])
    assert item["preco"] == "14900.00" and item["semaforo"] == "verde"
    # Nada interno vaza para o site
    texto = anonimo.get("/publico/veiculos").text
    for segredo in (
        "11500",
        "valor_compra",
        "custo",
        "9C2KC1670NR000001",
        "00123456789",
        "AAA1A11",
    ):
        assert segredo not in texto, segredo


def test_procedencia_publica(anonimo, dono, demonstracao):
    v = novo_veiculo(dono, placa="AAA1A13", data_compra="2026-10-01")  # final 3 → atenção
    dono.post(
        f"/veiculos/{v['id']}/custos",
        json={
            "tipo": "manutencao",
            "descricao": "Motor refeito",
            "valor": "900",
            "data": "2026-10-03",
        },
    )
    dono.post("/procedencia/consultar", json={"placa": "AAA1A13"})

    pelo_anuncio = anonimo.get(f"/publico/veiculos/{v['id']}/procedencia").json()
    assert pelo_anuncio["placa"] == "AAA•••3"
    pela_placa = anonimo.get("/publico/procedencia/aaa-1a13")
    assert pela_placa.status_code == 200
    laudo = pela_placa.json()
    assert laudo["placa"] == "AAA1A13" and laudo["semaforo"] == "amarelo"
    leilao = next(i for i in laudo["itens"] if i["chave"] == "leilao")
    assert leilao["situacao"] == "atencao"
    # O texto do provedor e os detalhes internos não saem para o público
    assert "2019" not in pela_placa.text and "Motor refeito" not in pela_placa.text
    assert "937" not in pela_placa.text and "11500" not in pela_placa.text
    assert [m["titulo"] for m in laudo["historico"]] == [
        "Fabricação",
        "Chegou à RC Motos",
        "Revisão feita na loja",
        "Consulta de procedência",
    ]

    assert anonimo.get("/publico/procedencia/ZZZ9Z99").status_code == 404
    assert anonimo.get("/publico/procedencia/123").status_code == 422
    em_preparo = novo_veiculo(dono, placa="BBB2B22", situacao="preparacao")
    assert anonimo.get("/publico/procedencia/BBB2B22").status_code == 404
    assert anonimo.get(f"/publico/veiculos/{em_preparo['id']}/procedencia").status_code == 404


def test_laudo_ilustrativo_nao_aparece_fora_da_demonstracao(
    anonimo, dono, demonstracao, monkeypatch
):
    v = novo_veiculo(dono, placa="AAA1A11")
    dono.post("/procedencia/consultar", json={"placa": "AAA1A11"})
    monkeypatch.setattr(demonstracao, "dados_demo", False)
    laudo = anonimo.get(f"/publico/veiculos/{v['id']}/procedencia").json()
    assert laudo["semaforo"] is None and laudo["itens"] == [] and laudo["ilustrativo"] is False
    assert anonimo.get("/publico/veiculos").json()["veiculos"][0]["semaforo"] is None


def test_limite_de_consultas_publicas(anonimo):
    from app.rotas import publico

    publico._acessos.clear()
    codigos = [anonimo.get("/publico/procedencia/ZZZ9Z99").status_code for _ in range(32)]
    assert codigos[:30] == [404] * 30 and codigos[30:] == [429, 429]
    publico._acessos.clear()
