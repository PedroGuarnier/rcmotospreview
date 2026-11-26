"""Alteração de veículo do estoque por mensagem: "a CG placa ABC1D23 agora custa 13.900",
"põe a Biz 125 branca à venda", "a XRE 300 tá com 15 mil km".

Acha o veículo (mais de um candidato vira pergunta), mostra o antes → depois, pede
confirmação e grava pelo mesmo caminho do formulário (`atualizar_veiculo`): mesmas regras
(à venda exige preço, etapa de vendido só pela venda) e o mesmo audit log.
"""

from typing import Any, get_args

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import assistente_busca as busca
from app import assistente_datas, schemas
from app.assistente import (
    _ROTULOS,
    _SITUACOES,
    _TIPO,
    Interpretacao,
    _conferir,
    _frase_validacao,
    _inteiro,
    _lista,
    _moeda,
    interpretar,
)
from app.models import SITUACOES_EM_ESTOQUE, Situacao, Usuario, Veiculo
from app.permissoes import P, pode
from app.rotas.veiculos import atualizar_veiculo, conferir_atualizacao
from app.servicos import aliquota_imposto, calcular_imposto
from app.tempo import hoje

# Ordem em que as mudanças aparecem na ficha
_ORDEM = (
    "tipo",
    "marca",
    "modelo",
    "ano_fabricacao",
    "ano_modelo",
    "cor",
    "km",
    "placa",
    "chassi",
    "renavam",
    "valor_compra",
    "data_compra",
    "preco_venda",
    "situacao",
    "observacoes",
)
_OBRIGATORIOS = {"tipo", "marca", "modelo", "valor_compra"}
_TODAS_AS_ETAPAS = {
    **_SITUACOES,
    Situacao.vendido: "Vendido",
    Situacao.pos_venda: "Pós-venda",
    Situacao.concluido: "Concluído",
}


def _formatar(campo: str, valor: Any) -> str:
    if valor is None:
        return "—"
    if campo == "tipo":
        return _TIPO[valor]
    if campo == "km":
        return f"{_inteiro(valor)} km"
    if campo == "placa":
        return busca.placa_formatada(valor)
    if campo in ("valor_compra", "preco_venda"):
        return _moeda(valor)
    if campo == "situacao":
        return _TODAS_AS_ETAPAS[valor]
    if campo == "data_compra":
        return assistente_datas.formatar(valor)
    return str(valor)


def _rotulo(campo: str) -> str:
    return _ROTULOS.get(campo, "Data da compra" if campo == "data_compra" else campo)


def conversar_edicao(
    db: Session,
    usuario: Usuario,
    mensagem: str,
    estado: schemas.AssistenteEstado | None,
    lido: Interpretacao | None = None,
) -> schemas.AssistenteResposta:
    """Uma rodada da alteração por mensagem. `lido` vem pronto quando a alteração começa."""
    continuando = estado is not None and estado.modo == "edicao" and estado.edicao is not None
    edicao = estado.edicao if continuando and estado else None
    mudancas: dict[str, Any] = edicao.mudancas.model_dump(exclude_none=True) if edicao else {}
    remover: list[str] = list(edicao.remover) if edicao else []
    veiculo_id = edicao.veiculo_id if edicao else None
    aguardando = estado.aguardando if continuando and estado else None
    candidatos = list(estado.candidatos) if continuando and estado else []
    paragrafos: list[str] = []
    avisos: list[str] = []
    opcoes: list[schemas.AssistenteOpcao] = []
    acao = "nenhuma"
    terminou = False
    atualizado: schemas.AssistenteVeiculo | None = None
    ve_custos = pode(usuario, P.custos_ver)
    escolha_pendente: list[int] | None = None
    problema: str | None = None  # regra que impede gravar (ex.: à venda sem preço)
    veiculo: Veiculo | None = busca.obter(db, veiculo_id) if veiculo_id else None

    def campos_finais() -> dict[str, Any]:
        """Só o que muda de verdade em relação ao que está gravado."""
        if veiculo is None:
            return {}
        finais = {c: v for c, v in mudancas.items() if getattr(veiculo, c) != v}
        for campo in remover:
            if getattr(veiculo, campo) is not None:
                finais[campo] = None
        return finais

    def responder(proximo: str | None) -> schemas.AssistenteResposta:
        return schemas.AssistenteResposta(
            resposta="\n".join(p for p in paragrafos if p),
            estado=schemas.AssistenteEstado(
                modo=None if terminou else "edicao",
                edicao=None
                if terminou
                else schemas.AssistenteEdicaoRascunho(
                    veiculo_id=veiculo.id if veiculo is not None else None,
                    mudancas=schemas.AssistenteRascunho(**mudancas),
                    remover=remover,
                ),
                aguardando=None if terminou else proximo,
                candidatos=[] if terminou else (escolha_pendente or []),
            ),
            ficha=[] if terminou else _ficha(),
            faltando=[],
            sugeridos=[],
            pronto=acao == "confirmar",
            acao=acao,
            veiculo=atualizado,
            avisos=avisos,
            opcoes=opcoes,
        )

    def _ficha() -> list[schemas.AssistenteItemFicha]:
        if veiculo is None:
            return []
        itens = [
            schemas.AssistenteItemFicha(campo="veiculo", rotulo="Veículo", valor=veiculo.descricao)
        ]
        finais = campos_finais()
        for campo in _ORDEM:
            if campo in finais:
                itens.append(
                    schemas.AssistenteItemFicha(
                        campo=campo,
                        rotulo=_rotulo(campo),
                        valor=_formatar(campo, finais[campo]),
                        antes=_formatar(campo, getattr(veiculo, campo)),
                    )
                )
        if ve_custos and ({"preco_venda", "valor_compra"} & set(finais)):
            preco = finais.get("preco_venda", veiculo.preco_venda)
            compra = finais.get("valor_compra", veiculo.valor_compra)
            if preco is not None:
                lucro = preco - compra - veiculo.total_custos
                antes = (
                    _moeda(veiculo.preco_venda - veiculo.custo_total)
                    if veiculo.preco_venda is not None
                    else "—"
                )
                itens.append(
                    schemas.AssistenteItemFicha(
                        campo="lucro_previsto",
                        rotulo="Lucro previsto",
                        valor=_moeda(lucro),
                        calculado=True,
                        antes=antes,
                    )
                )
                aliquota = aliquota_imposto(db)
                if aliquota > 0:
                    itens.append(
                        schemas.AssistenteItemFicha(
                            campo="imposto_previsto",
                            rotulo="Imposto estimado",
                            valor=_moeda(calcular_imposto(preco, compra, aliquota)),
                            calculado=True,
                        )
                    )
        return itens

    def seguir() -> schemas.AssistenteResposta:
        nonlocal acao, problema
        if escolha_pendente:
            return responder("veiculo")
        if veiculo is None:
            paragrafos.append(
                "Qual veículo você quer alterar? Mande a placa (ou o final dela) ou o modelo, "
                "por exemplo: “Biz 125 branca”."
            )
            return responder("veiculo")
        finais = campos_finais()
        if not finais:
            if mudancas or remover:
                paragrafos.append(f"Isso já está assim no cadastro de {veiculo.descricao}.")
            paragrafos.append(
                f"O que você quer mudar em {veiculo.descricao}? Por exemplo: “preço 9.900”, "
                "“15 mil km”, “cor azul” ou “põe à venda”."
            )
            return responder("mudanca")
        try:
            dados = schemas.VeiculoAtualizar(**finais)
            conferir_atualizacao(db, veiculo, dados.model_dump(exclude_unset=True))
        except ValidationError as erro:
            paragrafos.append(f"Um dado não passou na conferência: {_frase_validacao(erro)}")
            return responder(None)
        except HTTPException as erro:
            problema = str(erro.detail)
            precisa_preco = "preço de venda" in problema and "preco_venda" not in finais
            if precisa_preco and veiculo.preco_venda is None:
                paragrafos.append(
                    f"Para pôr {veiculo.descricao} à venda preciso do preço. Por quanto vai "
                    "anunciar? Exemplo: 14.900."
                )
                return responder("preco_venda")
            paragrafos.append(f"Assim não dá para salvar: {problema}")
            return responder(None)
        acao = "confirmar"
        paragrafos.append(f"Vou alterar {veiculo.descricao}: {_resumo(finais, veiculo)}.")
        paragrafos.append("Confira a alteração. Posso salvar?")
        return responder("confirmacao")

    if not pode(usuario, P.estoque_editar):
        terminou = True
        paragrafos.append(
            "Seu perfil não altera veículos do estoque. Peça a quem cuida do estoque."
        )
        return responder(None)

    # 1. Escolha numa lista mostrada ("2", "a segunda")
    escolha = None
    if aguardando == "veiculo" and candidatos:
        escolha = busca.escolha_na_lista(mensagem, len(candidatos))
    if escolha is not None:
        veiculo = busca.obter(db, candidatos[escolha - 1])
        return _depois_de_achar(veiculo, mudancas, remover, paragrafos, avisos, ve_custos, seguir)

    if lido is None:
        lido = interpretar(mensagem, aguardando, contexto="edicao")
    if lido.intencao == "venda":  # "vendi a biz...": a alteração fica de lado
        from app.assistente_venda import conversar_venda  # import aqui: evita ciclo

        resposta = conversar_venda(db, usuario, mensagem, None, lido)
        if not pode(usuario, P.vendas_registrar):
            return resposta
        resposta.resposta = "Deixei a alteração de lado, sem salvar.\n" + resposta.resposta
        return resposta

    # 2. Cancelar, confirmar, negar
    if lido.intencao == "cancelar":
        terminou, acao = True, "cancelado"
        paragrafos.append("Pronto, não mudei nada.")
        return responder(None)
    if lido.intencao == "afirmacao":
        if aguardando == "confirmacao" and veiculo is not None and campos_finais():
            travado = busca.obter_travado(db, veiculo.id)
            if travado is None:
                paragrafos.append("Esse veículo não existe mais no estoque.")
                terminou = True
                return responder(None)
            veiculo = travado
            descricao_antes = veiculo.descricao
            mudou = campos_finais()
            try:
                salvo = atualizar_veiculo(db, veiculo, schemas.VeiculoAtualizar(**mudou), usuario)
            except ValidationError as erro:
                paragrafos.append(f"Não consegui salvar: {_frase_validacao(erro)}")
                return seguir()
            except HTTPException as erro:
                db.rollback()
                veiculo = busca.obter(db, veiculo.id)
                paragrafos.append(f"Não consegui salvar: {erro.detail}")
                return seguir()
            terminou, acao = True, "atualizado"
            atualizado = schemas.AssistenteVeiculo(
                id=salvo.id, descricao=salvo.descricao, placa=salvo.placa
            )
            paragrafos.append(
                f"Pronto! {descricao_antes} foi atualizado: {_resumo(mudou)}.\n"
                "Se quiser, adicione fotos aqui mesmo."
            )
            veiculo = salvo
            return responder(None)
        return seguir()
    if lido.intencao in ("negacao", "dispensa"):
        if aguardando == "confirmacao":
            paragrafos.append(
                "Sem problema, não mudei nada. O que precisa corrigir? Por exemplo: "
                "“o preço é 13.500” ou “cancela”."
            )
            return responder(None)
        paragrafos.append("Tudo bem, não mudei nada.")
        return seguir()
    if lido.intencao not in ("edicao", "cadastro"):
        paragrafos.append(
            "Não entendi essa mensagem. Sobre a alteração em andamento: diga o que mudar, "
            "responda “sim” para salvar ou “cancela” para desistir."
        )
        return seguir()

    # 3. O que muda
    paragrafos.extend(lido.erros)
    ano_maximo = hoje().year + 1
    for campo, valor in lido.campos.items():
        if campo == "valor_compra" and not ve_custos:
            paragrafos.append("Seu perfil não altera o valor de compra.")
            continue
        if campo == "data_compra" and valor > hoje():
            paragrafos.append("A data da compra não pode ser futura.")
            continue
        erro = _conferir(campo, valor, ano_maximo)
        if erro:
            paragrafos.append(erro)
            continue
        mudancas[campo] = valor
        if campo in remover:
            remover.remove(campo)
    for campo in lido.remover:
        if campo in _OBRIGATORIOS:
            paragrafos.append(f"{_rotulo(campo)} é obrigatório: mande o valor certo.")
            continue
        if campo not in get_args(schemas.CampoRemovivel):
            continue
        mudancas.pop(campo, None)
        if campo not in remover:
            remover.append(campo)
    if lido.soltos:
        valores = _lista([_moeda(v) for v, _ in lido.soltos])
        paragrafos.append(
            f"Vi {valores}, mas não sei se é o preço de venda ou o valor de compra. "
            "Escreva, por exemplo: “preço 13.900”."
        )
    for _campo, pergunta, _sugestao in lido.perguntas:
        paragrafos.append(pergunta)
    avisos.extend(lido.avisos)

    ref = lido.referencia
    if ref.get("dois"):
        paragrafos.append(
            "Entendi mais de um veículo nessa mensagem ({} e {}). Eu altero um de cada vez: "
            "diga qual.".format(*ref["dois"])
        )
    elif ref:
        achados = busca.buscar_veiculos(db, ref, SITUACOES_EM_ESTOQUE)
        if candidatos and aguardando == "veiculo":
            achados = [v for v in achados if v.id in candidatos] or achados
        if len(achados) == 1:
            veiculo = achados[0]
        elif len(achados) > 1:
            achados = achados[: busca.MAXIMO_DE_OPCOES]
            lista, botoes = busca.lista_para_escolher(achados)
            paragrafos.append(
                f"Achei {len(achados)} veículos no estoque que combinam:\n{lista}\n"
                "Qual deles? Responda com o número ou a placa."
            )
            opcoes.extend(botoes)
            escolha_pendente = [v.id for v in achados]
            veiculo = None
        else:
            paragrafos.append(
                f"Não encontrei {busca.descrever_referencia(ref)} no estoque. Se for um "
                "veículo novo, mande os dados com o valor de compra para eu cadastrar."
            )
    return _depois_de_achar(veiculo, mudancas, remover, paragrafos, avisos, ve_custos, seguir)


def _resumo(mudancas: dict[str, Any], veiculo: Veiculo | None = None) -> str:
    """ "preço de venda de R$ 14.900,00 para R$ 13.900,00 e situação à venda" """
    partes = []
    for campo in _ORDEM:
        if campo not in mudancas:
            continue
        nome = _rotulo(campo).lower()
        novo = _formatar(campo, mudancas[campo])
        if campo == "situacao":
            novo = novo.lower()
        if mudancas[campo] is None:
            partes.append(f"sem {nome}")
        elif veiculo is not None and getattr(veiculo, campo) is not None:
            antes = _formatar(campo, getattr(veiculo, campo))
            antes = antes.lower() if campo == "situacao" else antes
            partes.append(f"{nome} de {antes} para {novo}")
        else:
            partes.append(f"{nome} {novo}")
    return _lista(partes)


def _depois_de_achar(veiculo, mudancas, remover, paragrafos, avisos, ve_custos, seguir):
    """Regras que dependem do veículo: vendido não muda de preço, compra só com custos."""
    if veiculo is not None and veiculo.venda_ativa is not None:
        if "preco_venda" in mudancas or "preco_venda" in remover:
            mudancas.pop("preco_venda", None)
            if "preco_venda" in remover:
                remover.remove("preco_venda")
            paragrafos.append(
                f"{veiculo.descricao} já foi vendido: o preço de venda não muda mais (o valor "
                "da venda fica na tela de Vendas)."
            )
    if veiculo is not None and not ve_custos:
        mudancas.pop("valor_compra", None)
    if "preco_venda" in mudancas and "valor_compra" not in mudancas and veiculo is not None:
        if mudancas["preco_venda"] < veiculo.valor_compra and ve_custos:
            avisos.append("O preço de venda fica abaixo do valor de compra.")
    return seguir()
