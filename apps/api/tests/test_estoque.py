import io

from PIL import Image

from tests.conftest import VEICULO, nova_venda, novo_veiculo


def _foto(formato="JPEG", tamanho=(2400, 1200)) -> bytes:
    saida = io.BytesIO()
    Image.new("RGB", tamanho, (200, 30, 30)).save(saida, formato)
    return saida.getvalue()


def test_cadastro_normaliza_placa_e_calcula_custos(dono):
    v = novo_veiculo(dono, renavam="123456789")
    assert v["placa"] == "ABC1D23"
    assert v["renavam"] == "00123456789"
    assert v["custo_total"] == "11500.00"
    assert v["lucro_previsto"] == "3400.00"
    r = dono.post(
        f"/veiculos/{v['id']}/custos",
        json={"tipo": "manutencao", "descricao": "Revisão", "valor": "280.50"},
    )
    assert r.status_code == 201
    v = r.json()
    assert v["total_custos"] == "280.50"
    assert v["custo_total"] == "11780.50"
    assert v["lucro_previsto"] == "3119.50"
    r = dono.delete(f"/veiculos/{v['id']}/custos/{v['custos'][0]['id']}")
    assert r.json()["total_custos"] == "0.00"


def test_validacoes(dono):
    assert dono.post("/veiculos", json={**VEICULO, "placa": "123"}).status_code == 422
    assert dono.post("/veiculos", json={**VEICULO, "valor_compra": "-1"}).status_code == 422
    novo_veiculo(dono)
    r = dono.post("/veiculos", json=VEICULO)
    assert r.status_code == 409
    assert "placa" in r.json()["detail"]


def test_a_venda_exige_preco(dono):
    r = dono.post("/veiculos", json={**VEICULO, "preco_venda": None})
    assert r.status_code == 422
    v = novo_veiculo(dono, preco_venda=None, situacao="preparacao")
    assert dono.patch(f"/veiculos/{v['id']}", json={"situacao": "a_venda"}).status_code == 422
    r = dono.patch(f"/veiculos/{v['id']}", json={"situacao": "a_venda", "preco_venda": "9000"})
    assert r.status_code == 200
    assert r.json()["situacao"] == "a_venda"


def test_situacao_vendido_so_pela_venda(dono):
    v = novo_veiculo(dono)
    assert dono.patch(f"/veiculos/{v['id']}", json={"situacao": "vendido"}).status_code == 409
    assert dono.patch(f"/veiculos/{v['id']}", json={"situacao": "pos_venda"}).status_code == 409
    nova_venda(dono, v["id"])
    assert dono.patch(f"/veiculos/{v['id']}", json={"situacao": "a_venda"}).status_code == 409
    r = dono.patch(f"/veiculos/{v['id']}", json={"situacao": "pos_venda"})
    assert r.status_code == 200


def test_vendedor_ve_estoque_sem_custos_e_nao_edita(dono, vendedor):
    v = novo_veiculo(dono)
    dono.post(
        f"/veiculos/{v['id']}/custos", json={"tipo": "outro", "descricao": "Frete", "valor": "100"}
    )
    lista = vendedor.get("/veiculos").json()
    detalhe = vendedor.get(f"/veiculos/{v['id']}").json()
    for item in (lista[0], detalhe):
        assert item["preco_venda"] == "14900.00"
        for campo in ("valor_compra", "total_custos", "custo_total", "lucro_previsto"):
            assert item[campo] is None
    assert detalhe["custos"] is None
    assert vendedor.post("/veiculos", json={**VEICULO, "placa": "XYZ1234"}).status_code == 403
    assert vendedor.patch(f"/veiculos/{v['id']}", json={"km": 1}).status_code == 403
    assert vendedor.get(f"/veiculos/{v['id']}/historico").status_code == 403


def test_filtros_e_busca(dono):
    novo_veiculo(dono)
    novo_veiculo(dono, tipo="carro", marca="Fiat", modelo="Uno Way", placa="XYZ1234")
    novo_veiculo(dono, placa="QWE1234", situacao="preparacao")
    assert len(dono.get("/veiculos").json()) == 3
    assert len(dono.get("/veiculos?tipo=carro").json()) == 1
    assert len(dono.get("/veiculos?situacao=a_venda").json()) == 2
    assert [v["modelo"] for v in dono.get("/veiculos?busca=uno fiat").json()] == ["Uno Way"]
    assert len(dono.get("/veiculos?busca=xyz").json()) == 1
    assert len(dono.get("/veiculos?grupo=vendidos").json()) == 0


def test_fotos(dono, vendedor):
    v = novo_veiculo(dono)
    r = dono.post(f"/veiculos/{v['id']}/fotos", files={"arquivo": ("a.jpg", _foto(), "image/jpeg")})
    assert r.status_code == 201, r.text
    r = dono.post(
        f"/veiculos/{v['id']}/fotos", files={"arquivo": ("b.png", _foto("PNG"), "image/png")}
    )
    fotos = r.json()["fotos"]
    assert len(fotos) == 2
    assert r.json()["foto_capa"] == fotos[0]["miniatura_url"]

    # A foto é servida redimensionada e a miniatura é pequena
    grande = Image.open(io.BytesIO(dono.get(fotos[0]["url"]).content))
    mini = Image.open(io.BytesIO(dono.get(fotos[0]["miniatura_url"]).content))
    assert max(grande.size) == 1920 and max(mini.size) == 480

    r = dono.post(f"/veiculos/{v['id']}/fotos/{fotos[1]['id']}/capa")
    assert r.json()["fotos"][0]["id"] == fotos[1]["id"]

    r = dono.post(
        f"/veiculos/{v['id']}/fotos", files={"arquivo": ("x.jpg", b"nao e foto", "image/jpeg")}
    )
    assert r.status_code == 422
    r = vendedor.post(
        f"/veiculos/{v['id']}/fotos", files={"arquivo": ("a.jpg", _foto(), "image/jpeg")}
    )
    assert r.status_code == 403

    r = dono.delete(f"/veiculos/{v['id']}/fotos/{fotos[0]['id']}")
    assert len(r.json()["fotos"]) == 1
    assert dono.get(fotos[0]["url"]).status_code == 404


def test_excluir_so_dono_e_sem_venda(dono, gerente):
    v = novo_veiculo(dono)
    assert gerente.delete(f"/veiculos/{v['id']}").status_code == 403
    nova_venda(dono, v["id"])
    assert dono.delete(f"/veiculos/{v['id']}").status_code == 409
    outro = novo_veiculo(dono, placa="XYZ1234")
    assert dono.delete(f"/veiculos/{outro['id']}").status_code == 204
    assert dono.get(f"/veiculos/{outro['id']}").status_code == 404


def test_erros_de_validacao_em_portugues(dono):
    r = dono.post("/veiculos", json={**VEICULO, "placa": "123"})
    assert r.json()["detail"] == "Placa inválida. Use o formato ABC1234 ou ABC1D23."
    r = dono.post("/veiculos", json={"tipo": "moto", "marca": "Honda", "valor_compra": "0"})
    assert r.json()["detail"] == "modelo: campo obrigatório"
