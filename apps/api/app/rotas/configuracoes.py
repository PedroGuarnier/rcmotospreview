from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.db import obter_db
from app.models import Configuracao, Usuario
from app.permissoes import P, exigir
from app.servicos import CENTAVO, aliquota_imposto

router = APIRouter(prefix="/configuracoes", tags=["configurações"])


@router.get("", response_model=schemas.ConfiguracaoOut)
def ver(_: Usuario = Depends(exigir(P.custos_ver)), db: Session = Depends(obter_db)):
    return schemas.ConfiguracaoOut(imposto_margem_aliquota=aliquota_imposto(db))


@router.put("", response_model=schemas.ConfiguracaoOut)
def editar(
    dados: schemas.ConfiguracaoEditar,
    _: Usuario = Depends(exigir(P.configuracoes_editar)),
    db: Session = Depends(obter_db),
):
    """Vale para as vendas registradas daqui em diante; as já registradas ficam como estão."""
    configuracao = db.get(Configuracao, 1)
    if configuracao is None:
        configuracao = Configuracao(id=1)
        db.add(configuracao)
    configuracao.imposto_margem_aliquota = dados.imposto_margem_aliquota.quantize(CENTAVO)
    db.commit()
    return schemas.ConfiguracaoOut(imposto_margem_aliquota=aliquota_imposto(db))
