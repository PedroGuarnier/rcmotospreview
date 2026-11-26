from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.db import obter_db
from app.ia import atendimento
from app.ia.provedores import Provedor, provedor_ia
from app.models import Usuario
from app.permissoes import usuario_atual

router = APIRouter(prefix="/assistente", tags=["assistente"])


@router.post("/mensagem", response_model=schemas.AssistenteResposta)
def mensagem(
    dados: schemas.AssistenteMensagem,
    # Cadastro e alteração exigem estoque.editar; venda, vendas.registrar; perguntas,
    # qualquer perfil com a IA ligada. Quem decide é `atendimento.atender`.
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(obter_db),
    provedor: Provedor | None = Depends(provedor_ia),
):
    """Uma rodada da conversa. O `estado` devolvido volta na mensagem seguinte."""
    return atendimento.atender(db, usuario, dados.mensagem, dados.estado, provedor)
