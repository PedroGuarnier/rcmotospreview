"""Um teste para cada defeito encontrado na revisão de 23/11/2026, antes de ir para produção."""

from datetime import timedelta

import pytest

from app.config import Config
from app.models import Perfil, RegraComissao
from app.tempo import hoje
from tests.conftest import SENHA, cliente_logado, criar_usuario, nova_venda, novo_veiculo


def _em(dias: int) -> str:
    return (hoje() + timedelta(days=dias)).isoformat()


DEBITO = {"tipo": "multa", "descricao": "Multa", "valor": "300", "prazo": _em(10)}


def test_cancelar_venda_com_debito_aberto_nao_volta_para_a_venda(dono, anonimo):
    v = novo_veiculo(dono)
    venda = nova_venda(dono, v["id"])
    assert dono.post(f"/veiculos/{v['id']}/debitos", json=DEBITO).status_code == 201
    dono.post(f"/vendas/{venda['id']}/cancelar", json={"motivo": "desistiu"})
    assert dono.get(f"/veiculos/{v['id']}").json()["situacao"] == "documentacao"
    assert anonimo.get("/publico/veiculos").json()["veiculos"] == []
    # sem débito, continua voltando para "à venda"
    outro = novo_veiculo(dono, placa="XYZ1234")
    venda = nova_venda(dono, outro["id"])
    dono.post(f"/vendas/{venda['id']}/cancelar", json={"motivo": "desistiu"})
    assert dono.get(f"/veiculos/{outro['id']}").json()["situacao"] == "a_venda"


def test_custo_de_debito_pago_nao_pode_ser_apagado_por_fora(dono):
    v = novo_veiculo(dono, situacao="documentacao")
    v = dono.post(f"/veiculos/{v['id']}/debitos", json=DEBITO).json()
    v = dono.post(f"/veiculos/{v['id']}/debitos/{v['debitos'][0]['id']}/pagar", json={}).json()
    r = dono.delete(f"/veiculos/{v['id']}/custos/{v['custos'][0]['id']}")
    assert r.status_code == 409 and "débito" in r.json()["detail"]
    assert dono.get(f"/veiculos/{v['id']}").json()["total_custos"] == "300.00"


def test_vendedor_nao_le_descricao_de_custo_nem_texto_do_provedor_no_laudo(
    dono, vendedor, financeiro, monkeypatch
):
    from app.config import obter_config

    monkeypatch.setattr(obter_config(), "dados_demo", True)
    v = novo_veiculo(dono, placa="AAA1A17", data_compra="2026-10-01")  # final 7: restrição
    dono.post(
        f"/veiculos/{v['id']}/custos",
        json={"tipo": "manutencao", "descricao": "Retífica do motor após batida", "valor": "900"},
    )
    dono.post("/procedencia/consultar", json={"placa": "AAA1A17"})

    completo = dono.get(f"/veiculos/{v['id']}/laudos").text
    assert "Retífica do motor" in completo and "circulação e transferência" in completo
    for api in (vendedor, financeiro):
        r = api.get(f"/veiculos/{v['id']}/laudos")
        assert r.status_code == 200 and r.json()[0]["semaforo"] == "vermelho"
        assert "Retífica" not in r.text and "circulação" not in r.text


def test_dono_rebaixado_perde_os_aportes(dono):
    socio = criar_usuario(Perfil.dono, email="socio@teste.com")
    api = cliente_logado(socio)
    assert api.get("/aportes").status_code == 200
    r = dono.patch(f"/usuarios/{socio.id}", json={"perfil": "gerente"})
    assert r.json()["acesso_aportes"] is False
    api = cliente_logado(socio)  # a troca de perfil derruba a sessão antiga
    assert api.get("/aportes").status_code == 403
    # mas o dono pode manter de propósito
    outro = criar_usuario(Perfil.dono, email="outro@teste.com")
    r = dono.patch(f"/usuarios/{outro.id}", json={"perfil": "gerente", "acesso_aportes": True})
    assert r.json()["acesso_aportes"] is True


def test_desfazer_pagamento_da_comissao_refaz_o_valor(dono, usuario_vendedor):
    v = novo_veiculo(dono)
    venda = nova_venda(dono, v["id"], vendedor_id=usuario_vendedor.id)  # lucro 3000 → 300
    comissao_id = venda["comissao"]["id"]
    dono.post(f"/comissoes/{comissao_id}/pagar")
    dono.post(
        f"/veiculos/{v['id']}/custos",
        json={"tipo": "outro", "descricao": "Conserto", "valor": "2000"},
    )
    assert dono.get(f"/vendas/{venda['id']}").json()["comissao"]["valor"] == "300.00"  # congelada
    r = dono.post(f"/comissoes/{comissao_id}/desfazer-pagamento")
    assert r.json()["status"] == "pendente" and r.json()["valor"] == "100.00"  # 10% de 1000


def test_errar_a_senha_de_alguem_nao_tranca_a_conta_para_o_dono_dela(anonimo):
    criar_usuario(Perfil.dono)
    invasor = {"x-forwarded-for": "198.51.100.7"}
    for _ in range(5):
        r = anonimo.post(
            "/auth/entrar", json={"email": "dono@teste.com", "senha": "chute"}, headers=invasor
        )
        assert r.status_code == 401
    r = anonimo.post(
        "/auth/entrar", json={"email": "dono@teste.com", "senha": SENHA}, headers=invasor
    )
    assert r.status_code == 429  # aquele IP está bloqueado, mesmo com a senha certa
    # o dono, de outro lugar, entra normalmente
    r = anonimo.post(
        "/auth/entrar",
        json={"email": "dono@teste.com", "senha": SENHA},
        headers={"x-forwarded-for": "203.0.113.20"},
    )
    assert r.status_code == 200


def test_bloqueio_nao_revela_se_o_email_existe(anonimo):
    criar_usuario(Perfil.gerente)

    def codigos(email):
        return [
            anonimo.post("/auth/entrar", json={"email": email, "senha": "x"}).status_code
            for _ in range(7)
        ]

    assert codigos("gerente@teste.com") == codigos("ninguem@teste.com") == [401] * 5 + [429, 429]


def test_redefinir_senha_libera_o_login(dono, anonimo):
    usuario = criar_usuario(Perfil.vendedor)
    ips = [{"x-forwarded-for": f"198.51.100.{i}"} for i in range(8)]
    for cabecalho in ips:  # ataque espalhado: 5 erros de cada IP até estourar o teto da conta
        for _ in range(5):
            anonimo.post(
                "/auth/entrar", json={"email": usuario.email, "senha": "x"}, headers=cabecalho
            )
    limpo = {"x-forwarded-for": "203.0.113.50"}
    r = anonimo.post("/auth/entrar", json={"email": usuario.email, "senha": SENHA}, headers=limpo)
    assert r.status_code == 429
    dono.post(f"/usuarios/{usuario.id}/redefinir-senha", json={"nova_senha": "senha-nova-123"})
    r = anonimo.post(
        "/auth/entrar", json={"email": usuario.email, "senha": "senha-nova-123"}, headers=limpo
    )
    assert r.status_code == 200


def test_entrada_grande_ou_absurda_responde_422_e_nao_erro_500(dono):
    v = novo_veiculo(dono)
    longa = "Prata com detalhes em preto fosco e adesivos vermelhos"
    assert dono.patch(f"/veiculos/{v['id']}", json={"cor": longa}).status_code == 422
    assert dono.patch(f"/veiculos/{v['id']}", json={"marca": "M" * 61}).status_code == 422
    assert dono.get("/veiculos/99999999999").status_code == 422
    assert dono.get("/vendas?mes=9999-12").status_code == 422
    assert dono.get("/vendas?mes=0001-01").status_code == 422
    # e o veículo continua inteiro
    assert dono.get(f"/veiculos/{v['id']}").json()["cor"] == "Vermelha"


def test_percentual_de_comissao_acima_de_100_e_recusado_mesmo_sozinho(dono):
    vendedor = criar_usuario(
        Perfil.vendedor, comissao_regra=RegraComissao.percentual_venda, comissao_valor=2
    )
    assert dono.patch(f"/usuarios/{vendedor.id}", json={"comissao_valor": "150"}).status_code == 422
    assert dono.patch(f"/usuarios/{vendedor.id}", json={"comissao_valor": "5"}).status_code == 200
    # valor fixo pode passar de 100 (são reais, não percentual)
    r = dono.patch(
        f"/usuarios/{vendedor.id}", json={"comissao_regra": "valor_fixo", "comissao_valor": "150"}
    )
    assert r.status_code == 200


def test_laudo_de_placa_corrigida_deixa_de_valer(dono, anonimo, monkeypatch):
    from app.config import obter_config

    monkeypatch.setattr(obter_config(), "dados_demo", True)
    v = novo_veiculo(dono, placa="AAA1A11")
    dono.post("/procedencia/consultar", json={"placa": "AAA1A11"})
    assert anonimo.get("/publico/procedencia/AAA1A11").json()["semaforo"] == "verde"
    dono.patch(f"/veiculos/{v['id']}", json={"placa": "AAA1A17"})  # estava digitada errada
    assert anonimo.get("/publico/procedencia/AAA1A17").json()["semaforo"] is None
    assert dono.get(f"/veiculos/{v['id']}/laudos").json() == []


def test_vendido_pode_ir_e_voltar_do_pos_venda(dono):
    v = novo_veiculo(dono)
    nova_venda(dono, v["id"])
    assert dono.patch(f"/veiculos/{v['id']}", json={"situacao": "pos_venda"}).status_code == 200
    r = dono.patch(f"/veiculos/{v['id']}", json={"situacao": "vendido"})
    assert r.status_code == 200 and r.json()["situacao"] == "vendido"


def test_sem_segredo_configurado_nunca_se_usa_um_segredo_conhecido():
    solto = Config(segredo_jwt="", ambiente="desenvolvimento")
    assert len(solto.segredo_jwt) == 64 and "troque" not in solto.segredo_jwt
    with pytest.raises(ValueError):
        Config(segredo_jwt="", ambiente="producao")
    assert Config(segredo_jwt="a" * 40, ambiente="producao").segredo_jwt == "a" * 40
