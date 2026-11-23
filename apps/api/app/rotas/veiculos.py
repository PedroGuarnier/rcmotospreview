from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import fotos, procedencia, schemas
from app.config import obter_config
from app.db import obter_db
from app.models import (
    SITUACOES_EM_ESTOQUE,
    SITUACOES_VENDIDO,
    AuditLog,
    CustoVeiculo,
    DebitoVeiculo,
    FotoVeiculo,
    Situacao,
    StatusDebito,
    TipoCusto,
    TipoVeiculo,
    Usuario,
    Veiculo,
    Venda,
)
from app.permissoes import P, exigir, pode
from app.servicos import NIVEIS, mudar_situacao, nivel_do_debito, recalcular_venda_do_veiculo
from app.tempo import hoje

router = APIRouter(prefix="/veiculos", tags=["estoque"])

_CARGA = (
    selectinload(Veiculo.custos),
    selectinload(Veiculo.debitos),
    selectinload(Veiculo.fotos),
    selectinload(Veiculo.vendas).selectinload(Venda.cliente),
    selectinload(Veiculo.vendas).selectinload(Venda.vendedor),
)


def _obter(db: Session, veiculo_id: int, *, travar: bool = False) -> Veiculo:
    consulta = select(Veiculo).where(Veiculo.id == veiculo_id).options(*_CARGA)
    if travar:
        consulta = consulta.with_for_update(of=Veiculo)
    veiculo = db.scalar(consulta)
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Veículo não encontrado.")
    return veiculo


def _debito(debito: DebitoVeiculo) -> schemas.DebitoOut:
    pago = debito.status == StatusDebito.pago
    return schemas.DebitoOut(
        id=debito.id,
        tipo=debito.tipo,
        descricao=debito.descricao,
        valor=debito.valor,
        prazo=debito.prazo,
        status=debito.status,
        pago_em=debito.pago_em,
        dias_restantes=None if pago else (debito.prazo - hoje()).days,
        nivel="pago" if pago else nivel_do_debito(debito.prazo, hoje()),
    )


def _resumo(veiculo: Veiculo, com_custos: bool) -> dict:
    dias = max((datetime.now(UTC) - veiculo.situacao_desde).days, 0)
    abertos = veiculo.debitos_abertos
    niveis = [nivel_do_debito(d.prazo, hoje()) for d in abertos]
    dados = {
        "id": veiculo.id,
        "tipo": veiculo.tipo,
        "marca": veiculo.marca,
        "modelo": veiculo.modelo,
        "descricao": veiculo.descricao,
        "ano_fabricacao": veiculo.ano_fabricacao,
        "ano_modelo": veiculo.ano_modelo,
        "cor": veiculo.cor,
        "km": veiculo.km,
        "placa": veiculo.placa,
        "preco_venda": veiculo.preco_venda,
        "situacao": veiculo.situacao,
        "situacao_desde": veiculo.situacao_desde,
        "dias_na_situacao": dias,
        "parado": veiculo.situacao in SITUACOES_EM_ESTOQUE
        and dias >= obter_config().dias_parado_alerta,
        "foto_capa": fotos.url(veiculo.fotos[0].miniatura) if veiculo.fotos else None,
        "debitos_abertos": len(abertos),
        "proximo_prazo": min((d.prazo for d in abertos), default=None),
        "nivel_debito": min(niveis, key=NIVEIS.index) if niveis else None,
    }
    if com_custos:
        dados["valor_compra"] = veiculo.valor_compra
        dados["total_custos"] = veiculo.total_custos
        dados["custo_total"] = veiculo.custo_total
        if veiculo.preco_venda is not None:
            # Débito em aberto ainda vai virar custo: já entra na conta do lucro previsto.
            dados["lucro_previsto"] = (
                veiculo.preco_venda - veiculo.custo_total - veiculo.total_debitos_abertos
            )
    return dados


def _detalhe(veiculo: Veiculo, usuario: Usuario) -> schemas.VeiculoDetalhe:
    com_custos = pode(usuario, P.custos_ver)
    dados = _resumo(veiculo, com_custos)
    dados.update(
        chassi=veiculo.chassi,
        renavam=veiculo.renavam,
        data_compra=veiculo.data_compra,
        observacoes=veiculo.observacoes,
        fotos=[
            schemas.FotoOut(id=f.id, url=fotos.url(f.arquivo), miniatura_url=fotos.url(f.miniatura))
            for f in veiculo.fotos
        ],
    )
    if com_custos:
        dados["custos"] = [schemas.CustoOut.model_validate(c) for c in veiculo.custos]
        dados["debitos"] = [_debito(d) for d in veiculo.debitos]
        dados["total_debitos_abertos"] = veiculo.total_debitos_abertos
    venda = veiculo.venda_ativa
    # O vendedor só enxerga os dados da venda se ela for dele.
    if venda is not None and (pode(usuario, P.vendas_ver_todas) or venda.vendedor_id == usuario.id):
        dados["venda"] = schemas.VendaDoVeiculo(
            id=venda.id,
            data_venda=venda.data_venda,
            valor=venda.valor,
            forma=venda.forma,
            cliente=schemas.PessoaRef.model_validate(venda.cliente),
            vendedor=schemas.PessoaRef.model_validate(venda.vendedor),
            lucro=venda.lucro if com_custos else None,
        )
    return schemas.VeiculoDetalhe(**dados)


def _conferir_duplicados(db: Session, placa: str | None, chassi: str | None, ignorar_id=None):
    for campo, valor, nome in ((Veiculo.placa, placa, "placa"), (Veiculo.chassi, chassi, "chassi")):
        if not valor:
            continue
        outro = db.scalar(select(Veiculo).where(campo == valor))
        if outro is not None and outro.id != ignorar_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Já existe um veículo com esta {nome}: {outro.descricao}."
                if nome == "placa"
                else f"Já existe um veículo com este {nome}: {outro.descricao}.",
            )


def _conferir_situacao(veiculo: Veiculo, nova: Situacao) -> None:
    """Regras da linha do veículo que valem para mudança manual de situação."""
    vendido = veiculo.venda_ativa is not None
    if vendido and nova not in SITUACOES_VENDIDO:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Veículo vendido: para voltar ao estoque, cancele a venda.",
        )
    if not vendido and nova not in SITUACOES_EM_ESTOQUE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta situação só vale para veículo vendido. Registre a venda primeiro.",
        )
    if nova == Situacao.a_venda and veiculo.preco_venda is None:
        raise HTTPException(
            422,
            "Informe o preço de venda antes de colocar o veículo à venda.",
        )
    if nova == Situacao.a_venda and veiculo.debitos_abertos:
        nomes = ", ".join(d.descricao for d in veiculo.debitos_abertos)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Este veículo tem débito em aberto ({nomes}). Quite antes de colocar à venda.",
        )


@router.get("", response_model=list[schemas.VeiculoOut])
def listar(
    situacao: Situacao | None = None,
    tipo: TipoVeiculo | None = None,
    busca: str | None = None,
    grupo: str | None = None,  # "estoque" | "vendidos"
    usuario: Usuario = Depends(exigir(P.estoque_ver)),
    db: Session = Depends(obter_db),
):
    consulta = select(Veiculo).options(*_CARGA)
    if situacao:
        consulta = consulta.where(Veiculo.situacao == situacao)
    if grupo == "estoque":
        consulta = consulta.where(Veiculo.situacao.in_(SITUACOES_EM_ESTOQUE))
    elif grupo == "vendidos":
        consulta = consulta.where(Veiculo.situacao.in_(SITUACOES_VENDIDO))
    if tipo:
        consulta = consulta.where(Veiculo.tipo == tipo)
    if busca and busca.strip():
        for termo in busca.split()[:5]:
            padrao = f"%{termo}%"
            consulta = consulta.where(
                or_(
                    Veiculo.marca.ilike(padrao),
                    Veiculo.modelo.ilike(padrao),
                    Veiculo.placa.ilike(padrao),
                    Veiculo.chassi.ilike(padrao),
                    Veiculo.cor.ilike(padrao),
                )
            )
    consulta = consulta.order_by(Veiculo.situacao_desde.desc(), Veiculo.id.desc())
    com_custos = pode(usuario, P.custos_ver)
    return [_resumo(v, com_custos) for v in db.scalars(consulta)]


@router.post("", response_model=schemas.VeiculoDetalhe, status_code=status.HTTP_201_CREATED)
def criar(
    dados: schemas.VeiculoCriar,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    _conferir_duplicados(db, dados.placa, dados.chassi)
    veiculo = Veiculo(**dados.model_dump(exclude={"situacao"}), situacao=Situacao.compra)
    _conferir_situacao(veiculo, dados.situacao)
    veiculo.situacao = dados.situacao
    db.add(veiculo)
    db.flush()
    procedencia.ligar_laudos_ao_veiculo(db, veiculo)
    db.commit()
    return _detalhe(_obter(db, veiculo.id), usuario)


@router.get("/{veiculo_id}", response_model=schemas.VeiculoDetalhe)
def detalhar(
    veiculo_id: int,
    usuario: Usuario = Depends(exigir(P.estoque_ver)),
    db: Session = Depends(obter_db),
):
    return _detalhe(_obter(db, veiculo_id), usuario)


@router.patch("/{veiculo_id}", response_model=schemas.VeiculoDetalhe)
def atualizar(
    veiculo_id: int,
    dados: schemas.VeiculoAtualizar,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id, travar=True)
    campos = dados.model_dump(exclude_unset=True)
    for obrigatorio in ("tipo", "marca", "modelo", "valor_compra"):
        if obrigatorio in campos and campos[obrigatorio] is None:
            raise HTTPException(422, f"O campo {obrigatorio} é obrigatório.")
    _conferir_duplicados(db, campos.get("placa"), campos.get("chassi"), ignorar_id=veiculo.id)
    nova_situacao = campos.pop("situacao", None)
    for campo, valor in campos.items():
        setattr(veiculo, campo, valor)
    if veiculo.situacao == Situacao.a_venda and veiculo.preco_venda is None:
        raise HTTPException(422, "Veículo à venda precisa ter preço de venda.")
    if nova_situacao is not None and nova_situacao != veiculo.situacao:
        if nova_situacao == Situacao.vendido and veiculo.venda_ativa is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Para marcar como vendido, registre a venda."
            )
        _conferir_situacao(veiculo, nova_situacao)
        mudar_situacao(veiculo, nova_situacao)
    if "valor_compra" in campos:
        recalcular_venda_do_veiculo(veiculo)
    if "placa" in campos:
        procedencia.ligar_laudos_ao_veiculo(db, veiculo)
    db.commit()
    return _detalhe(_obter(db, veiculo.id), usuario)


@router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(
    veiculo_id: int,
    _: Usuario = Depends(exigir(P.usuarios_gerir)),  # só o dono
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id, travar=True)
    if veiculo.vendas:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este veículo tem venda registrada e não pode ser excluído.",
        )
    arquivos = [c for f in veiculo.fotos for c in (f.arquivo, f.miniatura)]
    db.delete(veiculo)
    db.commit()
    fotos.apagar_arquivos(*arquivos)


# ---------- Custos ----------


@router.post(
    "/{veiculo_id}/custos",
    response_model=schemas.VeiculoDetalhe,
    status_code=status.HTTP_201_CREATED,
)
def lancar_custo(
    veiculo_id: int,
    dados: schemas.CustoCriar,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id, travar=True)
    data = dados.data or hoje()
    if data > hoje():
        raise HTTPException(422, "A data não pode ser futura.")
    veiculo.custos.append(
        CustoVeiculo(
            tipo=dados.tipo,
            descricao=dados.descricao,
            valor=dados.valor,
            data=data,
            registrado_por_id=usuario.id,
        )
    )
    recalcular_venda_do_veiculo(veiculo)
    db.commit()
    return _detalhe(_obter(db, veiculo.id), usuario)


@router.delete("/{veiculo_id}/custos/{custo_id}", response_model=schemas.VeiculoDetalhe)
def remover_custo(
    veiculo_id: int,
    custo_id: int,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id, travar=True)
    custo = next((c for c in veiculo.custos if c.id == custo_id), None)
    if custo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Custo não encontrado.")
    if any(d.custo_id == custo.id for d in veiculo.debitos):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este custo veio de um débito pago. Para tirá-lo, desfaça o pagamento do débito.",
        )
    veiculo.custos.remove(custo)
    recalcular_venda_do_veiculo(veiculo)
    db.commit()
    return _detalhe(_obter(db, veiculo.id), usuario)


# ---------- Débitos (IPVA, licenciamento, multas) ----------


def _achar_debito(veiculo: Veiculo, debito_id: int) -> DebitoVeiculo:
    debito = next((d for d in veiculo.debitos if d.id == debito_id), None)
    if debito is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Débito não encontrado.")
    return debito


@router.post(
    "/{veiculo_id}/debitos",
    response_model=schemas.VeiculoDetalhe,
    status_code=status.HTTP_201_CREATED,
)
def lancar_debito(
    veiculo_id: int,
    dados: schemas.DebitoCriar,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id, travar=True)
    veiculo.debitos.append(
        DebitoVeiculo(
            tipo=dados.tipo,
            descricao=dados.descricao,
            valor=dados.valor,
            prazo=dados.prazo,
            status=StatusDebito.aberto,
            registrado_por_id=usuario.id,
        )
    )
    # Veículo com débito aberto não fica à venda: volta para a etapa de documentação.
    if veiculo.situacao == Situacao.a_venda:
        mudar_situacao(veiculo, Situacao.documentacao)
    db.commit()
    return _detalhe(_obter(db, veiculo.id), usuario)


@router.post("/{veiculo_id}/debitos/{debito_id}/pagar", response_model=schemas.VeiculoDetalhe)
def pagar_debito(
    veiculo_id: int,
    debito_id: int,
    dados: schemas.DebitoPagar,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    """Quita o débito: ele vira custo do veículo, pelo valor realmente pago."""
    veiculo = _obter(db, veiculo_id, travar=True)
    debito = _achar_debito(veiculo, debito_id)
    if debito.status != StatusDebito.aberto:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este débito já foi pago.")
    data = dados.data or hoje()
    if data > hoje():
        raise HTTPException(422, "A data do pagamento não pode ser futura.")
    custo = CustoVeiculo(
        tipo=TipoCusto.debito,
        descricao=debito.descricao,
        valor=dados.valor_pago or debito.valor,
        data=data,
        registrado_por_id=usuario.id,
    )
    veiculo.custos.append(custo)
    db.flush()
    debito.status = StatusDebito.pago
    debito.pago_em = data
    debito.custo_id = custo.id
    recalcular_venda_do_veiculo(veiculo)
    db.commit()
    return _detalhe(_obter(db, veiculo.id), usuario)


@router.post("/{veiculo_id}/debitos/{debito_id}/reabrir", response_model=schemas.VeiculoDetalhe)
def reabrir_debito(
    veiculo_id: int,
    debito_id: int,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    """Desfaz um pagamento marcado por engano: o custo gerado sai e o débito volta a aberto."""
    veiculo = _obter(db, veiculo_id, travar=True)
    debito = _achar_debito(veiculo, debito_id)
    if debito.status != StatusDebito.pago:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este débito não está pago.")
    custo = next((c for c in veiculo.custos if c.id == debito.custo_id), None)
    if custo is not None:
        veiculo.custos.remove(custo)
    debito.status = StatusDebito.aberto
    debito.pago_em = None
    debito.custo_id = None
    if veiculo.situacao == Situacao.a_venda:
        mudar_situacao(veiculo, Situacao.documentacao)
    recalcular_venda_do_veiculo(veiculo)
    db.commit()
    return _detalhe(_obter(db, veiculo.id), usuario)


@router.delete("/{veiculo_id}/debitos/{debito_id}", response_model=schemas.VeiculoDetalhe)
def remover_debito(
    veiculo_id: int,
    debito_id: int,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id, travar=True)
    debito = _achar_debito(veiculo, debito_id)
    if debito.status == StatusDebito.pago:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Débito já pago: reabra o débito antes de excluir (o custo gerado sai junto).",
        )
    veiculo.debitos.remove(debito)
    db.commit()
    return _detalhe(_obter(db, veiculo.id), usuario)


# ---------- Fotos ----------


@router.post(
    "/{veiculo_id}/fotos",
    response_model=schemas.VeiculoDetalhe,
    status_code=status.HTTP_201_CREATED,
)
def enviar_foto(
    veiculo_id: int,
    arquivo: UploadFile = File(...),
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id)
    if len(veiculo.fotos) >= 30:
        raise HTTPException(status.HTTP_409_CONFLICT, "Limite de 30 fotos por veículo.")
    caminho, miniatura = fotos.salvar_foto(veiculo.id, fotos.ler_com_limite(arquivo))
    proxima = db.scalar(
        select(func.coalesce(func.max(FotoVeiculo.ordem), -1) + 1).where(
            FotoVeiculo.veiculo_id == veiculo.id
        )
    )
    try:
        db.add(
            FotoVeiculo(veiculo_id=veiculo.id, arquivo=caminho, miniatura=miniatura, ordem=proxima)
        )
        db.commit()
    except Exception:
        fotos.apagar_arquivos(caminho, miniatura)
        raise
    db.expire_all()
    return _detalhe(_obter(db, veiculo.id), usuario)


@router.post("/{veiculo_id}/fotos/{foto_id}/capa", response_model=schemas.VeiculoDetalhe)
def definir_capa(
    veiculo_id: int,
    foto_id: int,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id, travar=True)
    if not any(f.id == foto_id for f in veiculo.fotos):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada.")
    restantes = [f for f in veiculo.fotos if f.id != foto_id]
    for foto in veiculo.fotos:
        foto.ordem = 0 if foto.id == foto_id else restantes.index(foto) + 1
    db.commit()
    db.expire_all()
    return _detalhe(_obter(db, veiculo.id), usuario)


@router.delete("/{veiculo_id}/fotos/{foto_id}", response_model=schemas.VeiculoDetalhe)
def remover_foto(
    veiculo_id: int,
    foto_id: int,
    usuario: Usuario = Depends(exigir(P.estoque_editar)),
    db: Session = Depends(obter_db),
):
    veiculo = _obter(db, veiculo_id, travar=True)
    foto = next((f for f in veiculo.fotos if f.id == foto_id), None)
    if foto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada.")
    arquivos = (foto.arquivo, foto.miniatura)
    veiculo.fotos.remove(foto)
    db.commit()
    fotos.apagar_arquivos(*arquivos)
    return _detalhe(_obter(db, veiculo.id), usuario)


# ---------- Histórico do veículo ----------


@router.get("/{veiculo_id}/historico", response_model=list[schemas.EventoOut])
def historico(
    veiculo_id: int,
    _: Usuario = Depends(exigir(P.historico_veiculo_ver)),
    db: Session = Depends(obter_db),
):
    return db.scalars(
        select(AuditLog)
        .where(AuditLog.veiculo_id == veiculo_id)
        .order_by(AuditLog.id.desc())
        .limit(200)
    ).all()
