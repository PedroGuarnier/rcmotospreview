"""Rotas sem login, usadas pelo site: catálogo e laudo dos veículos À VENDA.

Só sai daqui o que pode ser público: nada de valor de compra, custos, chassi, RENAVAM,
dados de comprador ou o texto detalhado do provedor de procedência.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import fotos, schemas
from app.config import obter_config
from app.db import obter_db
from app.limites import Janela, ip_do_cliente
from app.models import LaudoProcedencia, Situacao, TipoVeiculo, Veiculo
from app.rotas.procedencia import historico_do_veiculo
from app.validacao import normalizar_placa

router = APIRouter(prefix="/publico", tags=["site público"])

_CARGA = (selectinload(Veiculo.fotos), selectinload(Veiculo.custos), selectinload(Veiculo.laudos))

# Frase pública por situação: o detalhe do provedor pode citar terceiros e fica só na loja.
_FRASE = {
    "ok": "Nada consta.",
    "atencao": "Ponto de atenção — a loja explica o que é.",
    "alerta": "Restrição encontrada — fale com a loja.",
}

# Consulta de placa por IP: 10 por minuto e 60 por hora. Um visitante de verdade confere
# poucas placas; adivinhar a placa completa de um anúncio (3.600 combinações) fica inviável.
POR_MINUTO = Janela(10, 60)
POR_HORA = Janela(60, 3600)


def _limitar(request: Request) -> None:
    ip = ip_do_cliente(request)
    if POR_MINUTO.estourou(ip) or POR_HORA.estourou(ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Muitas consultas. Tente de novo mais tarde."
        )
    POR_MINUTO.registrar(ip)
    POR_HORA.registrar(ip)


def mascarar(placa: str | None) -> str | None:
    return f"{placa[:3]}•••{placa[-1]}" if placa else None


def _laudo_valido(veiculo: Veiculo) -> LaudoProcedencia | None:
    """Laudo mais recente. Laudo ilustrativo só aparece em ambiente de demonstração."""
    demo = obter_config().dados_demo
    return next(
        (
            laudo
            for laudo in veiculo.laudos
            if laudo.placa == veiculo.placa and (demo or not laudo.ilustrativo)
        ),
        None,
    )


def _publico(veiculo: Veiculo) -> schemas.VeiculoPublico:
    laudo = _laudo_valido(veiculo)
    return schemas.VeiculoPublico(
        id=veiculo.id,
        tipo=veiculo.tipo,
        marca=veiculo.marca,
        modelo=veiculo.modelo,
        ano_fabricacao=veiculo.ano_fabricacao,
        ano_modelo=veiculo.ano_modelo,
        cor=veiculo.cor,
        km=veiculo.km,
        preco=veiculo.preco_venda,
        placa_mascarada=mascarar(veiculo.placa),
        fotos=[
            schemas.FotoOut(id=f.id, url=fotos.url(f.arquivo), miniatura_url=fotos.url(f.miniatura))
            for f in veiculo.fotos
        ],
        dias_na_loja=max((datetime.now(UTC) - veiculo.situacao_desde).days, 0),
        semaforo=laudo.semaforo if laudo else None,
    )


def _procedencia(veiculo: Veiculo, placa: str) -> schemas.ProcedenciaPublica:
    laudo = _laudo_valido(veiculo)
    return schemas.ProcedenciaPublica(
        placa=placa,
        veiculo=_publico(veiculo),
        semaforo=laudo.semaforo if laudo else None,
        consultado_em=laudo.criado_em if laudo else None,
        ilustrativo=bool(laudo and laudo.ilustrativo),
        itens=[
            schemas.ItemLaudo(
                chave=item["chave"],
                titulo=item["titulo"],
                situacao=item["situacao"],
                detalhe=_FRASE.get(item["situacao"], ""),
            )
            for item in (laudo.dados.get("itens", []) if laudo else [])
        ],
        historico=historico_do_veiculo(veiculo, laudo, publico=True),
    )


def _a_venda():
    return (
        select(Veiculo)
        .where(Veiculo.situacao == Situacao.a_venda, Veiculo.preco_venda.is_not(None))
        .options(*_CARGA)
    )


@router.get("/veiculos", response_model=schemas.CatalogoPublico)
def catalogo(tipo: TipoVeiculo | None = None, db: Session = Depends(obter_db)):
    """Catálogo do site: sempre igual ao estoque — o que está "à venda" no sistema."""
    consulta = _a_venda().order_by(Veiculo.situacao_desde.desc(), Veiculo.id.desc())
    if tipo:
        consulta = consulta.where(Veiculo.tipo == tipo)
    return schemas.CatalogoPublico(
        veiculos=[_publico(v) for v in db.scalars(consulta)],
        ilustrativo=obter_config().dados_demo,
    )


@router.get("/veiculos/{veiculo_id}/procedencia", response_model=schemas.ProcedenciaPublica)
def procedencia_do_anuncio(veiculo_id: int, db: Session = Depends(obter_db)):
    """Laudo aberto a partir do anúncio: a placa segue mascarada."""
    veiculo = db.scalar(_a_venda().where(Veiculo.id == veiculo_id))
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Este veículo não está mais à venda.")
    return _procedencia(veiculo, mascarar(veiculo.placa) or "")


@router.get("/procedencia/{placa}", response_model=schemas.ProcedenciaPublica)
def procedencia_pela_placa(placa: str, request: Request, db: Session = Depends(obter_db)):
    """Quem digita a placa inteira vê o laudo — só de veículo que está à venda na loja."""
    _limitar(request)
    try:
        placa = normalizar_placa(placa)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    veiculo = db.scalar(_a_venda().where(Veiculo.placa == placa))
    if veiculo is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Esta placa não está entre os veículos à venda na loja."
        )
    return _procedencia(veiculo, placa)
