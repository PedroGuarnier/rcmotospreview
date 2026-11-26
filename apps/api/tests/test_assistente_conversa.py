"""Assistente de cadastro pela rota: a conversa inteira, do rascunho ao veículo criado.

O servidor não guarda a conversa: cada teste devolve o `estado` recebido na rodada anterior.
"""

from decimal import Decimal

from sqlalchemy import select

from app.models import AuditLog, Configuracao, LaudoProcedencia, Semaforo, Veiculo
from tests.conftest import novo_veiculo

FRASE = (
    "Cadastra uma Honda CG 160 Fan 2022 vermelha, placa ABC1D23, 18.500 km, "
    "comprei por 11.500 e vou vender por 14.900"
)


class Conversa:
    """Guarda o estado entre as rodadas, como a tela faz."""

    def __init__(self, api):
        self.api = api
        self.estado = None

    def dizer(self, mensagem: str) -> dict:
        r = self.api.post(
            "/assistente/mensagem", json={"mensagem": mensagem, "estado": self.estado}
        )
        assert r.status_code == 200, r.text
        resposta = r.json()
        self.estado = resposta["estado"]
        return resposta


def ficha(resposta: dict) -> dict:
    return {item["campo"]: item["valor"] for item in resposta["ficha"]}


def nomes(lista: list[dict]) -> list[str]:
    return [item["campo"] for item in lista]


def total_de_veiculos(db) -> int:
    return len(db.scalars(select(Veiculo)).all())


def test_frase_completa_confirma_e_cria(dono, db):
    conversa = Conversa(dono)
    r = conversa.dizer(FRASE)
    assert r["acao"] == "confirmar" and r["pronto"] is True
    assert r["estado"]["aguardando"] == "confirmacao"
    assert r["faltando"] == [] and r["sugeridos"] == []
    assert ficha(r) == {
        "tipo": "Moto",
        "marca": "Honda",
        "modelo": "CG 160 Fan",
        "ano": "2022/2022",
        "cor": "Vermelha",
        "km": "18.500 km",
        "placa": "ABC-1D23",
        "valor_compra": "R$ 11.500,00",
        "preco_venda": "R$ 14.900,00",
        "situacao": "Compra",
        "lucro_previsto": "R$ 3.400,00",
    }
    assert r["avisos"] == ["Considerei 2022 como ano de fabricação e do modelo."]
    assert "Posso cadastrar?" in r["resposta"]
    assert total_de_veiculos(db) == 0  # nada é gravado antes do sim

    r = conversa.dizer("sim")
    assert r["acao"] == "criado"
    assert r["veiculo"] == {
        "id": r["veiculo"]["id"],
        "descricao": "Honda CG 160 Fan 2022 (ABC1D23)",
        "placa": "ABC1D23",
    }
    assert r["estado"] == {
        "rascunho": conversa.estado["rascunho"],
        "aguardando": None,
        "historico": [],
    }
    assert all(valor is None for valor in r["estado"]["rascunho"].values())
    assert r["ficha"] == []
    assert "fotos" in r["resposta"] and "procedência" in r["resposta"]

    v = dono.get(f"/veiculos/{r['veiculo']['id']}").json()
    assert v["situacao"] == "compra"
    assert (v["valor_compra"], v["preco_venda"], v["km"]) == ("11500.00", "14900.00", 18500)


def test_veiculo_criado_e_igual_ao_do_formulario(dono):
    conversa = Conversa(dono)
    conversa.dizer(FRASE + ", chassi 9C2KC2200NR123456, renavam 123456789, já pode anunciar")
    pelo_assistente = dono.get(f"/veiculos/{conversa.dizer('pode cadastrar')['veiculo']['id']}")
    pelo_formulario = novo_veiculo(
        dono,
        placa="XYZ1234",
        chassi="9C2KC2200NR654321",
        renavam="987654321",
        situacao="a_venda",
    )
    diferentes = {"id", "placa", "chassi", "renavam", "descricao", "situacao_desde"}
    a = {k: v for k, v in pelo_assistente.json().items() if k not in diferentes}
    b = {k: v for k, v in pelo_formulario.items() if k not in diferentes}
    assert a == b
    assert pelo_assistente.json()["chassi"] == "9C2KC2200NR123456"
    assert pelo_assistente.json()["renavam"] == "00123456789"


def test_pergunta_um_campo_por_vez_e_entende_resposta_curta(dono, db):
    conversa = Conversa(dono)
    r = conversa.dizer("chegou uma moto")
    assert r["estado"]["aguardando"] == "marca"
    assert nomes(r["faltando"]) == ["marca", "modelo", "valor_compra"]
    assert "marca e o modelo" in r["resposta"]

    r = conversa.dizer("honda")
    assert r["estado"]["aguardando"] == "modelo" and "modelo" in r["resposta"]

    r = conversa.dizer("biz 125")
    assert r["estado"]["aguardando"] == "valor_compra"
    assert nomes(r["faltando"]) == ["valor_compra"] and r["pronto"] is False
    assert "valor de compra" in r["resposta"]

    r = conversa.dizer("9 mil")
    assert r["acao"] == "confirmar" and r["pronto"] is True
    assert ficha(r)["valor_compra"] == "R$ 9.000,00"
    assert nomes(r["sugeridos"]) == ["ano_modelo", "km", "placa", "preco_venda"]
    assert "Faltou ano, km, placa e preço de venda" in r["resposta"]
    assert "posso cadastrar assim?" in r["resposta"]

    r = conversa.dizer("isso mesmo")
    assert r["acao"] == "criado" and r["veiculo"]["placa"] is None
    assert "procedência" not in r["resposta"]  # sem placa não há o que consultar
    veiculo = db.scalar(select(Veiculo))
    assert (veiculo.marca, veiculo.modelo, veiculo.valor_compra) == (
        "Honda",
        "Biz 125",
        Decimal("9000.00"),
    )


def test_honda_sem_modelo_pergunta_se_e_moto_ou_carro(dono):
    conversa = Conversa(dono)
    r = conversa.dizer("honda 2020 prata comprei por 30 mil")
    assert r["estado"]["aguardando"] == "modelo"
    r = conversa.dizer("xpto")
    assert r["estado"]["aguardando"] == "tipo" and "moto ou carro" in r["resposta"]
    r = conversa.dizer("carro")
    assert r["acao"] == "confirmar" and ficha(r)["tipo"] == "Carro"


def test_marca_e_modelo_fora_do_catalogo(dono):
    conversa = Conversa(dono)
    conversa.dizer("comprei por 18 mil")
    r = conversa.dizer("Zontes Tactic 400")
    assert (ficha(r)["marca"], ficha(r)["modelo"]) == ("Zontes", "Tactic 400")
    assert r["estado"]["aguardando"] == "tipo"
    assert conversa.dizer("moto")["acao"] == "confirmar"


def test_correcao_substitui_e_pede_confirmacao_de_novo(dono):
    conversa = Conversa(dono)
    conversa.dizer(FRASE)
    r = conversa.dizer("o km é 20 mil")
    assert ficha(r)["km"] == "20.000 km" and r["acao"] == "confirmar"
    r = conversa.dizer("não, a placa é ABC1D24")
    assert ficha(r)["placa"] == "ABC-1D24"
    r = conversa.dizer("troca a cor pra preta")
    assert ficha(r)["cor"] == "Preta"
    r = conversa.dizer("preco 15.900")
    assert ficha(r)["preco_venda"] == "R$ 15.900,00" and ficha(r)["lucro_previsto"] == "R$ 4.400,00"
    r = conversa.dizer("na verdade comprei por 11 mil")
    assert ficha(r)["valor_compra"] == "R$ 11.000,00"
    assert r["acao"] == "confirmar" and r["estado"]["aguardando"] == "confirmacao"

    r = conversa.dizer("sim, mas é modelo 2023")  # "sim" com correção não grava
    assert r["acao"] == "confirmar" and ficha(r)["ano"] == "2022/2023"

    criado = conversa.dizer("confirmo")["veiculo"]
    v = dono.get(f"/veiculos/{criado['id']}").json()
    assert (v["km"], v["placa"], v["cor"]) == (20000, "ABC1D24", "Preta")
    assert (v["preco_venda"], v["valor_compra"], v["ano_modelo"]) == ("15900.00", "11000.00", 2023)


def test_remocao(dono):
    conversa = Conversa(dono)
    conversa.dizer(FRASE)
    r = conversa.dizer("sem placa")
    assert "placa" not in ficha(r) and "Tirei da ficha: placa" in r["resposta"]
    r = conversa.dizer("tira o preco")
    assert "preco_venda" not in ficha(r) and "lucro_previsto" not in ficha(r)
    r = conversa.dizer("remove a cor")
    assert "cor" not in ficha(r)
    assert nomes(r["sugeridos"]) == ["placa", "preco_venda"] and r["acao"] == "confirmar"
    r = conversa.dizer("tira a cor")
    assert "a ficha fica sem cor" in r["resposta"]
    r = conversa.dizer("tira o valor de compra")  # obrigatório: volta a perguntar
    assert r["estado"]["aguardando"] == "valor_compra" and r["pronto"] is False


def test_cancelar_zera_o_rascunho(dono, db):
    conversa = Conversa(dono)
    conversa.dizer(FRASE)
    r = conversa.dizer("cancela")
    assert r["acao"] == "cancelado" and r["ficha"] == [] and r["pronto"] is False
    assert r["estado"]["aguardando"] is None
    assert conversa.dizer("sim")["acao"] == "nenhuma"
    assert total_de_veiculos(db) == 0
    assert conversa.dizer("deixa pra lá")["acao"] == "cancelado"  # sem nada em andamento


def test_sim_fora_de_hora_nao_cria(dono, db):
    conversa = Conversa(dono)
    r = conversa.dizer("sim")
    assert r["acao"] == "nenhuma" and "não gravei nada" in r["resposta"]
    conversa.dizer("biz 125 2021")
    r = conversa.dizer("sim")  # ainda falta o valor de compra
    assert r["acao"] == "nenhuma" and "falta o valor de compra" in r["resposta"]
    assert r["estado"]["aguardando"] == "valor_compra"
    assert total_de_veiculos(db) == 0

    # estado forjado dizendo que já pode confirmar: o servidor confere de novo
    forjado = {"rascunho": {"marca": "Honda"}, "aguardando": "confirmacao"}
    r = dono.post("/assistente/mensagem", json={"mensagem": "sim", "estado": forjado}).json()
    assert r["acao"] == "nenhuma" and r["pronto"] is False
    assert total_de_veiculos(db) == 0


def test_estado_adulterado_nao_cria_veiculo_vendido(dono, db):
    """Situação de veículo vendido só existe com venda registrada: o assistente ignora."""
    rascunho = {
        "tipo": "moto",
        "marca": "Honda",
        "modelo": "Biz 125",
        "valor_compra": "9000.00",
        "situacao": "vendido",
    }
    forjado = {"rascunho": rascunho, "aguardando": "confirmacao"}
    r = dono.post("/assistente/mensagem", json={"mensagem": "sim", "estado": forjado})
    assert r.status_code == 200 and r.json()["acao"] == "criado"
    assert db.scalar(select(Veiculo)).situacao == "compra"


def test_negacao_pura_mantem_o_rascunho(dono, db):
    conversa = Conversa(dono)
    antes = ficha(conversa.dizer(FRASE))
    r = conversa.dizer("não")
    assert r["acao"] == "nenhuma" and "O que precisa corrigir?" in r["resposta"]
    assert ficha(r) == antes
    r = conversa.dizer("sim")  # depois do não, um sim solto ainda não grava
    assert r["acao"] == "confirmar" and total_de_veiculos(db) == 0
    assert conversa.dizer("sim")["acao"] == "criado"


def test_placa_e_chassi_duplicados(dono, db):
    existente = novo_veiculo(dono, chassi="9C2KC2200NR123456")
    conversa = Conversa(dono)
    r = conversa.dizer(FRASE)
    assert r["duplicado"] == {
        "id": existente["id"],
        "descricao": "Honda CG 160 Fan 2022 (ABC1D23)",
        "campo": "placa",
    }
    assert r["pronto"] is False and r["acao"] == "nenhuma"
    assert r["estado"]["aguardando"] == "placa"
    assert "Já existe um veículo com esta placa" in r["resposta"]

    r = conversa.dizer("sim")  # não deixa confirmar enquanto não corrigir
    assert r["acao"] == "nenhuma" and r["duplicado"] is not None
    assert total_de_veiculos(db) == 1

    r = conversa.dizer("abc 1d24")  # resposta curta: é a placa certa
    assert r["duplicado"] is None and r["acao"] == "confirmar"
    assert ficha(r)["placa"] == "ABC-1D24"

    r = conversa.dizer("chassi 9C2KC2200NR123456")
    assert r["duplicado"]["campo"] == "chassi" and r["estado"]["aguardando"] == "chassi"
    r = conversa.dizer("9C2KC2200NR000001")
    assert r["duplicado"] is None and r["acao"] == "confirmar"
    assert conversa.dizer("sim")["acao"] == "criado"
    assert total_de_veiculos(db) == 2


def test_a_venda_exige_preco(dono):
    conversa = Conversa(dono)
    r = conversa.dizer("biz 125 2021 comprei por 9 mil, já pode ir pra vitrine")
    assert ficha(r)["situacao"] == "À venda"
    assert nomes(r["faltando"]) == ["preco_venda"] and r["pronto"] is False
    assert r["estado"]["aguardando"] == "preco_venda"
    r = conversa.dizer("12.900")
    assert r["acao"] == "confirmar" and ficha(r)["preco_venda"] == "R$ 12.900,00"
    criado = conversa.dizer("ok")["veiculo"]
    assert dono.get(f"/veiculos/{criado['id']}").json()["situacao"] == "a_venda"


def test_erros_de_validacao_viram_frase_e_o_rascunho_continua(dono):
    conversa = Conversa(dono)
    conversa.dizer("biz 125 comprei por 9 mil")
    r = conversa.dizer("ano 1900")
    assert "O ano 1900 está fora da faixa" in r["resposta"] and "ano" not in ficha(r)
    r = conversa.dizer("chassi 123")
    assert "Chassi inválido" in r["resposta"] and "chassi" not in ficha(r)
    r = conversa.dizer("preço 0")
    assert "precisa ser maior que zero" in r["resposta"] and "preco_venda" not in ficha(r)
    r = conversa.dizer("km 99999999")
    assert "quilometragem demais" in r["resposta"] and "km" not in ficha(r)
    r = conversa.dizer("placa abc12")
    assert "Não reconheci a placa" in r["resposta"] and "placa" not in ficha(r)
    r = conversa.dizer("vendo por 12")
    assert "12 mil" in r["resposta"] and "preco_venda" not in ficha(r)
    # o que já estava certo continua, e dá para confirmar
    assert ficha(r)["modelo"] == "Biz 125" and ficha(r)["valor_compra"] == "R$ 9.000,00"
    assert r["acao"] == "confirmar"


def test_numero_sem_pista_vira_pergunta(dono):
    conversa = Conversa(dono)
    r = conversa.dizer("biz 125 2021 9.000")
    assert "valor_compra" not in ficha(r) and "km" not in ficha(r)
    assert "não sei se é km, valor de compra ou preço de venda" in r["resposta"]
    assert r["estado"]["aguardando"] == "valor_compra"
    r = conversa.dizer("comprei por 9.000")
    assert ficha(r)["valor_compra"] == "R$ 9.000,00"


def test_preco_abaixo_da_compra_avisa(dono):
    r = Conversa(dono).dizer("biz 125 comprei por 9 mil vendo por 8 mil")
    assert "O preço de venda está abaixo do valor de compra." in r["avisos"]
    assert ficha(r)["lucro_previsto"] == "-R$ 1.000,00"


def test_ajuda_e_fora_do_escopo_nao_perdem_o_rascunho(dono, db):
    conversa = Conversa(dono)
    r = conversa.dizer("oi")
    assert "Exemplo:" in r["resposta"] and r["ficha"] == [] and r["acao"] == "nenhuma"
    r = conversa.dizer("quantas motos vendemos em outubro?")
    assert "só cadastro veículo novo" in r["resposta"] and r["ficha"] == []
    r = conversa.dizer("vendi a cg pro joão por 14 mil")
    assert "Registrar venda ainda não é comigo" in r["resposta"] and r["ficha"] == []
    r = conversa.dizer("xyzzy")
    assert "Não entendi" in r["resposta"] and "Exemplo:" in r["resposta"]

    antes = ficha(conversa.dizer(FRASE))
    for mensagem in ("como funciona?", "qual o lucro do mês?", "blablabla", "obrigado"):
        r = conversa.dizer(mensagem)
        assert ficha(r) == antes, mensagem
        assert r["acao"] == "confirmar" and r["estado"]["aguardando"] == "confirmacao"
    assert total_de_veiculos(db) == 0
    assert conversa.dizer("sim")["acao"] == "criado"


def test_pergunta_pendente_e_repetida(dono):
    conversa = Conversa(dono)
    conversa.dizer("biz 125")
    r = conversa.dizer("hein")
    assert "Não entendi" in r["resposta"] and "valor de compra" in r["resposta"]
    assert r["estado"]["aguardando"] == "valor_compra"


def test_lucro_previsto_e_imposto_so_com_custos_ver(dono, db):
    db.add(Configuracao(id=1, imposto_margem_aliquota=Decimal("6.50")))
    db.commit()
    r = Conversa(dono).dizer(FRASE)
    calculados = [item for item in r["ficha"] if item["calculado"]]
    assert [(i["campo"], i["rotulo"], i["valor"]) for i in calculados] == [
        ("lucro_previsto", "Lucro previsto", "R$ 3.400,00"),
        ("imposto_previsto", "Imposto estimado (6,5%)", "R$ 221,00"),
    ]


def test_permissoes(dono, gerente, vendedor, financeiro, anonimo):
    corpo = {"mensagem": FRASE, "estado": None}
    assert anonimo.post("/assistente/mensagem", json=corpo).status_code == 401
    assert vendedor.post("/assistente/mensagem", json=corpo).status_code == 403
    assert financeiro.post("/assistente/mensagem", json=corpo).status_code == 403
    assert gerente.post("/assistente/mensagem", json=corpo).json()["acao"] == "confirmar"
    assert dono.post("/assistente/mensagem", json=corpo).json()["acao"] == "confirmar"


def test_audit_log_registra_a_criacao(gerente, db):
    conversa = Conversa(gerente)
    conversa.dizer(FRASE)
    assert db.scalars(select(AuditLog).where(AuditLog.entidade == "veiculo")).all() == []
    criado = conversa.dizer("sim")["veiculo"]
    eventos = db.scalars(select(AuditLog).where(AuditLog.entidade == "veiculo")).all()
    assert len(eventos) == 1
    evento = eventos[0]
    assert (evento.acao, evento.usuario_nome) == ("criou", "Gerente")
    assert (evento.entidade_id, evento.veiculo_id) == (criado["id"], criado["id"])
    assert evento.resumo == "Honda CG 160 Fan 2022 (ABC1D23)"
    assert evento.alteracoes["valor_compra"] == "11500.00"
    assert evento.alteracoes["placa"] == "ABC1D23"


def test_laudo_de_procedencia_consultado_antes_passa_para_o_veiculo(dono, db):
    db.add(
        LaudoProcedencia(
            placa="ABC1D23",
            provedor="demonstracao",
            ilustrativo=True,
            semaforo=Semaforo.verde,
            dados={"veiculo": {}, "itens": []},
        )
    )
    db.commit()
    conversa = Conversa(dono)
    conversa.dizer(FRASE)
    criado = conversa.dizer("sim")["veiculo"]
    db.expire_all()
    assert db.scalar(select(LaudoProcedencia)).veiculo_id == criado["id"]


def test_validacao_do_corpo(dono):
    def enviar(corpo):
        return dono.post("/assistente/mensagem", json=corpo)

    assert enviar({"mensagem": "", "estado": None}).status_code == 422
    assert enviar({"mensagem": "   ", "estado": None}).status_code == 422
    assert enviar({"mensagem": "a" * 1001, "estado": None}).status_code == 422
    assert enviar({"mensagem": "a" * 1000, "estado": None}).status_code == 200
    assert enviar({"mensagem": "oi"}).status_code == 200  # estado é opcional
    # estado adulterado: os mesmos limites do cadastro valem
    adulterados = (
        {"placa": "123"},
        {"km": -1},
        {"ano_modelo": 1500},
        {"preco_venda": "0"},
        {"marca": "x" * 61},  # maior que a coluna do banco
        {"situacao": "inexistente"},
    )
    for rascunho in adulterados:
        estado = {"rascunho": rascunho, "aguardando": None}
        assert enviar({"mensagem": "sim", "estado": estado}).status_code == 422, rascunho
    estado = {"rascunho": {}, "aguardando": "qualquer"}
    assert enviar({"mensagem": "sim", "estado": estado}).status_code == 422


def test_rota_de_cadastro_continua_igual(dono, db):
    """A criação foi extraída para `criar_veiculo`: o formulário não pode notar diferença."""
    v = novo_veiculo(dono, renavam="123456789")
    assert (v["placa"], v["renavam"], v["situacao"]) == ("ABC1D23", "00123456789", "a_venda")
    evento = db.scalar(select(AuditLog).where(AuditLog.entidade == "veiculo"))
    assert (evento.acao, evento.usuario_nome, evento.veiculo_id) == ("criou", "Dono", v["id"])


def test_dois_veiculos_na_mesma_mensagem_nao_misturam(dono, db):
    conversa = Conversa(dono)
    r = conversa.dizer("troquei um gol 2010 numa biz 2020")
    assert (
        "mais de um veículo" in r["resposta"] and "Gol" in r["resposta"] and "Biz" in r["resposta"]
    )
    assert r["acao"] == "nenhuma" and r["ficha"] == []
    assert total_de_veiculos(db) == 0


def test_versao_escrita_depois_da_cor_entra_no_modelo(dono):
    r = Conversa(dono).dizer("strada 2018 branca cabine simples 80 mil km paguei 55 mil")
    campos = ficha(r)
    assert (campos["marca"], campos["modelo"]) == ("Fiat", "Strada Cabine Simples")
    assert (campos["cor"], campos["km"]) == ("Branca", "80.000 km")


def test_caracteres_de_controle_nao_chegam_ao_banco(dono, db):
    """NUL e companhia derrubariam a gravação no Postgres: são tirados na entrada."""
    conversa = Conversa(dono)
    conversa.dizer("biz 125 2021 branca\u0000 comprei por 9 mil")
    conversa.dizer("obs: revisada \u0007 na oficina")
    r = conversa.dizer("sim")
    assert r["acao"] == "criado"
    veiculo = db.scalar(select(Veiculo))
    assert (veiculo.modelo, veiculo.cor) == ("Biz 125", "Branca")
    assert veiculo.observacoes is not None
    assert not any(ord(c) < 32 for c in veiculo.observacoes)
    # estado devolvido pelo navegador passa pelo mesmo filtro
    estado = {"rascunho": {"marca": "Hon\u0000da", "modelo": "Biz"}, "aguardando": None}
    r = dono.post("/assistente/mensagem", json={"mensagem": "ajuda", "estado": estado})
    assert r.status_code == 200 and r.json()["estado"]["rascunho"]["marca"] == "Honda"


def test_valores_fora_da_faixa_viram_aviso_e_nao_erro(dono):
    conversa = Conversa(dono)
    r = conversa.dizer("biz 125 km 99999999 comprei por 9 mil vendo por 0")
    assert "km" not in ficha(r) and "preco_venda" not in ficha(r)
    assert "maior que zero" in r["resposta"] and "quilometragem demais" in r["resposta"]
