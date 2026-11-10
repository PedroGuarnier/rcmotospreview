from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models import AuditLog, Perfil, Veiculo
from app.tempo import hoje
from tests.conftest import cliente_logado, criar_usuario, nova_venda, novo_veiculo


def test_painel(dono, gerente, financeiro, vendedor, usuario_vendedor, db):
    moto = novo_veiculo(dono)  # compra 11500
    carro = novo_veiculo(
        dono,
        tipo="carro",
        marca="Fiat",
        modelo="Uno",
        placa="XYZ1234",
        valor_compra="24000",
        preco_venda="31900",
    )
    parado = novo_veiculo(dono, placa="QWE1234", valor_compra="9000", preco_venda="12000")
    preparo = novo_veiculo(dono, placa="RTY1234", valor_compra="5000", situacao="preparacao")
    dono.post(
        f"/veiculos/{preparo['id']}/custos",
        json={"tipo": "manutencao", "descricao": "Pneu", "valor": "200"},
    )
    db.execute(
        update(Veiculo)
        .where(Veiculo.id == parado["id"])
        .values(situacao_desde=datetime.now(UTC) - timedelta(days=60))
    )
    db.commit()

    nova_venda(dono, moto["id"], valor="14500", vendedor_id=usuario_vendedor.id)  # lucro 3000
    nova_venda(dono, carro["id"], valor="30000")  # lucro 6000
    cancelada = novo_veiculo(dono, placa="UIO1234")
    venda = nova_venda(dono, cancelada["id"])
    dono.post(f"/vendas/{venda['id']}/cancelar", json={"motivo": "desistiu"})

    r = gerente.get("/painel")
    assert r.status_code == 200
    p = r.json()
    mes = p["mes_atual"]
    assert mes["mes"] == hoje().strftime("%Y-%m")
    assert mes["total"] == {
        "vendas": 2,
        "faturamento": "44500.00",
        "lucro": "9000.00",
        "ticket_medio": "22250.00",
    }
    assert mes["moto"]["ticket_medio"] == "14500.00"
    assert mes["carro"]["lucro"] == "6000.00"
    assert len(p["meses"]) == 6 and p["meses"][0]["total"]["vendas"] == 0
    assert p["meses"][0]["total"]["ticket_medio"] is None

    estoque = p["estoque"]
    assert estoque["em_estoque"] == 3  # parado, preparo e o da venda cancelada
    assert estoque["por_situacao"]["vendido"] == 2
    # 9000 + 5000 + 200 (custo) + 11500 (voltou ao estoque)
    assert estoque["capital_investido"] == "25700.00"
    assert estoque["potencial_venda"] == "26900.00"  # 12000 + 14900
    assert [v["id"] for v in p["parados"]] == [parado["id"]]
    assert p["parados"][0]["dias"] == 60
    assert [(c["vendedor"]["id"], c["total"]) for c in p["comissoes_mes"]] == [
        (usuario_vendedor.id, "300.00")
    ]

    assert financeiro.get("/painel").status_code == 403
    assert vendedor.get("/painel").status_code == 403


def test_aportes_so_dono_e_habilitados(dono, gerente, financeiro, vendedor):
    r = dono.post("/aportes", json={"valor": "5000", "descricao": "Capital de giro"})
    assert r.status_code == 201
    dono.post("/aportes", json={"valor": "1500.50", "descricao": "Reforma"})
    assert dono.get("/aportes").json()["total"] == "6500.50"
    for api in (gerente, financeiro, vendedor):
        assert api.get("/aportes").status_code == 403
        assert "aportes.ver" not in api.get("/auth/eu").json()["permissoes"]

    habilitado = criar_usuario(Perfil.gerente, email="g2@teste.com", acesso_aportes=True)
    api = cliente_logado(habilitado)
    assert len(api.get("/aportes").json()["itens"]) == 2
    assert api.post("/aportes", json={"valor": "10", "descricao": "x"}).status_code == 201
    assert api.delete(f"/aportes/{r.json()['id']}").status_code == 403  # excluir é só do dono
    assert dono.delete(f"/aportes/{r.json()['id']}").status_code == 204


def test_dono_habilita_aportes_para_gerente(dono):
    usuario = criar_usuario(Perfil.gerente)
    api = cliente_logado(usuario)
    assert api.get("/aportes").status_code == 403
    assert dono.patch(f"/usuarios/{usuario.id}", json={"acesso_aportes": True}).status_code == 200
    assert api.get("/aportes").status_code == 200


def test_audit_log_registra_quem_quando_o_que(dono, gerente, vendedor, db):
    v = novo_veiculo(gerente)
    gerente.patch(f"/veiculos/{v['id']}", json={"preco_venda": "15500", "km": 19000})
    gerente.post(
        f"/veiculos/{v['id']}/custos",
        json={"tipo": "manutencao", "descricao": "Revisão", "valor": "280"},
    )
    nova_venda(vendedor, v["id"])

    eventos = dono.get("/historico").json()
    assert all(e["criado_em"] for e in eventos)
    resumo = [(e["usuario_nome"], e["acao"], e["entidade"]) for e in reversed(eventos)]
    assert ("Gerente", "criou", "veiculo") in resumo
    assert ("Gerente", "criou", "custo") in resumo
    assert ("Vendedor", "criou", "venda") in resumo
    assert ("Vendedor", "criou", "comissao") in resumo
    assert ("Vendedor", "entrou", "sessao") in resumo

    alteracao = next(
        e for e in eventos if e["acao"] == "alterou" and e["usuario_nome"] == "Gerente"
    )
    assert alteracao["alteracoes"] == {
        "preco_venda": {"de": "14900.00", "para": "15500.00"},
        "km": {"de": 18500, "para": 19000},
    }

    # Histórico do veículo junta veículo, custos e venda
    do_veiculo = gerente.get(f"/veiculos/{v['id']}/historico").json()
    assert {e["entidade"] for e in do_veiculo} == {"veiculo", "custo", "venda"}

    # Filtros e permissão
    assert all(e["entidade"] == "venda" for e in dono.get("/historico?entidade=venda").json())
    assert gerente.get("/historico").status_code == 403
    assert vendedor.get("/historico").status_code == 403


def test_audit_log_nunca_guarda_senha(dono, db):
    dono.post(
        "/usuarios",
        json={"nome": "Novo", "email": "n@t.com", "senha": "senha-secreta-1", "perfil": "vendedor"},
    )
    usuario_id = dono.get("/usuarios").json()[-1]["id"]
    dono.post(f"/usuarios/{usuario_id}/redefinir-senha", json={"nova_senha": "senha-secreta-2"})
    for evento in db.scalars(select(AuditLog)):
        texto = str(evento.alteracoes)
        assert "argon2" not in texto and "senha-secreta" not in texto
    redefinicao = db.scalars(
        select(AuditLog).where(AuditLog.entidade == "usuario", AuditLog.acao == "alterou")
    ).all()
    assert redefinicao and "senha" in redefinicao[-1].alteracoes
