from datetime import timedelta
from decimal import Decimal

import pytest

from app.models import Perfil, RegraComissao
from app.servicos import calcular_comissao
from app.tempo import hoje
from tests.conftest import cliente_logado, criar_usuario, nova_venda, novo_veiculo


@pytest.mark.parametrize(
    ("regra", "regra_valor", "venda", "lucro", "esperado"),
    [
        (RegraComissao.percentual_lucro, "10", "14500", "2720", "272.00"),
        (RegraComissao.percentual_lucro, "10", "10000", "-500", "0.00"),  # prejuízo
        (RegraComissao.percentual_lucro, "7.5", "10000", "1333.33", "100.00"),  # arredonda
        (RegraComissao.percentual_venda, "2", "14500", "0", "290.00"),
        (RegraComissao.valor_fixo, "150", "14500", "-999", "150.00"),
    ],
)
def test_calculo_da_comissao(regra, regra_valor, venda, lucro, esperado):
    valor = calcular_comissao(regra, Decimal(regra_valor), Decimal(venda), Decimal(lucro))
    assert valor == Decimal(esperado)


def test_baixa_calcula_lucro_e_gera_comissao(dono, usuario_vendedor):
    v = novo_veiculo(dono)
    dono.post(
        f"/veiculos/{v['id']}/custos",
        json={"tipo": "manutencao", "descricao": "Revisão", "valor": "280"},
    )
    venda = nova_venda(dono, v["id"], vendedor_id=usuario_vendedor.id)
    # lucro = venda − compra − custos = 14500 − 11500 − 280
    assert venda["lucro"] == "2720.00"
    assert venda["valor_compra"] == "11500.00"
    assert venda["total_custos"] == "280.00"
    assert venda["comissao"]["valor"] == "272.00"  # 10% do lucro
    assert venda["comissao"]["status"] == "pendente"
    assert venda["cliente"]["telefone"] == "86999990001"

    detalhe = dono.get(f"/veiculos/{v['id']}").json()
    assert detalhe["situacao"] == "vendido"
    assert detalhe["venda"]["id"] == venda["id"]


def test_nao_vende_duas_vezes_nem_fora_de_a_venda(dono):
    v = novo_veiculo(dono)
    nova_venda(dono, v["id"])
    r = dono.post(
        "/vendas",
        json={
            "veiculo_id": v["id"],
            "cliente_novo": {"nome": "Outro"},
            "valor": "1",
            "forma": "a_vista",
        },
    )
    assert r.status_code == 409
    assert "já foi vendido" in r.json()["detail"]

    preparando = novo_veiculo(dono, placa="XYZ1234", situacao="preparacao")
    r = dono.post(
        "/vendas",
        json={
            "veiculo_id": preparando["id"],
            "cliente_novo": {"nome": "Outro"},
            "valor": "1",
            "forma": "a_vista",
        },
    )
    assert r.status_code == 409
    assert "não está à venda" in r.json()["detail"]


def test_validacoes_da_forma_de_pagamento(dono):
    v = novo_veiculo(dono)
    base = {
        "veiculo_id": v["id"],
        "cliente_novo": {"nome": "Comprador"},
        "valor": "10000",
    }
    casos = [
        {"forma": "parcelado_loja"},  # sem plano
        {  # parcelas não cobrem o valor
            "forma": "parcelado_loja",
            "entrada": "1000",
            "numero_parcelas": 3,
            "valor_parcela": "1000",
            "primeiro_vencimento": "2026-12-10",
        },
        {"forma": "a_vista", "numero_parcelas": 3},
        {"forma": "a_vista", "entrada": "100"},
        {"forma": "financiado_banco", "entrada": "20000"},
        {"forma": "a_vista", "data_venda": (hoje() + timedelta(days=1)).isoformat()},
        {"forma": "a_vista", "cliente_id": 1},  # cliente escolhido E novo
    ]
    for caso in casos:
        assert dono.post("/vendas", json={**base, **caso}).status_code == 422, caso
    ok = {
        "forma": "parcelado_loja",
        "entrada": "1000",
        "numero_parcelas": 3,
        "valor_parcela": "3000",
        "primeiro_vencimento": "2026-12-10",
    }
    assert dono.post("/vendas", json={**base, **ok}).status_code == 201


def test_reaproveita_cliente_pelo_cpf(dono):
    a = novo_veiculo(dono)
    b = novo_veiculo(dono, placa="XYZ1234")
    cliente = {"nome": "Maria", "cpf_cnpj": "529.982.247-25"}
    v1 = nova_venda(dono, a["id"], cliente_novo=cliente)
    v2 = nova_venda(dono, b["id"], cliente_novo=cliente)
    assert v1["cliente"]["id"] == v2["cliente"]["id"]
    assert v1["cliente"]["cpf_cnpj"] == "52998224725"
    r = dono.post(
        "/vendas",
        json={
            "veiculo_id": a["id"],
            "cliente_novo": {"nome": "X", "cpf_cnpj": "111.111.111-11"},
            "valor": "1",
            "forma": "a_vista",
        },
    )
    assert r.status_code == 422


def test_vendedor_so_vende_em_seu_nome_e_so_ve_as_suas(dono, vendedor, usuario_vendedor):
    outro = criar_usuario(Perfil.vendedor, email="outro@teste.com")
    a = novo_veiculo(dono)
    b = novo_veiculo(dono, placa="XYZ1234")

    r = vendedor.post(
        "/vendas",
        json={
            "veiculo_id": a["id"],
            "cliente_novo": {"nome": "C"},
            "valor": "14000",
            "forma": "a_vista",
            "vendedor_id": outro.id,
        },
    )
    assert r.status_code == 403

    minha = nova_venda(vendedor, a["id"])
    assert minha["vendedor"]["id"] == usuario_vendedor.id
    assert minha["lucro"] is None and minha["valor_compra"] is None  # sem custos.ver
    assert minha["comissao"]["valor"] == "300.00"  # mas vê a própria comissão

    alheia = nova_venda(dono, b["id"], vendedor_id=outro.id)
    assert [v["id"] for v in vendedor.get("/vendas").json()] == [minha["id"]]
    assert vendedor.get(f"/vendas/{alheia['id']}").status_code == 404
    assert vendedor.get(f"/veiculos/{b['id']}").json()["venda"] is None
    assert vendedor.post(f"/vendas/{minha['id']}/cancelar", json={"motivo": "x"}).status_code == 403


def test_cancelar_devolve_ao_estoque_e_cancela_comissao(dono, gerente, usuario_vendedor):
    v = novo_veiculo(dono)
    venda = nova_venda(dono, v["id"], vendedor_id=usuario_vendedor.id)
    r = gerente.post(f"/vendas/{venda['id']}/cancelar", json={"motivo": "Cliente desistiu"})
    assert r.status_code == 200
    assert r.json()["status"] == "cancelada"
    assert r.json()["comissao"]["status"] == "cancelada"
    assert dono.get(f"/veiculos/{v['id']}").json()["situacao"] == "a_venda"
    assert dono.get("/vendas").json() == []
    assert len(dono.get("/vendas?incluir_canceladas=true").json()) == 1
    assert gerente.post(f"/vendas/{venda['id']}/cancelar", json={"motivo": "x"}).status_code == 409
    # Pode vender de novo
    nova_venda(dono, v["id"])


def test_custo_depois_da_venda_refaz_lucro_e_comissao_pendente(dono, usuario_vendedor):
    v = novo_veiculo(dono)
    venda = nova_venda(dono, v["id"], vendedor_id=usuario_vendedor.id)
    assert venda["lucro"] == "3000.00" and venda["comissao"]["valor"] == "300.00"
    dono.post(
        f"/veiculos/{v['id']}/custos",
        json={"tipo": "documentacao", "descricao": "Transferência", "valor": "500"},
    )
    venda = dono.get(f"/vendas/{venda['id']}").json()
    assert venda["lucro"] == "2500.00" and venda["comissao"]["valor"] == "250.00"

    # Comissão já paga não muda mais
    assert dono.post(f"/comissoes/{venda['comissao']['id']}/pagar").status_code == 200
    dono.post(
        f"/veiculos/{v['id']}/custos",
        json={"tipo": "outro", "descricao": "Brinde", "valor": "100"},
    )
    venda = dono.get(f"/vendas/{venda['id']}").json()
    assert venda["lucro"] == "2400.00" and venda["comissao"]["valor"] == "250.00"
    r = dono.post(f"/vendas/{venda['id']}/cancelar", json={"motivo": "x"})
    assert r.status_code == 409  # comissão paga trava o cancelamento


def test_relatorio_de_comissoes(dono, financeiro, gerente, vendedor, usuario_vendedor):
    fixo = criar_usuario(
        Perfil.vendedor,
        email="fixo@teste.com",
        nome="Fixo",
        comissao_regra=RegraComissao.valor_fixo,
        comissao_valor=150,
    )
    a = novo_veiculo(dono)
    b = novo_veiculo(dono, placa="XYZ1234")
    c = novo_veiculo(dono, placa="QWE1234")
    nova_venda(dono, a["id"], vendedor_id=usuario_vendedor.id)  # 300
    nova_venda(dono, b["id"], vendedor_id=fixo.id)  # 150
    antiga = (hoje().replace(day=1) - timedelta(days=1)).isoformat()
    nova_venda(dono, c["id"], vendedor_id=fixo.id, data_venda=antiga)  # mês passado

    rel = financeiro.get("/comissoes").json()
    assert rel["total"] == "450.00" and rel["pendente"] == "450.00"
    assert [(g["vendedor"]["nome"], g["total"]) for g in rel["por_vendedor"]] == [
        ("Vendedor", "300.00"),
        ("Fixo", "150.00"),
    ]
    mes_passado = financeiro.get(f"/comissoes?mes={antiga[:7]}").json()
    assert mes_passado["total"] == "150.00"

    # Vendedor só enxerga as dele, mesmo pedindo as de outro
    proprio = vendedor.get(f"/comissoes?vendedor_id={fixo.id}").json()
    assert [i["vendedor"]["id"] for i in proprio["itens"]] == [usuario_vendedor.id]

    # Pagar: financeiro e dono sim; gerente e vendedor não
    comissao_id = proprio["itens"][0]["id"]
    assert gerente.post(f"/comissoes/{comissao_id}/pagar").status_code == 403
    assert vendedor.post(f"/comissoes/{comissao_id}/pagar").status_code == 403
    assert financeiro.post(f"/comissoes/{comissao_id}/pagar").json()["status"] == "paga"
    assert financeiro.post(f"/comissoes/{comissao_id}/pagar").status_code == 409
    rel = financeiro.get("/comissoes").json()
    assert rel["pendente"] == "150.00"
    r = financeiro.post(f"/comissoes/{comissao_id}/desfazer-pagamento")
    assert r.json()["status"] == "pendente"


def test_vendedor_sem_regra_nao_gera_comissao(dono):
    v = novo_veiculo(dono)
    venda = nova_venda(dono, v["id"])  # o próprio dono vendeu
    assert venda["comissao"] is None


def test_financeiro_ve_vendas_mas_nao_registra(dono, financeiro):
    v = novo_veiculo(dono)
    nova_venda(dono, v["id"])
    vendas = financeiro.get("/vendas").json()
    assert len(vendas) == 1 and vendas[0]["lucro"] is None
    r = financeiro.post(
        "/vendas",
        json={
            "veiculo_id": v["id"],
            "cliente_novo": {"nome": "C"},
            "valor": "1",
            "forma": "a_vista",
        },
    )
    assert r.status_code == 403


def test_sessao_de_vendedor_desativado_nao_pode_ser_vendedor(dono):
    inativo = criar_usuario(Perfil.vendedor, email="inativo@teste.com", ativo=False)
    v = novo_veiculo(dono)
    r = dono.post(
        "/vendas",
        json={
            "veiculo_id": v["id"],
            "cliente_novo": {"nome": "C"},
            "valor": "1",
            "forma": "a_vista",
            "vendedor_id": inativo.id,
        },
    )
    assert r.status_code == 422
    assert cliente_logado  # mantém o import usado em outros testes
