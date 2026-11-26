"""Venda por mensagem: "vendi a CG placa ABC1D23 pro João Silva por 14.900 à vista".

Acha o veículo entre os que estão à venda (mais de um candidato vira pergunta), junta os
dados da baixa, mostra a ficha com lucro e comissão previstos (só para quem vê custos), pede
confirmação e grava pelo mesmo serviço da tela (`servicos.registrar_venda`): mesmas regras,
mesmo audit log. Nada é gravado antes do "sim".
"""

from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import assistente_busca as busca
from app import assistente_datas, schemas, servicos
from app.assistente import Interpretacao, _lista, _moeda, _percentual, interpretar
from app.models import Cliente, FormaPagamento, Situacao, Usuario, Veiculo
from app.permissoes import P, pode
from app.tempo import hoje

FORMAS = {
    FormaPagamento.a_vista: "À vista",
    FormaPagamento.financiado_banco: "Financiado pelo banco",
    FormaPagamento.parcelado_loja: "Parcelado na loja",
}
_ROTULOS = {
    "veiculo": "Veículo",
    "comprador": "Comprador",
    "valor": "Valor da venda",
    "forma": "Forma de pagamento",
    "numero_parcelas": "Nº de parcelas",
    "valor_parcela": "Valor da parcela",
    "primeiro_vencimento": "1º vencimento",
    "vendedor": "Vendedor",
}
_AGUARDANDO = {
    "veiculo": "veiculo",
    "comprador": "comprador",
    "valor": "valor_venda",
    "forma": "forma",
    "numero_parcelas": "numero_parcelas",
    "valor_parcela": "valor_parcela",
    "primeiro_vencimento": "primeiro_vencimento",
    "vendedor": "vendedor",
}
_PARCELAS = ("numero_parcelas", "valor_parcela", "primeiro_vencimento")
_CAMPOS = (
    "comprador",
    "telefone",
    "cpf_cnpj",
    "valor",
    "forma",
    "banco",
    "entrada",
    "numero_parcelas",
    "valor_parcela",
    "primeiro_vencimento",
    "data_venda",
)
EXEMPLO = "vendi a CG 160 placa ABC1D23 pro João Silva por 14.900 à vista"


def texto_ajuda() -> str:
    return (
        "Para registrar uma venda, escreva do jeito que você fala: o veículo (placa, final da "
        "placa ou modelo), o comprador, o valor e a forma de pagamento.\n"
        f"Exemplo: {EXEMPLO}, vendedor Carlos.\n"
        "Parcelado na loja: “em 10x de 1.200, primeira parcela dia 10/12”. "
        "Antes de gravar eu mostro a ficha da venda e peço a sua confirmação."
    )


def _telefone(numero: str) -> str:
    if len(numero) == 11:
        return f"({numero[:2]}) {numero[2:7]}-{numero[7:]}"
    if len(numero) == 10:
        return f"({numero[:2]}) {numero[2:6]}-{numero[6:]}"
    return numero


def _normal(texto: str) -> str:
    return " ".join(busca._palavras(texto))


def _cliente_existente(db: Session, dados: dict) -> Cliente | None:
    """O comprador já está cadastrado? Pelo CPF/CNPJ, ou pelo nome igual (um só, e com o mesmo
    telefone quando os dois têm). Senão a venda cadastra um cliente novo, como a tela."""
    if dados.get("cpf_cnpj"):
        return db.scalar(select(Cliente).where(Cliente.cpf_cnpj == dados["cpf_cnpj"]))
    nome = dados.get("comprador")
    if not nome:
        return None
    primeira = busca._palavras(nome)[0] if busca._palavras(nome) else ""
    parecidos = db.scalars(select(Cliente).where(Cliente.nome.ilike(f"%{primeira}%"))).all()
    iguais = [c for c in parecidos if _normal(c.nome) == _normal(nome)]
    if len(iguais) != 1:
        return None
    cliente = iguais[0]
    telefone = dados.get("telefone")
    if telefone and cliente.telefone and cliente.telefone != telefone:
        return None
    return cliente


def _a_venda(veiculo: Veiculo) -> bool:
    return veiculo.situacao == Situacao.a_venda and veiculo.venda_ativa is None


def _por_que_nao_vende(veiculo: Veiculo) -> str:
    if veiculo.venda_ativa is not None:
        venda = veiculo.venda_ativa
        return (
            f"{veiculo.descricao} já foi vendido em "
            f"{assistente_datas.formatar(venda.data_venda)} para {venda.cliente.nome}."
        )
    return (
        f"{veiculo.descricao} está na etapa {busca.SITUACOES[veiculo.situacao]}. Para registrar a "
        "venda ele precisa estar à venda, com preço: mude a etapa primeiro (por exemplo, "
        f"“põe a {veiculo.modelo} à venda”)."
    )


def conversar_venda(
    db: Session,
    usuario: Usuario,
    mensagem: str,
    estado: schemas.AssistenteEstado | None,
    lido: Interpretacao | None = None,
) -> schemas.AssistenteResposta:
    """Uma rodada da venda por mensagem. `lido` vem pronto quando a venda começa agora."""
    continuando = estado is not None and estado.modo == "venda"
    dados: dict[str, Any] = (
        estado.venda.model_dump(exclude_none=True) if continuando and estado.venda else {}
    )
    aguardando = estado.aguardando if continuando else None
    candidatos = list(estado.candidatos) if continuando else []
    paragrafos: list[str] = []
    avisos: list[str] = []
    opcoes: list[schemas.AssistenteOpcao] = []
    acao = "nenhuma"
    registrada: schemas.AssistenteVendaRegistrada | None = None
    terminou = False
    ve_custos = pode(usuario, P.custos_ver)

    def responder(
        proximo: str | None, escolhas: list[int] | None = None
    ) -> schemas.AssistenteResposta:
        campos = schemas.AssistenteVendaRascunho.model_fields
        guardar = {k: v for k, v in dados.items() if k in campos}
        faltam = [] if terminou else _faltando()
        return schemas.AssistenteResposta(
            resposta="\n".join(p for p in paragrafos if p),
            estado=schemas.AssistenteEstado(
                modo=None if terminou else "venda",
                venda=None if terminou else schemas.AssistenteVendaRascunho(**guardar),
                aguardando=None if terminou else proximo,
                candidatos=[] if terminou else (escolhas or []),
            ),
            ficha=[] if terminou else _ficha(),
            faltando=[schemas.AssistenteCampo(campo=c, rotulo=_ROTULOS[c]) for c in faltam],
            sugeridos=[],
            pronto=acao == "confirmar",
            acao=acao,
            avisos=avisos,
            venda=registrada,
            opcoes=opcoes,
        )

    if not pode(usuario, P.vendas_registrar):
        terminou = True
        paragrafos.append("Seu perfil não registra vendas. Peça a quem registra (gerente ou dono).")
        return responder(None)

    # Veículo que já estava na ficha: confere de novo (o estado vem do navegador e o estoque
    # pode ter mudado desde a última mensagem).
    veiculo: Veiculo | None = None
    if dados.get("veiculo_id"):
        veiculo = busca.obter(db, dados["veiculo_id"])
        if veiculo is None or not _a_venda(veiculo):
            if veiculo is not None:
                paragrafos.append(_por_que_nao_vende(veiculo))
            dados.pop("veiculo_id")
            veiculo = None
    if dados.get("vendedor_id"):
        vendedor = db.get(Usuario, dados["vendedor_id"])
        if vendedor is None or not vendedor.ativo:
            dados.pop("vendedor_id")

    escolha_pendente: tuple[str, list[int]] | None = None
    perguntas: list[tuple[str, str, Any]] = []

    def _faltando() -> list[str]:
        faltam = []
        if veiculo is None:
            faltam.append("veiculo")
        if not dados.get("comprador"):
            faltam.append("comprador")
        if "valor" not in dados:
            faltam.append("valor")
        if "forma" not in dados:
            faltam.append("forma")
        elif dados["forma"] == FormaPagamento.parcelado_loja:
            faltam.extend(c for c in _PARCELAS if c not in dados)
        if "vendedor_id" not in dados:
            faltam.append("vendedor")
        return faltam

    def _ficha() -> list[schemas.AssistenteItemFicha]:
        itens: list[schemas.AssistenteItemFicha] = []

        def item(campo: str, rotulo: str, valor: str, calculado: bool = False) -> None:
            itens.append(
                schemas.AssistenteItemFicha(
                    campo=campo, rotulo=rotulo, valor=valor, calculado=calculado
                )
            )

        if veiculo is not None:
            item("veiculo", "Veículo", veiculo.descricao)
            if veiculo.preco_venda is not None:
                item("preco_anunciado", "Preço anunciado", _moeda(veiculo.preco_venda))
        if dados.get("comprador"):
            cliente = _cliente_existente(db, dados)
            item(
                "comprador",
                "Comprador",
                dados["comprador"] + (" (já é cliente)" if cliente else ""),
            )
        if dados.get("telefone"):
            item("telefone", "WhatsApp", _telefone(dados["telefone"]))
        if dados.get("cpf_cnpj"):
            item("cpf_cnpj", "CPF/CNPJ", dados["cpf_cnpj"])
        if "valor" in dados:
            item("valor", "Valor da venda", _moeda(dados["valor"]))
        if "forma" in dados:
            forma = FORMAS[dados["forma"]]
            if dados.get("banco"):
                forma += f" ({dados['banco']})"
            item("forma", "Forma de pagamento", forma)
        if dados.get("entrada") is not None:
            item("entrada", "Entrada", _moeda(dados["entrada"]))
        if dados.get("numero_parcelas"):
            texto = f"{dados['numero_parcelas']}x"
            if dados.get("valor_parcela"):
                texto += f" de {_moeda(dados['valor_parcela'])}"
            item("parcelas", "Parcelas", texto)
        elif dados.get("valor_parcela"):
            item("parcelas", "Valor da parcela", _moeda(dados["valor_parcela"]))
        if dados.get("primeiro_vencimento"):
            item(
                "primeiro_vencimento",
                "1º vencimento",
                assistente_datas.formatar(dados["primeiro_vencimento"]),
            )
        vendedor = db.get(Usuario, dados["vendedor_id"]) if dados.get("vendedor_id") else None
        if vendedor is not None:
            item("vendedor", "Vendedor", vendedor.nome)
        if itens:
            item(
                "data_venda",
                "Data da venda",
                assistente_datas.formatar(dados.get("data_venda") or hoje()),
            )
        if ve_custos and veiculo is not None and "valor" in dados:
            valor = dados["valor"]
            lucro = servicos.calcular_lucro(valor, veiculo.valor_compra, veiculo.total_custos)
            item("lucro_previsto", "Lucro previsto", _moeda(lucro), True)
            aliquota = servicos.aliquota_imposto(db)
            if aliquota > 0:
                imposto = servicos.calcular_imposto(valor, veiculo.valor_compra, aliquota)
                item(
                    "imposto_previsto",
                    f"Imposto estimado ({_percentual(aliquota)})",
                    _moeda(imposto),
                    True,
                )
            if vendedor and vendedor.comissao_regra and vendedor.comissao_valor is not None:
                comissao = servicos.calcular_comissao(
                    vendedor.comissao_regra, vendedor.comissao_valor, valor, lucro
                )
                item("comissao_prevista", f"Comissão de {vendedor.nome}", _moeda(comissao), True)
        return itens

    def montar() -> schemas.VendaCriar:
        assert veiculo is not None
        cliente = _cliente_existente(db, dados)
        corpo: dict[str, Any] = {
            "veiculo_id": veiculo.id,
            "valor": dados.get("valor"),
            "forma": dados.get("forma"),
            "vendedor_id": dados.get("vendedor_id"),
            "data_venda": dados.get("data_venda") or hoje(),
        }
        if cliente is not None:
            corpo["cliente_id"] = cliente.id
        else:
            corpo["cliente_novo"] = {
                "nome": dados.get("comprador"),
                "telefone": dados.get("telefone"),
                "cpf_cnpj": dados.get("cpf_cnpj"),
            }
        for campo in ("banco", "entrada", *_PARCELAS):
            if dados.get(campo) is not None:
                corpo[campo] = dados[campo]
        return schemas.VendaCriar.model_validate(corpo)

    def perguntar(campo: str) -> schemas.AssistenteResposta:
        escolhas: list[int] = []
        if campo == "veiculo":
            paragrafos.append(
                "Qual veículo foi vendido? Mande a placa (ou o final dela) ou o modelo, por "
                "exemplo: “Biz 125 branca”."
            )
        elif campo == "comprador":
            paragrafos.append("Quem comprou? Mande o nome do comprador (e o WhatsApp, se tiver).")
        elif campo == "valor":
            frase = "Por quanto foi a venda?"
            if veiculo is not None and veiculo.preco_venda is not None:
                anunciado = _moeda(veiculo.preco_venda)
                frase += f" O preço anunciado é {anunciado}."
                opcoes.append(
                    schemas.AssistenteOpcao(
                        rotulo=f"Pelo anunciado ({anunciado})", mensagem="pelo anunciado"
                    )
                )
            paragrafos.append(frase)
        elif campo == "forma":
            paragrafos.append(
                "Qual foi a forma de pagamento: à vista, financiado pelo banco ou parcelado "
                "na loja?"
            )
            opcoes.extend(
                [
                    schemas.AssistenteOpcao(rotulo="À vista", mensagem="à vista"),
                    schemas.AssistenteOpcao(rotulo="Financiado pelo banco", mensagem="financiado"),
                    schemas.AssistenteOpcao(
                        rotulo="Parcelado na loja", mensagem="parcelado na loja"
                    ),
                ]
            )
        elif campo == "numero_parcelas":
            paragrafos.append("Em quantas parcelas na loja? Por exemplo: “10x de 1.200”.")
        elif campo == "valor_parcela":
            paragrafos.append("Qual é o valor de cada parcela? Por exemplo: 1.200.")
        elif campo == "primeiro_vencimento":
            paragrafos.append("Quando vence a primeira parcela? Por exemplo: 10/12/2026.")
        elif campo == "vendedor":
            equipe = busca.usuarios_ativos(db)[: busca.MAXIMO_DE_OPCOES]
            paragrafos.append("Quem foi o vendedor?")
            escolhas = [u.id for u in equipe]
            opcoes.extend(
                schemas.AssistenteOpcao(rotulo=u.nome, mensagem=str(n))
                for n, u in enumerate(equipe, start=1)
            )
        return responder(_AGUARDANDO[campo], escolhas)

    def seguir() -> schemas.AssistenteResposta:
        nonlocal acao
        if escolha_pendente:
            return responder(*escolha_pendente)
        if perguntas:
            campo, pergunta, sugestao = perguntas[0]
            paragrafos.append(pergunta)
            if sugestao:
                data = assistente_datas.formatar(sugestao)
                opcoes.append(schemas.AssistenteOpcao(rotulo=data, mensagem=data))
            return responder(campo)
        faltam = _faltando()
        if faltam:
            return perguntar(faltam[0])
        try:
            montar()
        except ValidationError as erro:
            paragrafos.append(f"Antes de registrar: {_frase_validacao(erro)}")
            return responder(None)
        acao = "confirmar"
        paragrafos.append("Confira a venda. Posso registrar?")
        return responder("confirmacao")

    # 1. Escolha numa lista que o assistente mostrou ("2", "a segunda")
    escolha = None
    if aguardando in ("veiculo", "vendedor") and candidatos:
        escolha = busca.escolha_na_lista(mensagem, len(candidatos))
    if escolha is not None:
        escolhido = candidatos[escolha - 1]
        if aguardando == "veiculo":
            achado = busca.obter(db, escolhido)
            if achado is not None and _a_venda(achado):
                veiculo, dados["veiculo_id"] = achado, achado.id
            elif achado is not None:
                paragrafos.append(_por_que_nao_vende(achado))
        else:
            _definir_vendedor(db, usuario, dados, escolhido, paragrafos)
        return seguir()

    if lido is None:
        lido = interpretar(mensagem, aguardando, contexto="venda")

    # 2. Cancelar, confirmar, negar
    if lido.intencao == "cancelar":
        terminou, acao = True, "cancelado"
        paragrafos.append("Pronto, descartei a venda. Nada foi gravado.")
        return responder(None)
    if lido.intencao == "afirmacao":
        if aguardando == "confirmacao" and not _faltando():
            try:
                corpo = montar()
                venda = servicos.registrar_venda(db, corpo, usuario)
                db.commit()
            except ValidationError as erro:
                paragrafos.append(f"Não consegui registrar: {_frase_validacao(erro)}")
                return seguir()
            except HTTPException as erro:
                db.rollback()
                paragrafos.append(f"Não consegui registrar: {erro.detail}")
                return seguir()
            except IntegrityError:
                db.rollback()
                paragrafos.append(
                    "Não consegui registrar: veículo já vendido ou CPF/CNPJ já cadastrado."
                )
                return seguir()
            assert veiculo is not None
            terminou, acao = True, "registrado"
            registrada = schemas.AssistenteVendaRegistrada(
                id=venda.id,
                veiculo_id=veiculo.id,
                descricao=veiculo.descricao,
                comprador=venda.cliente.nome,
                valor=venda.valor,
            )
            frase = (
                f"Pronto! Venda registrada: {veiculo.descricao} para {venda.cliente.nome} por "
                f"{_moeda(venda.valor)} ({FORMAS[venda.forma].lower()})."
            )
            if ve_custos and venda.comissao is not None:
                frase += (
                    f"\nComissão de {venda.vendedor.nome}: {_moeda(venda.comissao.valor)} "
                    "(pendente)."
                )
            paragrafos.append(frase + "\nEla já aparece em Vendas e no painel.")
            return responder(None)
        if _faltando():
            nomes = _lista([_ROTULOS[c].lower() for c in _faltando()])
            paragrafos.append(f"Ainda não dá para registrar: falta {nomes}.")
        return seguir()
    if lido.intencao in ("negacao", "dispensa"):
        if aguardando == "confirmacao":
            paragrafos.append(
                "Sem problema, não gravei nada. O que precisa corrigir? Por exemplo: "
                "“o valor foi 14 mil”, “foi parcelado em 10x de 1.500” ou “vendedor Carlos”."
            )
            return responder(None)
        paragrafos.append("Tudo bem, não gravei nada.")
        return seguir()
    if lido.intencao == "ajuda":
        paragrafos.append(texto_ajuda())
        return seguir()
    if lido.intencao != "venda":
        paragrafos.append(
            "Não entendi essa mensagem. Sobre a venda em andamento: responda o que perguntei, "
            "corrija algum dado ou diga “cancela” para desistir."
        )
        return seguir()

    # 3. Dados da venda: junta à ficha
    paragrafos.extend(lido.erros)
    vd = lido.venda_dados
    for campo in _CAMPOS:
        if campo in vd:
            dados[campo] = vd[campo]
    forma = dados.get("forma")
    if forma is not None and forma != FormaPagamento.parcelado_loja:
        tinha = [c for c in _PARCELAS if c in dados]
        for c in _PARCELAS:
            dados.pop(c, None)
        if tinha and any(c in vd for c in _PARCELAS):
            avisos.append(
                "Parcelas só são anotadas no parcelado na loja: as do financiamento ficam "
                "com o banco."
            )
    if forma == FormaPagamento.a_vista:
        dados.pop("entrada", None)
    if forma is not None and forma != FormaPagamento.financiado_banco:
        dados.pop("banco", None)

    # vendedor
    if vd.get("vendedor_eu"):
        _definir_vendedor(db, usuario, dados, usuario.id, paragrafos)
    elif vd.get("vendedor_nome"):
        nome = vd["vendedor_nome"]
        achados = busca.buscar_usuarios(db, nome)
        if len(achados) == 1:
            _definir_vendedor(db, usuario, dados, achados[0].id, paragrafos)
        elif len(achados) > 1:
            achados = achados[: busca.MAXIMO_DE_OPCOES]
            paragrafos.append(
                f"Tem mais de uma pessoa chamada {nome} na equipe. Qual foi o vendedor?"
            )
            opcoes.extend(
                schemas.AssistenteOpcao(rotulo=u.nome, mensagem=str(n))
                for n, u in enumerate(achados, start=1)
            )
            escolha_pendente = ("vendedor", [u.id for u in achados])
        else:
            paragrafos.append(f"Não achei ninguém ativo na equipe chamado “{nome}”.")
            dados.pop("vendedor_id", None)

    # veículo
    ref = lido.referencia
    if ref.get("dois"):
        paragrafos.append(
            "Entendi mais de um veículo nessa mensagem ({} e {}). Eu registro uma venda de "
            "cada vez: diga qual foi vendido.".format(*ref["dois"])
        )
    elif ref:
        achados = busca.buscar_veiculos(db, ref, (Situacao.a_venda,))
        if candidatos and aguardando == "veiculo":
            entre_os_listados = [v for v in achados if v.id in candidatos]
            achados = entre_os_listados or achados
        vendaveis = [v for v in achados if _a_venda(v)]
        if len(vendaveis) == 1:
            veiculo, dados["veiculo_id"] = vendaveis[0], vendaveis[0].id
        elif len(vendaveis) > 1:
            vendaveis = vendaveis[: busca.MAXIMO_DE_OPCOES]
            lista, botoes = busca.lista_para_escolher(vendaveis)
            paragrafos.append(
                f"Achei {len(vendaveis)} veículos à venda que combinam:\n{lista}\n"
                "Qual deles foi vendido? Responda com o número ou a placa."
            )
            opcoes.extend(botoes)
            escolha_pendente = ("veiculo", [v.id for v in vendaveis])
        elif achados:  # placa de um veículo que não está à venda
            paragrafos.append(_por_que_nao_vende(achados[0]))
        else:
            descricao = busca.descrever_referencia(ref)
            parados = [
                v
                for v in busca.buscar_veiculos(
                    db,
                    ref,
                    (Situacao.compra, Situacao.documentacao, Situacao.preparacao),
                )
            ]
            if len(parados) == 1:
                paragrafos.append(_por_que_nao_vende(parados[0]))
            else:
                paragrafos.append(f"Não encontrei {descricao} à venda no estoque.")

    if vd.get("valor_anunciado"):
        if veiculo is not None and veiculo.preco_venda is not None:
            dados["valor"] = veiculo.preco_venda
        elif veiculo is not None:
            paragrafos.append("Esse veículo não tem preço anunciado: me diga o valor da venda.")

    if "vendedor_id" not in dados and not pode(usuario, P.vendas_ver_todas):
        dados["vendedor_id"] = usuario.id  # o vendedor registra as próprias vendas

    if lido.soltos:
        valores = _lista([_moeda(v) for v, _ in lido.soltos])
        paragrafos.append(
            f"Vi {valores}, mas não sei se é o valor da venda, a entrada ou a parcela. "
            "Escreva, por exemplo: “por 14.900”, “entrada de 3 mil” ou “10x de 1.200”."
        )
    perguntas.extend(lido.perguntas)

    if veiculo is not None and "valor" in dados:
        if veiculo.preco_venda is not None and dados["valor"] < veiculo.preco_venda:
            avisos.append(f"Valor abaixo do anunciado ({_moeda(veiculo.preco_venda)}).")
        if ve_custos and dados["valor"] < veiculo.custo_total:
            avisos.append("Venda abaixo do que a loja investiu no veículo: lucro negativo.")
    return seguir()


def _definir_vendedor(
    db: Session, usuario: Usuario, dados: dict, vendedor_id: int, paragrafos: list[str]
) -> None:
    if vendedor_id != usuario.id and not pode(usuario, P.vendas_ver_todas):
        paragrafos.append("Você só pode registrar vendas em seu nome: deixei você como vendedor.")
        vendedor_id = usuario.id
    vendedor = db.get(Usuario, vendedor_id)
    if vendedor is not None and vendedor.ativo:
        dados["vendedor_id"] = vendedor.id


_MENSAGENS_VALIDACAO = {
    "missing": "campo obrigatório",
    "string_too_short": "campo obrigatório",
    "greater_than": "deve ser maior que zero",
    "greater_than_equal": "valor abaixo do mínimo",
    "less_than_equal": "valor acima do máximo",
    "decimal_max_places": "use no máximo 2 casas decimais",
    "decimal_max_digits": "valor grande demais",
}
_NOMES_DOS_CAMPOS = {
    "valor": "Valor da venda",
    "forma": "Forma de pagamento",
    "nome": "Comprador",
    "numero_parcelas": "Nº de parcelas",
    "valor_parcela": "Valor da parcela",
    "entrada": "Entrada",
    "telefone": "WhatsApp",
    "cpf_cnpj": "CPF/CNPJ",
}


def _frase_validacao(erro: ValidationError) -> str:
    frases = []
    for detalhe in erro.errors():
        if detalhe["type"] == "value_error":
            frases.append(detalhe["msg"].removeprefix("Value error, "))
            continue
        campo = str(detalhe["loc"][-1]) if detalhe["loc"] else ""
        mensagem = _MENSAGENS_VALIDACAO.get(detalhe["type"], "valor inválido")
        frases.append(f"{_NOMES_DOS_CAMPOS.get(campo, campo)}: {mensagem}")
    return "; ".join(frases)
