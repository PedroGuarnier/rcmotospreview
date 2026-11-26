"""Rotas sem login, usadas pelo site: catálogo e laudo dos veículos À VENDA, e a contagem de
visitas e cliques no WhatsApp.

Só sai daqui o que pode ser público: nada de valor de compra, custos, chassi, RENAVAM,
dados de comprador ou o texto detalhado do provedor de procedência. E nada entra de quem
visita: a contagem guarda só números por veículo e por dia, sem IP nem navegador.
"""

import re
import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app import fotos, schemas
from app.config import obter_config
from app.db import obter_db
from app.models import ContagemSite, LaudoProcedencia, Situacao, TipoVeiculo, Veiculo
from app.procedencia import laudo_valido
from app.rotas.procedencia import historico_do_veiculo
from app.tempo import hoje
from app.validacao import normalizar_placa

router = APIRouter(prefix="/publico", tags=["site público"])

_CARGA = (selectinload(Veiculo.fotos), selectinload(Veiculo.custos), selectinload(Veiculo.laudos))

# Frase pública por situação: o detalhe do provedor pode citar terceiros e fica só na loja.
_FRASE = {
    "ok": "Nada consta.",
    "atencao": "Ponto de atenção — a loja explica o que é.",
    "alerta": "Restrição encontrada — fale com a loja.",
}

# Limite simples por IP e por uso, em memória, numa janela de um minuto: consulta de placa
# (30 por minuto) e contagem de visitas/cliques (120 por minuto). O IP não é gravado.
_JANELA, _LIMITE = 60.0, 30
_LIMITE_EVENTOS = 120
_acessos: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _limitar(
    request: Request,
    uso: str = "placa",
    limite: int = _LIMITE,
    mensagem: str = "Muitas consultas. Tente de novo em um minuto.",
) -> None:
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "?"
    )
    agora = time.monotonic()
    fila = _acessos[(uso, ip)]
    while fila and agora - fila[0] > _JANELA:
        fila.popleft()
    if len(fila) >= limite:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, mensagem)
    fila.append(agora)
    if len(_acessos) > 10_000:  # não deixa o dicionário crescer sem fim
        _acessos.clear()


def mascarar(placa: str | None) -> str | None:
    return f"{placa[:3]}•••{placa[-1]}" if placa else None


# A mesma regra vale para o aviso da área da equipe ao pôr um veículo à venda sem laudo.
_laudo_valido = laudo_valido


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
        atualizado_em=_atualizado_em(veiculo, laudo),
    )


def _atualizado_em(veiculo: Veiculo, laudo: LaudoProcedencia | None) -> datetime:
    """Última mudança no anúncio (cadastro, etapa, fotos ou laudo): o `lastModified` do sitemap
    e a versão da imagem de compartilhamento."""
    datas = [veiculo.atualizado_em, veiculo.situacao_desde, *(f.criado_em for f in veiculo.fotos)]
    if laudo is not None:
        datas.append(laudo.criado_em)
    return max(d for d in datas if d is not None)


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


@router.get("/veiculos/{veiculo_id}", response_model=schemas.VeiculoPublico)
def anuncio(veiculo_id: int, db: Session = Depends(obter_db)):
    """Página do produto no site: só existe enquanto o veículo está à venda."""
    veiculo = db.scalar(_a_venda().where(Veiculo.id == veiculo_id))
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Este veículo não está mais à venda.")
    return _publico(veiculo)


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


# ---------- Contagem de visitas e cliques no WhatsApp ----------

_COLUNA = {
    schemas.TipoEventoSite.visualizacao: "visualizacoes",
    schemas.TipoEventoSite.whatsapp_cartao: "cliques_cartao",
    schemas.TipoEventoSite.whatsapp_pagina: "cliques_pagina",
    schemas.TipoEventoSite.whatsapp_proposta: "cliques_proposta",
}

# Robôs óbvios (buscadores, prévias de link, ferramentas de linha de comando, navegador sem
# tela): não contam. Quem não diz o navegador também não.
_ROBO = re.compile(
    r"bot|crawl|spider|slurp|preview|externalhit|facebookcatalog|headless|lighthouse|"
    r"pagespeed|curl|wget|python|httpx|aiohttp|go-http|java/|okhttp|axios|node-fetch|undici|"
    r"scrapy|phantom|selenium|puppeteer|playwright",
    re.IGNORECASE,
)


def eh_robo(user_agent: str | None) -> bool:
    return not user_agent or not user_agent.strip() or bool(_ROBO.search(user_agent))


@router.post("/eventos", status_code=status.HTTP_204_NO_CONTENT)
def registrar_evento(evento: schemas.EventoSite, request: Request, db: Session = Depends(obter_db)):
    """Soma 1 na contagem do dia do veículo: visita à página ou clique no WhatsApp.

    O site chama com `navigator.sendBeacon`, sem esperar a resposta. Nada de quem visitou é
    gravado (nem IP, nem navegador): só o número do veículo, o dia e o contador.
    """
    _limitar(request, "eventos", _LIMITE_EVENTOS, "Muitas contagens. Tente de novo em um minuto.")
    if eh_robo(request.headers.get("user-agent")):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    a_venda = db.scalar(
        select(Veiculo.id).where(
            Veiculo.id == evento.veiculo_id,
            Veiculo.situacao == Situacao.a_venda,
            Veiculo.preco_venda.is_not(None),
        )
    )
    if a_venda is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Este veículo não está mais à venda.")
    coluna = _COLUNA[evento.tipo]
    # Soma atômica (INSERT ... ON CONFLICT): duas visitas ao mesmo tempo não se perdem.
    # É contagem, não dado de negócio: por isso não passa pelo ORM nem pelo audit log.
    tabela = ContagemSite.__table__
    db.execute(
        pg_insert(tabela)
        .values(veiculo_id=evento.veiculo_id, dia=hoje(), **{coluna: 1})
        .on_conflict_do_update(
            index_elements=[tabela.c.veiculo_id, tabela.c.dia],
            set_={coluna: tabela.c[coluna] + 1},
        )
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
