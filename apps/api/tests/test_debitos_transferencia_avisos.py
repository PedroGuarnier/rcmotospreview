from datetime import timedelta

from app.tempo import hoje
from tests.conftest import nova_venda, novo_veiculo


def _em(dias: int) -> str:
    return (hoje() + timedelta(days=dias)).isoformat()


def _debito(api, veiculo_id, dias, **campos):
    corpo = {"tipo": "ipva", "descricao": "IPVA 2026", "valor": "410.00", "prazo": _em(dias)}
    r = api.post(f"/veiculos/{veiculo_id}/debitos", json={**corpo, **campos})
    assert r.status_code == 201, r.text
    return r.json()


def test_debito_aberto_impede_ir_a_venda(dono):
    v = novo_veiculo(dono, situacao="documentacao")
    v = _debito(dono, v["id"], 20)
    assert v["debitos_abertos"] == 1 and v["proximo_prazo"] == _em(20) and v["nivel_debito"] == "ok"
    assert v["total_debitos_abertos"] == "410.00"
    # lucro previsto já desconta o débito: 14900 − 11500 − 410
    assert v["lucro_previsto"] == "2990.00"

    r = dono.patch(f"/veiculos/{v['id']}", json={"situacao": "a_venda"})
    assert r.status_code == 409
    assert "IPVA 2026" in r.json()["detail"]
    # outras etapas continuam liberadas
    assert dono.patch(f"/veiculos/{v['id']}", json={"situacao": "preparacao"}).status_code == 200


def test_pagar_debito_vira_custo_e_libera_a_venda(dono):
    v = novo_veiculo(dono, situacao="documentacao")
    v = _debito(dono, v["id"], 5)
    debito_id = v["debitos"][0]["id"]
    assert v["debitos"][0]["nivel"] == "urgente" and v["debitos"][0]["dias_restantes"] == 5

    # pagou com juros: o custo é o valor realmente pago
    r = dono.post(f"/veiculos/{v['id']}/debitos/{debito_id}/pagar", json={"valor_pago": "432.50"})
    assert r.status_code == 200
    v = r.json()
    assert v["debitos"][0]["status"] == "pago" and v["debitos"][0]["nivel"] == "pago"
    assert v["debitos_abertos"] == 0 and v["nivel_debito"] is None
    assert [(c["tipo"], c["descricao"], c["valor"]) for c in v["custos"]] == [
        ("debito", "IPVA 2026", "432.50")
    ]
    assert v["custo_total"] == "11932.50" and v["lucro_previsto"] == "2967.50"
    assert dono.patch(f"/veiculos/{v['id']}", json={"situacao": "a_venda"}).status_code == 200
    assert dono.post(f"/veiculos/{v['id']}/debitos/{debito_id}/pagar", json={}).status_code == 409


def test_reabrir_debito_desfaz_o_custo_e_tira_da_venda(dono):
    v = novo_veiculo(dono, situacao="documentacao")
    v = _debito(dono, v["id"], 5)
    debito_id = v["debitos"][0]["id"]
    dono.post(f"/veiculos/{v['id']}/debitos/{debito_id}/pagar", json={})
    dono.patch(f"/veiculos/{v['id']}", json={"situacao": "a_venda"})
    assert dono.delete(f"/veiculos/{v['id']}/debitos/{debito_id}").status_code == 409  # pago

    v = dono.post(f"/veiculos/{v['id']}/debitos/{debito_id}/reabrir").json()
    assert v["custos"] == [] and v["debitos"][0]["status"] == "aberto"
    assert v["situacao"] == "documentacao"
    v = dono.delete(f"/veiculos/{v['id']}/debitos/{debito_id}").json()
    assert v["debitos"] == []


def test_debito_lancado_em_veiculo_a_venda_volta_para_documentacao(dono, anonimo):
    v = novo_veiculo(dono)  # à venda
    assert len(anonimo.get("/publico/veiculos").json()["veiculos"]) == 1
    v = _debito(dono, v["id"], 30, tipo="multa", descricao="Multa de trânsito")
    assert v["situacao"] == "documentacao"
    assert anonimo.get("/publico/veiculos").json()["veiculos"] == []  # saiu do site


def test_niveis_do_prazo_do_debito(dono):
    v = novo_veiculo(dono, situacao="compra")
    for dias in (16, 15, 8, 7, 1, 0, -3):
        _debito(dono, v["id"], dias, descricao=f"em {dias}")
    debitos = dono.get(f"/veiculos/{v['id']}").json()["debitos"]
    assert {d["descricao"]: d["nivel"] for d in debitos} == {
        "em 16": "ok",
        "em 15": "atencao",
        "em 8": "atencao",
        "em 7": "urgente",
        "em 1": "urgente",
        "em 0": "hoje",
        "em -3": "vencido",
    }
    resumo = dono.get("/veiculos").json()[0]
    assert resumo["debitos_abertos"] == 7 and resumo["nivel_debito"] == "vencido"
    assert resumo["proximo_prazo"] == _em(-3)


def test_so_dono_e_gerente_mexem_em_debitos_e_vendedor_nao_ve_valores(
    dono, gerente, financeiro, vendedor
):
    v = novo_veiculo(dono, situacao="compra")
    corpo = {"tipo": "ipva", "descricao": "IPVA", "valor": "100", "prazo": _em(3)}
    assert gerente.post(f"/veiculos/{v['id']}/debitos", json=corpo).status_code == 201
    for api in (financeiro, vendedor):
        assert api.post(f"/veiculos/{v['id']}/debitos", json=corpo).status_code == 403
    visto = vendedor.get(f"/veiculos/{v['id']}").json()
    assert visto["debitos"] is None and visto["total_debitos_abertos"] is None
    assert visto["debitos_abertos"] == 1 and visto["nivel_debito"] == "urgente"  # sabe que existe
    assert dono.post("/veiculos/999/debitos", json=corpo).status_code == 404
    assert (
        dono.post(f"/veiculos/{v['id']}/debitos", json={**corpo, "valor": "0"}).status_code == 422
    )


def test_transferencia_conta_30_dias_da_venda(dono, financeiro, vendedor, usuario_vendedor):
    casos = {  # dias desde a venda → (dias restantes, situação)
        2: (28, "no_prazo"),
        9: (21, "no_prazo"),
        10: (20, "cobrar"),
        25: (5, "cobrar"),
        30: (0, "cobrar"),
        31: (-1, "vencida"),
    }
    vendas = {}
    for i, dias in enumerate(casos):
        v = novo_veiculo(dono, placa=f"AAA{i}A1{i}")
        vendas[dias] = nova_venda(
            dono, v["id"], data_venda=_em(-dias), vendedor_id=usuario_vendedor.id
        )
    for dias, (restantes, situacao) in casos.items():
        t = vendas[dias]["transferencia"]
        assert (t["dias_restantes"], t["situacao"]) == (restantes, situacao), dias
        assert t["prazo"] == _em(30 - dias) and t["transferida_em"] is None

    atrasada = vendas[31]["id"]
    assert vendedor.post(f"/vendas/{atrasada}/transferencia", json={}).status_code == 403
    r = financeiro.post(f"/vendas/{atrasada}/transferencia", json={"transferida_em": _em(-1)})
    assert r.status_code == 200
    assert r.json()["transferencia"]["situacao"] == "transferida"
    assert r.json()["transferencia"]["transferida_em"] == _em(-1)
    # datas impossíveis
    for dia in (_em(1), _em(-40)):
        r = dono.post(f"/vendas/{atrasada}/transferencia", json={"transferida_em": dia})
        assert r.status_code == 422
    r = dono.delete(f"/vendas/{atrasada}/transferencia")
    assert r.json()["transferencia"]["situacao"] == "vencida"

    dono.post(f"/vendas/{vendas[2]['id']}/cancelar", json={"motivo": "desistiu"})
    cancelada = dono.get(f"/vendas/{vendas[2]['id']}").json()
    assert cancelada["transferencia"] is None
    assert dono.post(f"/vendas/{cancelada['id']}/transferencia", json={}).status_code == 409


def test_avisos_juntam_prazos_e_respeitam_o_perfil(dono, gerente, financeiro, vendedor):
    a = novo_veiculo(dono, placa="AAA1A11", situacao="compra")
    _debito(dono, a["id"], -2, descricao="IPVA 2025")  # vencido
    _debito(dono, a["id"], 0, tipo="licenciamento", descricao="Licenciamento 2026")  # hoje
    _debito(dono, a["id"], 12, tipo="multa", descricao="Multa")  # atenção
    _debito(dono, a["id"], 40, descricao="IPVA 2027")  # longe: não avisa
    pago = _debito(dono, a["id"], 1, descricao="Pago")["debitos"]
    pago_id = next(d["id"] for d in pago if d["descricao"] == "Pago")
    dono.post(f"/veiculos/{a['id']}/debitos/{pago_id}/pagar", json={})  # pago: não avisa

    b = novo_veiculo(dono, placa="BBB2B22")
    c = novo_veiculo(dono, placa="CCC3C33")
    d = novo_veiculo(dono, placa="DDD4D44")
    venda_b = nova_venda(dono, b["id"], data_venda=_em(-35))  # transferência vencida
    nova_venda(
        dono, c["id"], data_venda=_em(-12), cliente_novo={"nome": "João", "telefone": "86999990002"}
    )
    nova_venda(dono, d["id"], data_venda=_em(-3), cliente_novo={"nome": "Cedo"})  # antes do 10º dia

    avisos = dono.get("/avisos").json()
    assert [(x["tipo"], x["nivel"], x["dias_restantes"]) for x in avisos["itens"]] == [
        ("transferencia", "vencido", -5),
        ("debito", "vencido", -2),
        ("debito", "hoje", 0),
        ("debito", "atencao", 12),
        ("transferencia", "atencao", 18),
    ]
    assert avisos["total"] == 5 and avisos["urgentes"] == 3
    primeiro, _, licenciamento, _, joao = avisos["itens"]
    assert primeiro["venda_id"] == venda_b["id"] and primeiro["cliente_nome"] == "Maria Compradora"
    assert "venceu há 5 dias" in primeiro["detalhe"]
    assert licenciamento["titulo"] == "Licenciamento: Licenciamento 2026"
    assert licenciamento["valor"] == "410.00" and "vence hoje" in licenciamento["detalhe"]
    assert joao["cliente_telefone"] == "86999990002"

    # gerente vê tudo; financeiro só transferências (sem valores de débito); vendedor nada
    assert gerente.get("/avisos").json()["total"] == 5
    do_financeiro = financeiro.get("/avisos").json()
    assert {x["tipo"] for x in do_financeiro["itens"]} == {"transferencia"}
    assert do_financeiro["total"] == 2
    assert vendedor.get("/avisos").json() == {"itens": [], "total": 0, "urgentes": 0}

    # resolvido, o aviso some sozinho
    dono.post(f"/vendas/{venda_b['id']}/transferencia", json={})
    assert dono.get("/avisos").json()["total"] == 4


def test_debitos_entram_no_historico(dono, gerente):
    v = novo_veiculo(dono, situacao="compra")
    v = _debito(gerente, v["id"], 5)
    gerente.post(f"/veiculos/{v['id']}/debitos/{v['debitos'][0]['id']}/pagar", json={})
    eventos = dono.get(f"/veiculos/{v['id']}/historico").json()
    do_debito = [(e["acao"], e["usuario_nome"]) for e in eventos if e["entidade"] == "debito"]
    assert do_debito == [("alterou", "Gerente"), ("criou", "Gerente")]
