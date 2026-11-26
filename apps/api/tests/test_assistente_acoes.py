"""Assistente pela rota: venda e alteração de veículo por mensagem, data da compra e marca
fora do catálogo no cadastro.

Como na tela, cada teste devolve o `estado` recebido na rodada anterior.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, Perfil, RegraComissao, Situacao, Veiculo, Venda
from app.tempo import hoje
from tests.conftest import criar_usuario, novo_veiculo
from tests.test_assistente_conversa import Conversa, ficha, nomes

VENDA = "vendi a CG 160 placa ABC1D23 pro João Silva por 14.900 à vista, vendedor Carlos"


def antes_e_depois(resposta: dict) -> dict:
    return {i["campo"]: (i["antes"], i["valor"]) for i in resposta["ficha"] if i["antes"]}


def total_de_vendas(db) -> int:
    return len(db.scalars(select(Venda)).all())


@pytest.fixture
def carlos():
    return criar_usuario(
        Perfil.vendedor,
        "carlos@teste.com",
        nome="Carlos Souza",
        comissao_regra=RegraComissao.percentual_lucro,
        comissao_valor=10,
    )


# ---------- Venda ----------


def test_venda_completa_mostra_lucro_e_comissao_e_grava_pelo_servico(dono, carlos, db):
    cg = novo_veiculo(dono)  # CG 160 Fan, ABC1D23, compra 11.500, à venda por 14.900
    conversa = Conversa(dono)
    r = conversa.dizer(VENDA)
    assert r["acao"] == "confirmar" and r["pronto"] is True
    assert r["estado"]["modo"] == "venda" and r["estado"]["aguardando"] == "confirmacao"
    assert ficha(r) == {
        "veiculo": "Honda CG 160 Fan 2022 (ABC1D23)",
        "preco_anunciado": "R$ 14.900,00",
        "comprador": "João Silva",
        "valor": "R$ 14.900,00",
        "forma": "À vista",
        "vendedor": "Carlos Souza",
        "data_venda": hoje().strftime("%d/%m/%Y"),
        "lucro_previsto": "R$ 3.400,00",
        "comissao_prevista": "R$ 340,00",
    }
    assert "Posso registrar?" in r["resposta"]
    assert total_de_vendas(db) == 0  # nada é gravado antes do sim

    r = conversa.dizer("sim")
    assert r["acao"] == "registrado" and r["estado"]["modo"] is None and r["ficha"] == []
    assert r["venda"]["veiculo_id"] == cg["id"] and r["venda"]["comprador"] == "João Silva"
    assert "Comissão de Carlos Souza: R$ 340,00" in r["resposta"]

    venda = dono.get(f"/vendas/{r['venda']['id']}").json()
    assert (venda["valor"], venda["forma"], venda["vendedor"]["nome"]) == (
        "14900.00",
        "a_vista",
        "Carlos Souza",
    )
    assert venda["lucro"] == "3400.00" and venda["comissao"]["valor"] == "340.00"
    assert dono.get(f"/veiculos/{cg['id']}").json()["situacao"] == "vendido"
    eventos = db.scalars(select(AuditLog).where(AuditLog.entidade == "venda")).all()
    assert [(e.acao, e.usuario_nome) for e in eventos] == [("criou", "Dono")]


def test_venda_parcelada_pergunta_um_dado_por_vez(dono, db):
    novo_veiculo(dono, modelo="Biz 125", placa="BIZ1A25", valor_compra="9000", preco_venda="11900")
    conversa = Conversa(dono)
    r = conversa.dizer("vendi a biz pro joão")
    assert r["estado"]["aguardando"] == "valor_venda"
    assert "O preço anunciado é R$ 11.900,00" in r["resposta"]
    assert r["opcoes"] == [
        {"rotulo": "Pelo anunciado (R$ 11.900,00)", "mensagem": "pelo anunciado"}
    ]

    r = conversa.dizer("pelo anunciado")
    assert ficha(r)["valor"] == "R$ 11.900,00" and r["estado"]["aguardando"] == "forma"
    assert [o["mensagem"] for o in r["opcoes"]] == ["à vista", "financiado", "parcelado na loja"]

    r = conversa.dizer("parcelado na loja")
    assert r["estado"]["aguardando"] == "numero_parcelas"
    assert nomes(r["faltando"]) == [
        "numero_parcelas",
        "valor_parcela",
        "primeiro_vencimento",
        "vendedor",
    ]
    r = conversa.dizer("10x de 990 com 2 mil de entrada")
    assert ficha(r)["parcelas"] == "10x de R$ 990,00" and ficha(r)["entrada"] == "R$ 2.000,00"
    assert r["estado"]["aguardando"] == "primeiro_vencimento"

    vencimento = hoje() + timedelta(days=20)
    r = conversa.dizer(vencimento.strftime("%d/%m/%Y"))
    assert ficha(r)["primeiro_vencimento"] == vencimento.strftime("%d/%m/%Y")
    assert r["estado"]["aguardando"] == "vendedor"  # o dono não é vendedor: pergunta
    assert "Dono" in [o["rotulo"] for o in r["opcoes"]]

    r = conversa.dizer("eu mesmo")
    assert ficha(r)["vendedor"] == "Dono" and r["acao"] == "confirmar"
    r = conversa.dizer("confirmo")
    assert r["acao"] == "registrado"
    venda = db.scalar(select(Venda))
    assert (venda.numero_parcelas, venda.valor_parcela, venda.entrada) == (
        10,
        Decimal("990.00"),
        Decimal("2000.00"),
    )
    assert venda.primeiro_vencimento == vencimento and venda.cliente.nome == "João"


def test_parcelas_que_nao_cobrem_a_venda_nao_deixam_confirmar(dono, db):
    novo_veiculo(dono)
    vencimento = (hoje() + timedelta(days=10)).strftime("%d/%m/%Y")
    r = Conversa(dono).dizer(
        f"vendi a cg placa abc1d23 pro joão por 14.900 parcelado em 10x de 1.000, "
        f"primeira parcela {vencimento}, vendedor eu"
    )
    assert r["acao"] == "nenhuma" and r["pronto"] is False
    assert "Entrada + parcelas não cobrem o valor da venda" in r["resposta"]


def test_mais_de_um_veiculo_lista_e_pergunta(dono, db):
    branca = novo_veiculo(dono, modelo="Biz 125", placa="AAA1A11", cor="Branca", preco_venda="9900")
    preta = novo_veiculo(dono, modelo="Biz 125", placa="BBB2B22", cor="Preta", preco_venda="9500")
    conversa = Conversa(dono)
    r = conversa.dizer("vendi a biz 125 pro joão por 9.500 à vista, vendedor eu")
    assert r["estado"]["aguardando"] == "veiculo" and r["acao"] == "nenhuma"
    assert "Achei 2 veículos à venda que combinam" in r["resposta"]
    assert sorted(r["estado"]["candidatos"]) == sorted([branca["id"], preta["id"]])
    assert [o["mensagem"] for o in r["opcoes"]] == ["1", "2"]
    assert "veiculo" not in ficha(r)  # nunca escolhe sozinho

    r = conversa.dizer("a preta")
    assert ficha(r)["veiculo"] == "Honda Biz 125 2022 (BBB2B22)" and r["acao"] == "confirmar"
    assert ficha(r)["comprador"] == "João" and ficha(r)["vendedor"] == "Dono"


def test_escolha_pelo_numero_da_lista(dono):
    primeiro = novo_veiculo(dono, modelo="Biz 125", placa="AAA1A11")
    novo_veiculo(dono, modelo="Biz 125", placa="BBB2B22")
    conversa = Conversa(dono)
    r = conversa.dizer("vendi a biz pro joão por 9.500 à vista, vendedor eu")
    posicao = r["estado"]["candidatos"].index(primeiro["id"]) + 1
    r = conversa.dizer(str(posicao))
    assert ficha(r)["veiculo"].endswith("(AAA1A11)") and r["acao"] == "confirmar"


def test_placa_de_veiculo_que_nao_esta_a_venda(dono):
    novo_veiculo(dono, situacao="preparacao")
    r = Conversa(dono).dizer(VENDA)
    assert "está na etapa preparação" in r["resposta"] and "veiculo" not in ficha(r)
    assert r["estado"]["aguardando"] == "veiculo"


def test_veiculo_ja_vendido_nao_vende_de_novo(dono, carlos, db):
    conversa = Conversa(dono)
    novo_veiculo(dono)
    conversa.dizer(VENDA)
    assert conversa.dizer("sim")["acao"] == "registrado"
    r = Conversa(dono).dizer(VENDA)
    assert "já foi vendido" in r["resposta"] and total_de_vendas(db) == 1


def test_vendedor_ambiguo_pergunta(dono, carlos, db):
    criar_usuario(Perfil.vendedor, "carlos2@teste.com", nome="Carlos Lima")
    novo_veiculo(dono)
    conversa = Conversa(dono)
    r = conversa.dizer(VENDA)
    assert "Tem mais de uma pessoa chamada Carlos" in r["resposta"]
    assert r["estado"]["aguardando"] == "vendedor" and "vendedor" not in ficha(r)
    assert [o["rotulo"] for o in r["opcoes"]] == ["Carlos Lima", "Carlos Souza"]
    r = conversa.dizer("2")
    assert ficha(r)["vendedor"] == "Carlos Souza" and r["acao"] == "confirmar"


def test_vendedor_desconhecido_avisa(dono):
    novo_veiculo(dono)
    r = Conversa(dono).dizer(VENDA.replace("Carlos", "Fulano"))
    assert "Não achei ninguém ativo na equipe chamado “Fulano”" in r["resposta"]
    assert r["estado"]["aguardando"] == "vendedor"


def test_vendedor_registra_a_propria_venda_sem_ver_lucro(dono, vendedor, carlos, db):
    novo_veiculo(dono)
    conversa = Conversa(vendedor)
    r = conversa.dizer("vendi a cg placa abc1d23 pro joão silva por 14.900 à vista")
    assert ficha(r)["vendedor"] == "Vendedor" and r["acao"] == "confirmar"
    assert not any(i["calculado"] for i in r["ficha"])  # sem lucro, imposto nem comissão
    r = conversa.dizer("sim")
    assert r["acao"] == "registrado" and "Comissão" not in r["resposta"]
    assert db.scalar(select(Venda)).vendedor.nome == "Vendedor"


def test_vendedor_nao_registra_em_nome_de_outro(dono, vendedor, carlos):
    novo_veiculo(dono)
    r = Conversa(vendedor).dizer(VENDA)
    assert "só pode registrar vendas em seu nome" in r["resposta"]
    assert ficha(r)["vendedor"] == "Vendedor"


@pytest.mark.parametrize("perfil", ["dono", "gerente", "vendedor"])
def test_quem_registra_venda_pelo_assistente(perfil, dono, gerente, vendedor, carlos, db):
    novo_veiculo(dono)
    api = {"dono": dono, "gerente": gerente, "vendedor": vendedor}[perfil]
    conversa = Conversa(api)
    conversa.dizer("vendi a cg placa abc1d23 pro joão por 14.900 à vista, vendedor eu")
    assert conversa.dizer("sim")["acao"] == "registrado"
    assert total_de_vendas(db) == 1


def test_financeiro_nao_usa_o_assistente(financeiro, dono):
    novo_veiculo(dono)
    r = financeiro.post("/assistente/mensagem", json={"mensagem": VENDA})
    assert r.status_code == 403


def test_vendedor_nao_cadastra_nem_altera_veiculo(dono, vendedor, db):
    novo_veiculo(dono)
    conversa = Conversa(vendedor)
    r = conversa.dizer("chegou uma biz 125 2021 comprei por 9 mil")
    assert "não cadastra veículos" in r["resposta"] and r["ficha"] == []
    r = conversa.dizer("a CG placa ABC1D23 agora custa 13.900")
    assert "não altera veículos" in r["resposta"] and r["ficha"] == []
    # estado forjado pelo navegador também não passa
    forjado = {
        "rascunho": {"tipo": "moto", "marca": "Honda", "modelo": "Biz", "valor_compra": "9000"},
        "aguardando": "confirmacao",
    }
    r = vendedor.post("/assistente/mensagem", json={"mensagem": "sim", "estado": forjado})
    assert r.status_code == 200 and r.json()["acao"] == "nenhuma"
    forjado = {
        "modo": "edicao",
        "edicao": {"veiculo_id": 1, "mudancas": {"preco_venda": "1000"}},
        "aguardando": "confirmacao",
    }
    r = vendedor.post("/assistente/mensagem", json={"mensagem": "sim", "estado": forjado})
    assert r.json()["acao"] == "nenhuma"
    assert db.scalar(select(Veiculo)).preco_venda == Decimal("14900.00")


def test_estado_forjado_de_venda_e_conferido_de_novo(dono, db):
    parado = novo_veiculo(dono, situacao="preparacao")
    forjado = {
        "modo": "venda",
        "venda": {
            "veiculo_id": parado["id"],
            "comprador": "João",
            "valor": "14900",
            "forma": "a_vista",
            "vendedor_id": 1,
        },
        "aguardando": "confirmacao",
    }
    r = dono.post("/assistente/mensagem", json={"mensagem": "sim", "estado": forjado}).json()
    assert r["acao"] != "registrado" and "está na etapa preparação" in r["resposta"]
    assert total_de_vendas(db) == 0


def test_cancelar_venda_nao_grava(dono, carlos, db):
    novo_veiculo(dono)
    conversa = Conversa(dono)
    conversa.dizer(VENDA)
    r = conversa.dizer("cancela")
    assert r["acao"] == "cancelado" and r["estado"]["modo"] is None
    assert conversa.dizer("sim")["acao"] == "nenhuma"
    assert total_de_vendas(db) == 0


def test_correcao_antes_de_confirmar(dono, carlos, db):
    novo_veiculo(dono)
    conversa = Conversa(dono)
    conversa.dizer(VENDA)
    r = conversa.dizer("não, foi 14 mil")
    assert ficha(r)["valor"] == "R$ 14.000,00" and r["acao"] == "confirmar"
    assert "Valor abaixo do anunciado (R$ 14.900,00)." in r["avisos"]
    r = conversa.dizer("financiado pelo bradesco com entrada de 4 mil")
    assert ficha(r)["forma"] == "Financiado pelo banco (Bradesco)"
    assert ficha(r)["entrada"] == "R$ 4.000,00"
    assert conversa.dizer("sim")["acao"] == "registrado"
    venda = db.scalar(select(Venda))
    assert (venda.forma, venda.banco, venda.entrada) == (
        "financiado_banco",
        "Bradesco",
        Decimal("4000.00"),
    )


def test_data_da_venda_futura_e_erro(dono, carlos):
    novo_veiculo(dono)
    futura = (hoje() + timedelta(days=40)).strftime("%d/%m/%Y")
    r = Conversa(dono).dizer(f"{VENDA} em {futura}")
    assert "A data da venda não pode ser futura" in r["resposta"]
    assert ficha(r)["data_venda"] == hoje().strftime("%d/%m/%Y")


def test_venda_com_cadastro_em_andamento_pede_para_terminar(dono):
    conversa = Conversa(dono)
    conversa.dizer("chegou uma biz 125 2021 comprei por 9 mil")
    r = conversa.dizer(VENDA)
    assert "Há um cadastro em andamento" in r["resposta"]
    assert ficha(r)["modelo"] == "Biz 125" and r["estado"]["modo"] is None


# ---------- Alteração ----------


def test_alteracao_mostra_antes_e_depois_e_grava_pelo_mesmo_caminho(dono, db):
    cg = novo_veiculo(dono)
    conversa = Conversa(dono)
    r = conversa.dizer("a CG placa ABC1D23 agora custa 13.900")
    assert r["estado"]["modo"] == "edicao" and r["acao"] == "confirmar"
    assert antes_e_depois(r) == {
        "preco_venda": ("R$ 14.900,00", "R$ 13.900,00"),
        "lucro_previsto": ("R$ 3.400,00", "R$ 2.400,00"),
    }
    assert ficha(r)["veiculo"] == "Honda CG 160 Fan 2022 (ABC1D23)"
    assert db.scalar(select(Veiculo)).preco_venda == Decimal("14900.00")  # ainda não gravou

    r = conversa.dizer("sim")
    assert r["acao"] == "atualizado" and r["veiculo"]["id"] == cg["id"]
    assert "Se quiser, adicione fotos aqui mesmo" in r["resposta"]
    db.expire_all()
    assert db.scalar(select(Veiculo)).preco_venda == Decimal("13900.00")
    evento = db.scalar(
        select(AuditLog).where(AuditLog.entidade == "veiculo", AuditLog.acao == "alterou")
    )
    assert evento.usuario_nome == "Dono"
    assert evento.alteracoes["preco_venda"] == {"de": "14900.00", "para": "13900.00"}


@pytest.mark.parametrize(
    "mensagem, campo, antes, depois",
    [
        ("a XRE 300 tá com 15 mil km", "km", "20.000 km", "15.000 km"),
        ("muda a cor da XRE para azul", "cor", "Vermelha", "Azul"),
        ("põe a XRE 300 vermelha em preparação", "situacao", "À venda", "Preparação"),
        (
            "corrige o valor de compra da xre pra 18 mil",
            "valor_compra",
            "R$ 19.000,00",
            "R$ 18.000,00",
        ),
        ("a placa da xre agora é ABC1D24", "placa", "XRE-3A00", "ABC-1D24"),
    ],
)
def test_alteracoes_por_mensagem(dono, db, mensagem, campo, antes, depois):
    novo_veiculo(dono, modelo="XRE 300", placa="XRE3A00", km=20000, valor_compra="19000")
    conversa = Conversa(dono)
    r = conversa.dizer(mensagem)
    assert antes_e_depois(r)[campo] == (antes, depois), r["resposta"]
    assert conversa.dizer("sim")["acao"] == "atualizado"


def test_por_a_venda_sem_preco_pede_o_preco(dono, db):
    novo_veiculo(
        dono,
        modelo="Biz 125",
        placa="BIZ1A25",
        cor="Branca",
        situacao="preparacao",
        preco_venda=None,
    )
    conversa = Conversa(dono)
    r = conversa.dizer("põe a Biz 125 branca à venda")
    assert r["acao"] == "nenhuma" and r["estado"]["aguardando"] == "preco_venda"
    assert "preciso do preço" in r["resposta"]
    r = conversa.dizer("9.900")
    assert antes_e_depois(r) == {
        "preco_venda": ("—", "R$ 9.900,00"),
        "situacao": ("Preparação", "À venda"),
        "lucro_previsto": ("—", "-R$ 1.600,00"),
    }
    assert r["acao"] == "confirmar"
    assert conversa.dizer("sim")["acao"] == "atualizado"
    db.expire_all()
    veiculo = db.scalar(select(Veiculo))
    assert (veiculo.situacao, veiculo.preco_venda) == (Situacao.a_venda, Decimal("9900.00"))


def test_tirar_preco_de_veiculo_a_venda_nao_deixa(dono):
    novo_veiculo(dono)
    r = Conversa(dono).dizer("tira o preço da cg placa abc1d23")
    assert "Veículo à venda precisa ter preço de venda" in r["resposta"] and r["pronto"] is False


def test_alteracao_com_dois_veiculos_pergunta(dono):
    novo_veiculo(dono, modelo="Biz 125", placa="AAA1A11", cor="Branca")
    novo_veiculo(dono, modelo="Biz 125", placa="BBB2B22", cor="Branca")
    conversa = Conversa(dono)
    r = conversa.dizer("a biz agora custa 9 mil")
    assert r["estado"]["aguardando"] == "veiculo" and "Achei 2 veículos" in r["resposta"]
    r = conversa.dizer("placa BBB2B22")
    assert ficha(r)["veiculo"].endswith("(BBB2B22)")
    assert antes_e_depois(r)["preco_venda"][1] == "R$ 9.000,00" and r["acao"] == "confirmar"


def test_veiculo_nao_encontrado_na_alteracao(dono):
    r = Conversa(dono).dizer("a XRE 300 tá com 15 mil km")
    assert "Não encontrei XRE 300 no estoque" in r["resposta"]


def test_veiculo_vendido_nao_muda_o_preco(dono, carlos):
    novo_veiculo(dono)
    conversa = Conversa(dono)
    conversa.dizer(VENDA)
    conversa.dizer("sim")
    r = Conversa(dono).dizer("a CG placa ABC1D23 agora custa 13.900")
    assert "já foi vendido: o preço de venda não muda mais" in r["resposta"]
    assert r["pronto"] is False


def test_cancelar_alteracao(dono, db):
    novo_veiculo(dono)
    conversa = Conversa(dono)
    conversa.dizer("a CG placa ABC1D23 agora custa 13.900")
    assert conversa.dizer("cancela")["acao"] == "cancelado"
    assert db.scalar(select(Veiculo)).preco_venda == Decimal("14900.00")


def test_patch_do_formulario_continua_igual(dono, db):
    """A edição foi extraída para `atualizar_veiculo`: o formulário não pode notar diferença."""
    v = novo_veiculo(dono, situacao="preparacao", preco_venda=None)
    r = dono.patch(f"/veiculos/{v['id']}", json={"situacao": "a_venda"})
    assert r.status_code == 422 and "preço de venda" in r.json()["detail"]
    r = dono.patch(f"/veiculos/{v['id']}", json={"preco_venda": "15000", "situacao": "a_venda"})
    assert r.status_code == 200 and r.json()["situacao"] == "a_venda"
    r = dono.patch(f"/veiculos/{v['id']}", json={"preco_venda": None})
    assert (
        r.status_code == 422 and r.json()["detail"] == "Veículo à venda precisa ter preço de venda."
    )


# ---------- Cadastro: data da compra e marca fora do catálogo ----------


def test_data_da_compra_no_cadastro(dono, db):
    conversa = Conversa(dono)
    r = conversa.dizer("chegou uma biz 125 2021 branca, comprei ontem por 9 mil")
    ontem = hoje() - timedelta(days=1)
    assert ficha(r)["data_compra"] == ontem.strftime("%d/%m/%Y")
    assert "comprado em" in r["resposta"]
    assert conversa.dizer("sim")["acao"] == "criado"
    assert db.scalar(select(Veiculo)).data_compra == ontem


def test_sem_data_da_compra_fica_como_o_formulario(dono, db):
    conversa = Conversa(dono)
    conversa.dizer("chegou uma biz 125 2021 comprei por 9 mil")
    conversa.dizer("sim")
    assert db.scalar(select(Veiculo)).data_compra is None  # o formulário também deixa vazia


def test_data_da_compra_futura_e_erro(dono):
    futura = (hoje() + timedelta(days=30)).strftime("%d/%m/%Y")
    r = Conversa(dono).dizer(f"biz 125 comprei {futura} por 9 mil")
    assert "A data da compra não pode ser futura" in r["resposta"]
    assert "data_compra" not in ficha(r) and r["acao"] == "confirmar"


def test_data_da_compra_ambigua_vira_pergunta(dono):
    dia = hoje() + timedelta(days=1)
    if dia.month != hoje().month:
        pytest.skip("no último dia do mês, 'dia de amanhã' é do mês seguinte")
    conversa = Conversa(dono)
    r = conversa.dizer(f"biz 125 comprei dia {dia.day} por 9 mil")
    assert "Fiquei na dúvida sobre a data da compra" in r["resposta"]
    assert r["estado"]["aguardando"] == "data_compra" and r["acao"] == "nenhuma"
    assert len(r["opcoes"]) == 1
    sugerida = r["opcoes"][0]["mensagem"]  # o mesmo dia, no mês passado
    assert sugerida.startswith(f"{dia.day:02d}/")
    r = conversa.dizer(sugerida)
    assert ficha(r)["data_compra"] == sugerida and r["acao"] == "confirmar"


def test_marca_fora_do_catalogo_pergunta_moto_ou_carro(dono, db):
    conversa = Conversa(dono)
    r = conversa.dizer("lifan 530 2015 prata comprei por 20 mil")
    assert (ficha(r)["marca"], ficha(r)["modelo"]) == ("Lifan", "530")
    assert r["estado"]["aguardando"] == "tipo"
    assert "Lifan 530 é moto ou carro?" in r["resposta"]
    r = conversa.dizer("carro")
    assert r["acao"] == "confirmar"
    assert conversa.dizer("sim")["acao"] == "criado"
    veiculo = db.scalar(select(Veiculo))
    assert (veiculo.tipo, veiculo.marca, veiculo.modelo) == ("carro", "Lifan", "530")


def test_venda_no_meio_de_uma_alteracao(dono, carlos, db):
    novo_veiculo(dono)
    conversa = Conversa(dono)
    conversa.dizer("a CG placa ABC1D23 agora custa 13.900")
    r = conversa.dizer(VENDA)
    assert "Deixei a alteração de lado" in r["resposta"]
    assert r["estado"]["modo"] == "venda" and r["acao"] == "confirmar"
    assert db.scalar(select(Veiculo)).preco_venda == Decimal("14900.00")
