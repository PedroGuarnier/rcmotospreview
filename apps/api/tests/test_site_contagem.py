"""Contagem de visitas e cliques no WhatsApp do site, procura na área da equipe e o laudo válido."""

from datetime import timedelta

import pytest
from sqlalchemy import func, inspect, select

from app import audit
from app.db import engine
from app.models import AuditLog, ContagemSite
from app.rotas import publico
from app.tempo import hoje
from tests.conftest import novo_veiculo

NAVEGADOR = {
    "user-agent": (
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Mobile Safari/537.36"
    )
}


@pytest.fixture(autouse=True)
def _limite_zerado():
    publico._acessos.clear()
    yield
    publico._acessos.clear()


def evento(cliente, veiculo_id, tipo="visualizacao", **extra):
    return cliente.post(
        "/publico/eventos",
        json={"tipo": tipo, "veiculo_id": veiculo_id, **extra},
        headers=NAVEGADOR,
    )


def contagens(db):
    return db.scalars(select(ContagemSite).order_by(ContagemSite.veiculo_id)).all()


def total_audit(db):
    return db.scalar(select(func.count(AuditLog.id)))


def test_evento_soma_no_dia_do_veiculo(anonimo, dono, db):
    v = novo_veiculo(dono)
    antes = total_audit(db)
    for tipo in (
        "visualizacao",
        "visualizacao",
        "whatsapp_cartao",
        "whatsapp_pagina",
        "whatsapp_pagina",
        "whatsapp_proposta",
    ):
        r = evento(anonimo, v["id"], tipo)
        assert r.status_code == 204 and r.content == b""

    [linha] = contagens(db)
    assert (linha.veiculo_id, linha.dia) == (v["id"], hoje())
    assert (linha.visualizacoes, linha.cliques_cartao) == (2, 1)
    assert (linha.cliques_pagina, linha.cliques_proposta) == (2, 1)
    # contagem não é alteração de negócio: nada no audit log
    assert total_audit(db) == antes
    assert ContagemSite not in audit.ENTIDADES


def test_nenhum_dado_de_quem_visitou_e_gravado(anonimo, dono, db):
    v = novo_veiculo(dono)
    cabecalhos = {**NAVEGADOR, "x-forwarded-for": "203.0.113.77"}
    anonimo.post(
        "/publico/eventos",
        json={"tipo": "visualizacao", "veiculo_id": v["id"]},
        headers=cabecalhos,
    )
    colunas = {c["name"] for c in inspect(engine).get_columns("contagem_site")}
    assert colunas == {
        "veiculo_id",
        "dia",
        "visualizacoes",
        "cliques_cartao",
        "cliques_pagina",
        "cliques_proposta",
    }
    [linha] = contagens(db)
    valores = {str(getattr(linha, c)) for c in colunas}
    assert not any("203.0.113" in x or "Mozilla" in x for x in valores)


@pytest.mark.parametrize(
    "corpo",
    [
        {"tipo": "clique", "veiculo_id": 1},
        {"tipo": "visualizacao"},
        {"veiculo_id": 1},
        {"tipo": "visualizacao", "veiculo_id": 0},
        {"tipo": "visualizacao", "veiculo_id": "um"},
        {"tipo": "visualizacao", "veiculo_id": 1, "ip": "1.2.3.4"},
        {"tipo": "visualizacao", "veiculo_id": 1, "origem": "cartao"},
    ],
)
def test_corpo_validado(anonimo, dono, db, corpo):
    novo_veiculo(dono)
    r = anonimo.post("/publico/eventos", json=corpo, headers=NAVEGADOR)
    assert r.status_code == 422
    assert contagens(db) == []


def test_veiculo_fora_da_vitrine_nao_conta(anonimo, dono, db):
    em_preparo = novo_veiculo(dono, placa="BBB2B22", situacao="preparacao")
    assert evento(anonimo, em_preparo["id"]).status_code == 404
    assert evento(anonimo, 9999, "whatsapp_cartao").status_code == 404
    assert contagens(db) == []


@pytest.mark.parametrize(
    "agente",
    [
        "",
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "facebookexternalhit/1.1",
        "curl/8.5.0",
        "python-requests/2.32",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 HeadlessChrome/131.0 Safari/537.36",
    ],
)
def test_robo_obvio_nao_conta(anonimo, dono, db, agente):
    v = novo_veiculo(dono)
    r = anonimo.post(
        "/publico/eventos",
        json={"tipo": "visualizacao", "veiculo_id": v["id"]},
        headers={"user-agent": agente},
    )
    assert r.status_code == 204
    assert contagens(db) == []


def test_limite_de_eventos(anonimo, dono, db):
    v = novo_veiculo(dono)
    cabecalhos = {**NAVEGADOR, "x-forwarded-for": "198.51.100.9"}
    codigos = [
        anonimo.post(
            "/publico/eventos",
            json={"tipo": "visualizacao", "veiculo_id": v["id"]},
            headers=cabecalhos,
        ).status_code
        for _ in range(publico._LIMITE_EVENTOS + 2)
    ]
    assert codigos[: publico._LIMITE_EVENTOS] == [204] * publico._LIMITE_EVENTOS
    assert codigos[publico._LIMITE_EVENTOS :] == [429, 429]
    assert contagens(db)[0].visualizacoes == publico._LIMITE_EVENTOS
    # o limite é por uso: a contagem não gasta a cota da consulta de placa (nem o contrário)
    assert anonimo.get("/publico/procedencia/ZZZ9Z99", headers=cabecalhos).status_code == 404
    outro = {**NAVEGADOR, "x-forwarded-for": "198.51.100.10"}
    r = anonimo.post(
        "/publico/eventos", json={"tipo": "visualizacao", "veiculo_id": v["id"]}, headers=outro
    )
    assert r.status_code == 204


def _semear(db, veiculo_id, dias_atras, visualizacoes=0, cartao=0, pagina=0, proposta=0):
    db.add(
        ContagemSite(
            veiculo_id=veiculo_id,
            dia=hoje() - timedelta(days=dias_atras),
            visualizacoes=visualizacoes,
            cliques_cartao=cartao,
            cliques_pagina=pagina,
            cliques_proposta=proposta,
        )
    )
    db.commit()


def test_numeros_na_pagina_do_veiculo(dono, vendedor, financeiro, anonimo, db):
    v = novo_veiculo(dono)
    _semear(db, v["id"], 0, visualizacoes=5, cartao=1, pagina=2)
    _semear(db, v["id"], 29, visualizacoes=3, proposta=1)  # ainda dentro dos 30 dias
    _semear(db, v["id"], 30, visualizacoes=40, cartao=7)  # fora da janela, só no total

    r = dono.get(f"/procura/veiculos/{v['id']}")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["dias"] == 30
    assert corpo["recente"] == {
        "visualizacoes": 8,
        "cliques": 4,
        "cliques_cartao": 1,
        "cliques_pagina": 2,
        "cliques_proposta": 1,
    }
    assert corpo["total"]["visualizacoes"] == 48 and corpo["total"]["cliques"] == 11

    sem_nada = novo_veiculo(dono, placa="CCC3C33")
    vazio = dono.get(f"/procura/veiculos/{sem_nada['id']}").json()
    assert vazio["recente"]["visualizacoes"] == 0 and vazio["total"]["cliques"] == 0
    assert dono.get("/procura/veiculos/9999").status_code == 404

    # quem vê o estoque vê a procura; sem login, não
    assert vendedor.get(f"/procura/veiculos/{v['id']}").status_code == 200
    assert financeiro.get(f"/procura/veiculos/{v['id']}").status_code == 200
    assert anonimo.get(f"/procura/veiculos/{v['id']}").status_code == 401


def test_mais_procurados_no_painel(dono, gerente, vendedor, anonimo, db):
    ids = [novo_veiculo(dono, placa=f"AAA1A{i:02d}")["id"] for i in range(7)]
    _semear(db, ids[0], 1, visualizacoes=50, cartao=1)
    _semear(db, ids[1], 2, visualizacoes=10, cartao=3, pagina=2)  # 5 cliques
    _semear(db, ids[2], 0, visualizacoes=4, proposta=2)
    _semear(db, ids[3], 3, visualizacoes=9, pagina=2)  # empata com ids[2]: mais visitas ganha
    _semear(db, ids[4], 40, visualizacoes=99, cartao=99)  # antigo: não entra
    _semear(db, ids[5], 5, visualizacoes=7)  # só visitas
    _semear(db, ids[6], 6, visualizacoes=1)

    r = gerente.get("/procura/mais-procurados")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["dias"] == 30
    assert [x["id"] for x in corpo["veiculos"]] == [ids[1], ids[3], ids[2], ids[0], ids[5]]
    primeiro = corpo["veiculos"][0]
    assert (primeiro["cliques"], primeiro["visualizacoes"]) == (5, 10)
    assert primeiro["situacao"] == "a_venda" and "Honda CG 160 Fan" in primeiro["descricao"]

    assert vendedor.get("/procura/mais-procurados").status_code == 200
    assert anonimo.get("/procura/mais-procurados").status_code == 401


def test_veiculo_excluido_leva_a_contagem(dono, anonimo, db):
    v = novo_veiculo(dono)
    evento(anonimo, v["id"])
    assert dono.delete(f"/veiculos/{v['id']}").status_code == 204
    db.expire_all()
    assert contagens(db) == []


def test_nada_novo_vaza_no_site(anonimo, dono):
    v = novo_veiculo(dono, chassi="9BWZZZ377VT004251", renavam="00123456789")
    evento(anonimo, v["id"], "whatsapp_cartao")
    catalogo = anonimo.get("/publico/veiculos")
    anuncio = anonimo.get(f"/publico/veiculos/{v['id']}")
    assert set(anuncio.json()) == {
        "id",
        "tipo",
        "marca",
        "modelo",
        "ano_fabricacao",
        "ano_modelo",
        "cor",
        "km",
        "preco",
        "placa_mascarada",
        "fotos",
        "dias_na_loja",
        "semaforo",
        "atualizado_em",
    }
    for resposta in (catalogo, anuncio, anonimo.get(f"/publico/veiculos/{v['id']}/procedencia")):
        texto = resposta.text
        for proibido in (
            "11500",
            "9BWZZZ",
            "00123456789",
            "ABC1D23",
            "laudo_valido",
            "visualiz",
            "cliques",
        ):
            assert proibido not in texto


def test_laudo_valido_na_area_da_equipe(dono, vendedor, monkeypatch):
    from app.config import obter_config

    cfg = obter_config()
    v = novo_veiculo(dono, placa="AAA1A11")
    assert dono.get(f"/veiculos/{v['id']}").json()["laudo_valido"] is False
    assert dono.get("/veiculos").json()[0]["laudo_valido"] is False

    # em demonstração o laudo ilustrativo vale; fora dela, não (a mesma regra do site)
    monkeypatch.setattr(cfg, "dados_demo", True)
    monkeypatch.setattr(cfg, "procedencia_provedor", "")
    assert dono.post("/procedencia/consultar", json={"placa": "AAA1A11"}).status_code == 201
    assert dono.get(f"/veiculos/{v['id']}").json()["laudo_valido"] is True
    assert vendedor.get(f"/veiculos/{v['id']}").json()["laudo_valido"] is True
    monkeypatch.setattr(cfg, "dados_demo", False)
    assert dono.get(f"/veiculos/{v['id']}").json()["laudo_valido"] is False

    # pôr à venda sem laudo não é bloqueado: a tela só avisa
    sem_laudo = novo_veiculo(dono, placa="BBB2B22", situacao="preparacao")
    r = dono.patch(f"/veiculos/{sem_laudo['id']}", json={"situacao": "a_venda"})
    assert r.status_code == 200
    assert r.json()["situacao"] == "a_venda" and r.json()["laudo_valido"] is False


def test_atualizado_em_acompanha_o_anuncio(anonimo, dono):
    v = novo_veiculo(dono)
    antes = anonimo.get(f"/publico/veiculos/{v['id']}").json()["atualizado_em"]
    dono.patch(f"/veiculos/{v['id']}", json={"preco_venda": "15500.00"})
    depois = anonimo.get(f"/publico/veiculos/{v['id']}").json()["atualizado_em"]
    assert depois > antes
