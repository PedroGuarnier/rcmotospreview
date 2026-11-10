from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.config import obter_config
from app.db import obter_db
from app.models import (
    SITUACOES_EM_ESTOQUE,
    CustoVeiculo,
    Situacao,
    StatusVenda,
    TipoVeiculo,
    Usuario,
    Veiculo,
    Venda,
)
from app.permissoes import P, exigir
from app.rotas.comissoes import relatorio
from app.tempo import hoje

router = APIRouter(prefix="/painel", tags=["painel"])

ZERO = Decimal("0.00")


def _numeros(vendas: int = 0, faturamento: Decimal = ZERO, lucro: Decimal = ZERO):
    ticket = (
        (faturamento / vendas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if vendas else None
    )
    return schemas.NumerosPeriodo(
        vendas=vendas, faturamento=faturamento, lucro=lucro, ticket_medio=ticket
    )


def _meses_ate(fim: date, quantidade: int) -> list[date]:
    meses, ano, mes = [], fim.year, fim.month
    for _ in range(quantidade):
        meses.append(date(ano, mes, 1))
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return list(reversed(meses))


@router.get("", response_model=schemas.PainelOut)
def painel(
    meses: int = Query(6, ge=1, le=24),
    _: Usuario = Depends(exigir(P.painel_ver)),
    db: Session = Depends(obter_db),
):
    cfg = obter_config()
    dia = hoje()
    lista_meses = _meses_ate(dia, meses)

    # Faturamento, lucro e quantidade por mês e por tipo (moto/carro) — vendas ativas.
    mes_col = func.date_trunc("month", Venda.data_venda).label("mes")
    linhas = db.execute(
        select(
            mes_col,
            Veiculo.tipo,
            func.count(Venda.id),
            func.coalesce(func.sum(Venda.valor), 0),
            func.coalesce(func.sum(Venda.lucro), 0),
        )
        .join(Venda.veiculo)
        .where(Venda.status == StatusVenda.ativa, Venda.data_venda >= lista_meses[0])
        .group_by(mes_col, Veiculo.tipo)
    ).all()
    por_mes: dict[tuple[str, TipoVeiculo], tuple[int, Decimal, Decimal]] = {
        (m.strftime("%Y-%m"), tipo): (qtd, fat, lucro) for m, tipo, qtd, fat, lucro in linhas
    }

    def montar(mes: date) -> schemas.MesPainel:
        chave = mes.strftime("%Y-%m")
        moto = por_mes.get((chave, TipoVeiculo.moto), (0, ZERO, ZERO))
        carro = por_mes.get((chave, TipoVeiculo.carro), (0, ZERO, ZERO))
        return schemas.MesPainel(
            mes=chave,
            total=_numeros(moto[0] + carro[0], moto[1] + carro[1], moto[2] + carro[2]),
            moto=_numeros(*moto),
            carro=_numeros(*carro),
        )

    serie = [montar(m) for m in lista_meses]

    # Estoque
    por_situacao = dict(
        db.execute(
            select(Veiculo.situacao, func.count(Veiculo.id)).group_by(Veiculo.situacao)
        ).all()
    )
    em_estoque = Veiculo.situacao.in_(SITUACOES_EM_ESTOQUE)
    compra = db.scalar(select(func.coalesce(func.sum(Veiculo.valor_compra), 0)).where(em_estoque))
    custos = db.scalar(
        select(func.coalesce(func.sum(CustoVeiculo.valor), 0))
        .join(CustoVeiculo.veiculo)
        .where(em_estoque)
    )
    potencial = db.scalar(
        select(func.coalesce(func.sum(Veiculo.preco_venda), 0)).where(
            Veiculo.situacao == Situacao.a_venda
        )
    )

    # Veículos parados há muito tempo na mesma etapa
    limite = datetime.now(UTC) - timedelta(days=cfg.dias_parado_alerta)
    parados = db.scalars(
        select(Veiculo)
        .where(em_estoque, Veiculo.situacao_desde <= limite)
        .order_by(Veiculo.situacao_desde)
        .limit(20)
    ).all()

    return schemas.PainelOut(
        hoje=dia,
        mes_atual=serie[-1],
        meses=serie,
        estoque=schemas.EstoquePainel(
            por_situacao={s.value: por_situacao.get(s, 0) for s in Situacao},
            em_estoque=sum(por_situacao.get(s, 0) for s in SITUACOES_EM_ESTOQUE),
            capital_investido=Decimal(compra) + Decimal(custos),
            potencial_venda=Decimal(potencial),
        ),
        parados=[
            schemas.VeiculoParado(
                id=v.id,
                descricao=v.descricao,
                situacao=v.situacao,
                dias=(datetime.now(UTC) - v.situacao_desde).days,
            )
            for v in parados
        ],
        dias_parado_alerta=cfg.dias_parado_alerta,
        comissoes_mes=relatorio(db, dia.strftime("%Y-%m"), None).por_vendedor,
    )
