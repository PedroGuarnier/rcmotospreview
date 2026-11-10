from app.models import Perfil
from tests.conftest import SENHA, cliente_logado, criar_usuario


def test_rotas_exigem_login(anonimo):
    for rota in ("/auth/eu", "/veiculos", "/vendas", "/painel", "/usuarios", "/aportes"):
        assert anonimo.get(rota).status_code == 401, rota


def test_login_e_eu(anonimo):
    criar_usuario(Perfil.dono, email="dono@teste.com")
    r = anonimo.post("/auth/entrar", json={"email": " DONO@teste.com ", "senha": SENHA})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    eu = anonimo.get("/auth/eu").json()
    assert eu["perfil"] == "dono"
    assert "usuarios.gerir" in eu["permissoes"]
    assert "senha_hash" not in eu


def test_senha_errada_nao_revela_se_email_existe(anonimo):
    criar_usuario(Perfil.dono)
    errada = anonimo.post("/auth/entrar", json={"email": "dono@teste.com", "senha": "x"})
    inexistente = anonimo.post("/auth/entrar", json={"email": "ninguem@teste.com", "senha": "x"})
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json()


def test_bloqueia_apos_cinco_tentativas(anonimo):
    criar_usuario(Perfil.vendedor)
    for _ in range(5):
        r = anonimo.post("/auth/entrar", json={"email": "vendedor@teste.com", "senha": "errada"})
        assert r.status_code == 401
    r = anonimo.post("/auth/entrar", json={"email": "vendedor@teste.com", "senha": SENHA})
    assert r.status_code == 429


def test_sair(dono):
    assert dono.post("/auth/sair").status_code == 204
    assert dono.get("/auth/eu").status_code == 401


def test_trocar_senha_derruba_outras_sessoes(anonimo):
    usuario = criar_usuario(Perfil.gerente)
    sessao_a, sessao_b = cliente_logado(usuario), cliente_logado(usuario)
    r = sessao_a.post(
        "/auth/trocar-senha", json={"senha_atual": SENHA, "nova_senha": "nova-senha-123"}
    )
    assert r.status_code == 200
    assert sessao_a.get("/auth/eu").status_code == 200
    assert sessao_b.get("/auth/eu").status_code == 401
    r = anonimo.post("/auth/entrar", json={"email": usuario.email, "senha": "nova-senha-123"})
    assert r.status_code == 200


def test_usuario_desativado_perde_acesso_na_hora(dono):
    usuario = criar_usuario(Perfil.vendedor)
    sessao = cliente_logado(usuario)
    assert dono.patch(f"/usuarios/{usuario.id}", json={"ativo": False}).status_code == 200
    assert sessao.get("/auth/eu").status_code == 401
    r = sessao.post("/auth/entrar", json={"email": usuario.email, "senha": SENHA})
    assert r.status_code == 401


def test_database_url_de_hospedagem_usa_o_driver_instalado():
    from app.config import Config

    for recebida in ("postgres://u:s@host/db", "postgresql://u:s@host/db"):
        assert Config(database_url=recebida).database_url == "postgresql+psycopg://u:s@host/db"
    intacta = "postgresql+psycopg://u:s@host:5432/db"
    assert Config(database_url=intacta).database_url == intacta
