"""Quem responde cada mensagem do assistente: o motor de regras decide primeiro.

- Quem pode cadastrar/alterar veículo (`estoque.editar`) ou registrar venda
  (`vendas.registrar`) conversa com o motor de regras; cada ação confere a sua permissão. Só vai
  para a IA o que ele classifica como pergunta / fora do escopo (ou mensagem que ele não
  entendeu, sem cadastro em andamento). Com um rascunho aguardando resposta, a pergunta é
  respondida e o rascunho continua no estado, com a pendência repetida.
- Quem não tem nenhuma das duas (financeiro) usa o assistente só para perguntas, e só com
  a IA ligada.

O histórico curto (últimas trocas de pergunta e resposta da IA, só texto) vai e volta no
`estado`, como o rascunho: o servidor não guarda a conversa.
"""

import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import assistente, schemas
from app.ia import agente
from app.ia.provedores import Provedor
from app.models import Usuario
from app.permissoes import P, pode

_COMECO_DE_PERGUNTA = re.compile(
    r"^(?:quant[oa]s?|qual|quais|quem|quando|onde|como|cade|me (?:mostra|diz|fala)|mostra|"
    r"lista|tem)\b"
)


def _e_pergunta(mensagem: str) -> bool:
    sem_acento = unicodedata.normalize("NFD", mensagem.lower()).encode("ascii", "ignore").decode()
    return "?" in mensagem or bool(_COMECO_DE_PERGUNTA.match(sem_acento.strip()))


def _historico_com(
    historico: list[schemas.AssistenteTroca], pergunta: str, resposta: agente.RespostaIA
) -> list[schemas.AssistenteTroca]:
    if not resposta.respondeu:  # falha ou limite: não vale como contexto
        return historico
    troca = schemas.AssistenteTroca(
        pergunta=pergunta, resposta=resposta.para_historico[: schemas.MAX_RESPOSTA_IA]
    )
    return [*historico, troca][-schemas.MAX_TROCAS_IA :]


def atender(
    db: Session,
    usuario: Usuario,
    mensagem: str,
    estado: schemas.AssistenteEstado | None,
    provedor: Provedor | None,
) -> schemas.AssistenteResposta:
    historico = list(estado.historico) if estado else []

    if not (pode(usuario, P.estoque_editar) or pode(usuario, P.vendas_registrar)):
        if provedor is None:  # sem ação por mensagem e sem IA, não há o que oferecer
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Seu perfil não tem acesso a esta função."
            )
        ia = agente.perguntar(db, usuario, mensagem, historico, provedor)
        return schemas.AssistenteResposta(
            resposta=ia.texto,
            estado=schemas.AssistenteEstado(historico=_historico_com(historico, mensagem, ia)),
            ficha=[],
            faltando=[],
            sugeridos=[],
            pronto=False,
            acao="nenhuma",
            avisos=[],
            origem="ia",
        )

    respondidas: list[agente.RespostaIA] = []

    def perguntas(lido: assistente.Interpretacao) -> str | None:
        """Chamada pelo motor de regras para o que não é cadastro. None: o motor responde."""
        if lido.intencao == "nada":  # só sem rascunho; com a IA desligada, o "não entendi"
            if provedor is None:
                return None
        elif lido.venda and not _e_pergunta(mensagem):
            return None  # "vendi a CG pro João": registrar venda é do motor de regras
        if provedor is None:
            return agente.DESLIGADA
        ia = agente.perguntar(db, usuario, mensagem, historico, provedor)
        respondidas.append(ia)
        return ia.texto

    resposta = assistente.conversar(db, usuario, mensagem, estado, perguntas=perguntas)
    if respondidas:
        resposta.estado.historico = _historico_com(historico, mensagem, respondidas[0])
        resposta.origem = "ia"
    else:
        resposta.estado.historico = historico
    return resposta
