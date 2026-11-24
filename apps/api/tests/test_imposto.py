"""Imposto estimado sobre a margem (venda − compra), com a alíquota configurada pelo dono."""

from decimal import Decimal

import pytest

from app.servicos import calcular_imposto
from tests.conftest import nova_venda, novo_veiculo


@pytest.mark.parametrize(
    ("venda", "compra", "aliquota", "esperado"),
    [
        ("14500", "11500", "6", "180.00"),  # 6% de 3000
        ("14500", "11500", "0", "0.00"),  # sem alíquota configurada
        ("10000", "11500", "6", "0.00"),  # margem negativa não gera imposto
        ("12345.67", "10000", "7.35", "172.41"),  # 172,4067 arredonda
    ],
)
def test_calculo_do_imposto(venda, compra, aliquota, esperado):
    assert calcular_imposto(Decimal(venda), Decimal(compra), Decimal(aliquota)) == Decimal(esperado)


def _aliquota(dono, valor: str):
    r = dono.put("/configuracoes", json={"imposto_margem_aliquota": valor})
    assert r.status_code == 200, r.text
    return r.json()


def test_so_o_dono_configura_a_aliquota(dono, gerente, financeiro, vendedor):
    assert dono.get("/configuracoes").json() == {"imposto_margem_aliquota": "0.00"}
    assert _aliquota(dono, "6.5") == {"imposto_margem_aliquota": "6.50"}
    assert gerente.get("/configuracoes").json() == {"imposto_margem_aliquota": "6.50"}
    assert gerente.put("/configuracoes", json={"imposto_margem_aliquota": "1"}).status_code == 403
    for sem_acesso in (financeiro, vendedor):
        assert sem_acesso.get("/configuracoes").status_code == 403
    for invalida in ("-1", "100.01", "6.555", "abc"):
        r = dono.put("/configuracoes", json={"imposto_margem_aliquota": invalida})
        assert r.status_code == 422, invalida


def test_venda_guarda_imposto_e_comissao_segue_antes_do_imposto(dono, usuario_vendedor):
    _aliquota(dono, "6")
    v = novo_veiculo(dono)
    dono.post(
        f"/veiculos/{v['id']}/custos",
        json={"tipo": "manutencao", "descricao": "Revisão", "valor": "280"},
    )
    venda = nova_venda(dono, v["id"], vendedor_id=usuario_vendedor.id)
    # margem = 14500 − 11500 = 3000 (os custos não entram na base do imposto)
    assert venda["imposto_aliquota"] == "6.00" and venda["imposto"] == "180.00"
    assert venda["lucro"] == "2720.00" and venda["lucro_liquido"] == "2540.00"
    assert venda["comissao"]["valor"] == "272.00"  # 10% do lucro antes do imposto

    do_veiculo = dono.get(f"/veiculos/{v['id']}").json()["venda"]
    assert do_veiculo["imposto"] == "180.00" and do_veiculo["lucro_liquido"] == "2540.00"


def test_mudar_a_aliquota_nao_mexe_em_venda_ja_registrada(dono):
    _aliquota(dono, "6")
    antiga = nova_venda(dono, novo_veiculo(dono)["id"])
    _aliquota(dono, "10")
    nova = nova_venda(dono, novo_veiculo(dono, placa="QWE1234")["id"])
    assert dono.get(f"/vendas/{antiga['id']}").json()["imposto"] == "180.00"
    assert nova["imposto_aliquota"] == "10.00" and nova["imposto"] == "300.00"

    # corrigir o valor de compra depois da venda refaz o imposto com a alíquota da venda (6%)
    r = dono.patch(f"/veiculos/{antiga['veiculo']['id']}", json={"valor_compra": "12000"})
    assert r.status_code == 200, r.text
    corrigida = dono.get(f"/vendas/{antiga['id']}").json()
    assert corrigida["imposto_aliquota"] == "6.00" and corrigida["imposto"] == "150.00"
    assert corrigida["lucro"] == "2500.00" and corrigida["lucro_liquido"] == "2350.00"


def test_previsao_no_veiculo_e_total_no_painel(dono, vendedor):
    _aliquota(dono, "6")
    v = novo_veiculo(dono)  # compra 11500, anunciado por 14900
    detalhe = dono.get(f"/veiculos/{v['id']}").json()
    assert detalhe["lucro_previsto"] == "3400.00" and detalhe["imposto_previsto"] == "204.00"
    assert vendedor.get(f"/veiculos/{v['id']}").json()["imposto_previsto"] is None

    nova_venda(dono, v["id"])
    nova_venda(dono, novo_veiculo(dono, placa="QWE1234", tipo="carro")["id"])
    mes = dono.get("/painel").json()["mes_atual"]
    assert mes["moto"]["imposto"] == "180.00" and mes["carro"]["imposto"] == "180.00"
    assert mes["total"]["imposto"] == "360.00"
    assert mes["total"]["lucro"] == "6000.00" and mes["total"]["lucro_liquido"] == "5640.00"


def test_vendedor_nao_ve_imposto_e_a_mudanca_fica_no_historico(dono, vendedor, usuario_vendedor):
    _aliquota(dono, "6")
    venda = nova_venda(dono, novo_veiculo(dono)["id"], vendedor_id=usuario_vendedor.id)
    sua = vendedor.get(f"/vendas/{venda['id']}").json()
    assert sua["imposto"] is None and sua["lucro_liquido"] is None

    _aliquota(dono, "7")
    eventos = dono.get("/historico?entidade=configuracao").json()
    assert [e["acao"] for e in eventos] == ["alterou", "criou"]
    assert eventos[0]["alteracoes"]["imposto_margem_aliquota"] == {"de": "6.00", "para": "7.00"}
