from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import assistente, schemas
from app.db import obter_db
from app.models import Usuario
from app.permissoes import P, exigir

router = APIRouter(prefix="/assistente", tags=["assistente"])


@router.post("/mensagem", response_model=schemas.AssistenteResposta)
def mensagem(
    dados: schemas.AssistenteMensagem,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),  # a mesma do formulário de cadastro
    db: Session = Depends(obter_db),
):
    """Uma rodada da conversa de cadastro. O `estado` devolvido volta na mensagem seguinte."""
    return assistente.conversar(db, usuario, dados.mensagem, dados.estado)
