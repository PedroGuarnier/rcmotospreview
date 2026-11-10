from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import procedencia, schemas
from app.db import obter_db
from app.models import LaudoProcedencia, TipoCusto, Usuario, Veiculo
from app.permissoes import P, exigir

router = APIRouter(tags=["procedência"])

_CARGA = (
    selectinload(LaudoProcedencia.consultado_por),
    selectinload(LaudoProcedencia.veiculo).selectinload(Veiculo.custos),
)


def _data(valor) -> str:
    return valor.strftime("%d/%m/%Y")


def historico_do_veiculo(veiculo: Veiculo | None, laudo: LaudoProcedencia | None, *, publico: bool):
    """Linha do tempo montada só com o que está registrado: laudo + sistema da loja."""
    marcos: list[tuple[str, schemas.MarcoHistorico]] = []

    def marco(ordem: str, quando: str, titulo: str, detalhe: str | None = None) -> None:
        marcos.append(
            (ordem, schemas.MarcoHistorico(quando=quando, titulo=titulo, detalhe=detalhe))
        )

    dados = (laudo.dados.get("veiculo") if laudo else None) or {}
    ano = (veiculo.ano_fabricacao if veiculo else None) or dados.get("ano_fabricacao")
    if ano:
        modelo = (veiculo.ano_modelo if veiculo else None) or dados.get("ano_modelo")
        marco(f"{ano}-00-00", str(ano), "Fabricação", f"Modelo {modelo}" if modelo else None)
    if veiculo is not None:
        if veiculo.data_compra:
            marco(veiculo.data_compra.isoformat(), _data(veiculo.data_compra), "Chegou à RC Motos")
        manutencoes = [c for c in veiculo.custos if c.tipo == TipoCusto.manutencao]
        if manutencoes:
            ultima = max(c.data for c in manutencoes)
            detalhe = None if publico else "; ".join(c.descricao for c in manutencoes)
            marco(ultima.isoformat(), _data(ultima), "Revisão feita na loja", detalhe)
        papeis = [c for c in veiculo.custos if c.tipo in (TipoCusto.documentacao, TipoCusto.debito)]
        if papeis:
            ultima = max(c.data for c in papeis)
            marco(ultima.isoformat(), _data(ultima), "Documentação e débitos em dia")
    if laudo is not None:
        resultado = {
            "verde": "Nada consta",
            "amarelo": "Ponto de atenção",
            "vermelho": "Restrição encontrada",
        }[laudo.semaforo.value]
        marco(
            laudo.criado_em.date().isoformat() + "T",
            _data(laudo.criado_em),
            "Consulta de procedência",
            resultado,
        )
    return [m for _, m in sorted(marcos, key=lambda par: par[0])]


def serializar(laudo: LaudoProcedencia) -> schemas.LaudoOut:
    return schemas.LaudoOut(
        id=laudo.id,
        placa=laudo.placa,
        semaforo=laudo.semaforo,
        ilustrativo=laudo.ilustrativo,
        provedor=laudo.provedor,
        criado_em=laudo.criado_em,
        consultado_por=laudo.consultado_por.nome if laudo.consultado_por else None,
        veiculo_id=laudo.veiculo_id,
        veiculo_descricao=laudo.veiculo.descricao if laudo.veiculo else None,
        dados_veiculo=laudo.dados.get("veiculo") or {},
        itens=[schemas.ItemLaudo(**item) for item in laudo.dados.get("itens", [])],
        historico=historico_do_veiculo(laudo.veiculo, laudo, publico=False),
    )


def _carregar(db: Session, laudo_id: int) -> LaudoProcedencia:
    return db.scalar(
        select(LaudoProcedencia).where(LaudoProcedencia.id == laudo_id).options(*_CARGA)
    )


@router.get("/procedencia/situacao", response_model=schemas.SituacaoProcedencia)
def situacao(_: Usuario = Depends(exigir(P.procedencia_consultar))):
    provedor = procedencia.provedor_ativo()
    return schemas.SituacaoProcedencia(
        disponivel=provedor is not None, ilustrativo=provedor == "demonstracao"
    )


@router.post(
    "/procedencia/consultar", response_model=schemas.LaudoOut, status_code=status.HTTP_201_CREATED
)
def consultar(
    dados: schemas.ConsultaPlaca,
    usuario: Usuario = Depends(exigir(P.procedencia_consultar)),
    db: Session = Depends(obter_db),
):
    try:
        laudo = procedencia.consultar(db, dados.placa, usuario)
    except procedencia.ProcedenciaIndisponivel as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "A consulta de procedência ainda não está conectada a um provedor.",
        ) from exc
    db.commit()
    return serializar(_carregar(db, laudo.id))


@router.get("/procedencia", response_model=list[schemas.LaudoOut])
def listar(
    limite: int = Query(20, ge=1, le=100),
    _: Usuario = Depends(exigir(P.procedencia_consultar)),
    db: Session = Depends(obter_db),
):
    """Últimas consultas feitas."""
    laudos = db.scalars(
        select(LaudoProcedencia).options(*_CARGA).order_by(LaudoProcedencia.id.desc()).limit(limite)
    )
    return [serializar(laudo) for laudo in laudos]


@router.get("/veiculos/{veiculo_id}/laudos", response_model=list[schemas.LaudoOut])
def laudos_do_veiculo(
    veiculo_id: int,
    _: Usuario = Depends(exigir(P.estoque_ver)),
    db: Session = Depends(obter_db),
):
    laudos = db.scalars(
        select(LaudoProcedencia)
        .where(LaudoProcedencia.veiculo_id == veiculo_id)
        .options(*_CARGA)
        .order_by(LaudoProcedencia.id.desc())
    )
    return [serializar(laudo) for laudo in laudos]
