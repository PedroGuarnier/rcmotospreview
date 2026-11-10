"""Testes rodam contra um Postgres de verdade (banco separado, limpo a cada teste).

Banco padrão: postgresql+psycopg://rcmotos:rcmotos@localhost:5432/rcmotos_teste
(sobrescreva com TEST_DATABASE_URL).
"""

import os
import tempfile

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://rcmotos:rcmotos@localhost:5432/rcmotos_teste"
)
os.environ["AMBIENTE"] = "teste"
os.environ["UPLOADS_DIR"] = tempfile.mkdtemp(prefix="rcmotos-uploads-")
os.environ["DADOS_DEMO"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Perfil, RegraComissao, Usuario  # noqa: E402
from app.security import gerar_hash  # noqa: E402

SENHA = "senha-de-teste"
_HASH = gerar_hash(SENHA)


@pytest.fixture(scope="session", autouse=True)
def _esquema():
    assert "teste" in engine.url.database, "os testes apagam o banco: use um banco de teste"
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _limpar():
    tabelas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as con:
        con.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao


def criar_usuario(perfil: Perfil, email: str | None = None, **campos) -> Usuario:
    with SessionLocal() as sessao:
        usuario = Usuario(
            nome=campos.pop("nome", perfil.value.capitalize()),
            email=email or f"{perfil.value}@teste.com",
            senha_hash=_HASH,
            perfil=perfil,
            acesso_aportes=campos.pop("acesso_aportes", perfil == Perfil.dono),
            **campos,
        )
        sessao.add(usuario)
        sessao.commit()
        return usuario


def cliente_logado(usuario: Usuario) -> TestClient:
    cliente = TestClient(app)
    r = cliente.post("/auth/entrar", json={"email": usuario.email, "senha": SENHA})
    assert r.status_code == 200, r.text
    return cliente


@pytest.fixture
def anonimo():
    return TestClient(app)


@pytest.fixture
def dono():
    return cliente_logado(criar_usuario(Perfil.dono))


@pytest.fixture
def gerente():
    return cliente_logado(criar_usuario(Perfil.gerente))


@pytest.fixture
def financeiro():
    return cliente_logado(criar_usuario(Perfil.financeiro))


@pytest.fixture
def usuario_vendedor():
    return criar_usuario(
        Perfil.vendedor, comissao_regra=RegraComissao.percentual_lucro, comissao_valor=10
    )


@pytest.fixture
def vendedor(usuario_vendedor):
    return cliente_logado(usuario_vendedor)


VEICULO = {
    "tipo": "moto",
    "marca": "Honda",
    "modelo": "CG 160 Fan",
    "ano_fabricacao": 2022,
    "ano_modelo": 2022,
    "cor": "Vermelha",
    "km": 18500,
    "placa": "abc-1d23",
    "valor_compra": "11500.00",
    "preco_venda": "14900.00",
    "situacao": "a_venda",
}


def novo_veiculo(api: TestClient, **campos) -> dict:
    r = api.post("/veiculos", json={**VEICULO, **campos})
    assert r.status_code == 201, r.text
    return r.json()


def nova_venda(api: TestClient, veiculo_id: int, **campos) -> dict:
    corpo = {
        "veiculo_id": veiculo_id,
        "cliente_novo": {"nome": "Maria Compradora", "telefone": "(86) 99999-0001"},
        "valor": "14500.00",
        "forma": "a_vista",
        **campos,
    }
    r = api.post("/vendas", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()
