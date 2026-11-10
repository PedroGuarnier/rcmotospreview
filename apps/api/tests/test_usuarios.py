from app.models import Perfil
from tests.conftest import criar_usuario

NOVO = {
    "nome": "João Vendedor",
    "email": "Joao@Teste.com",
    "senha": "senha-forte-1",
    "perfil": "vendedor",
    "comissao_regra": "percentual_lucro",
    "comissao_valor": "10",
}


def test_so_o_dono_gerencia_usuarios(gerente, financeiro, vendedor):
    for api in (gerente, financeiro, vendedor):
        assert api.get("/usuarios").status_code == 403
        assert api.post("/usuarios", json=NOVO).status_code == 403


def test_dono_cria_usuario_que_consegue_entrar(dono, anonimo):
    r = dono.post("/usuarios", json=NOVO)
    assert r.status_code == 201
    assert r.json()["email"] == "joao@teste.com"
    assert "senha" not in r.text.replace("senha-forte-1", "")  # nada de hash na resposta
    r = anonimo.post("/auth/entrar", json={"email": "joao@teste.com", "senha": "senha-forte-1"})
    assert r.status_code == 200


def test_email_duplicado_e_senha_curta(dono):
    assert dono.post("/usuarios", json=NOVO).status_code == 201
    assert dono.post("/usuarios", json=NOVO).status_code == 409
    assert (
        dono.post("/usuarios", json={**NOVO, "email": "b@t.com", "senha": "123"}).status_code == 422
    )


def test_nao_fica_sem_dono(dono):
    eu = dono.get("/auth/eu").json()
    assert dono.patch(f"/usuarios/{eu['id']}", json={"perfil": "gerente"}).status_code == 409
    assert dono.patch(f"/usuarios/{eu['id']}", json={"ativo": False}).status_code == 409


def test_redefinir_senha(dono, anonimo):
    usuario = criar_usuario(Perfil.vendedor)
    r = dono.post(f"/usuarios/{usuario.id}/redefinir-senha", json={"nova_senha": "outra-senha-9"})
    assert r.status_code == 204
    r = anonimo.post("/auth/entrar", json={"email": usuario.email, "senha": "outra-senha-9"})
    assert r.status_code == 200


def test_lista_de_vendedores_nao_expoe_dados(vendedor):
    r = vendedor.get("/usuarios/vendedores")
    assert r.status_code == 200
    assert set(r.json()[0]) == {"id", "nome"}
