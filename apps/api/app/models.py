"""Modelos do banco.

Dinheiro é sempre Numeric(12, 2) / Decimal. Enums são gravados como texto (sem tipo
nativo do Postgres) para que novos valores não exijam migração de tipo.
"""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Perfil(enum.StrEnum):
    dono = "dono"
    gerente = "gerente"
    financeiro = "financeiro"
    vendedor = "vendedor"


class TipoVeiculo(enum.StrEnum):
    moto = "moto"
    carro = "carro"


class Situacao(enum.StrEnum):
    """Etapas da linha do veículo (contrato, cláusula 1, item 4)."""

    compra = "compra"
    documentacao = "documentacao"
    preparacao = "preparacao"
    a_venda = "a_venda"
    vendido = "vendido"
    pos_venda = "pos_venda"
    concluido = "concluido"


SITUACOES_EM_ESTOQUE = (
    Situacao.compra,
    Situacao.documentacao,
    Situacao.preparacao,
    Situacao.a_venda,
)
SITUACOES_VENDIDO = (Situacao.vendido, Situacao.pos_venda, Situacao.concluido)


class TipoCusto(enum.StrEnum):
    manutencao = "manutencao"
    documentacao = "documentacao"
    debito = "debito"  # IPVA, licenciamento, multas pagos pela loja
    outro = "outro"


class FormaPagamento(enum.StrEnum):
    a_vista = "a_vista"
    financiado_banco = "financiado_banco"
    parcelado_loja = "parcelado_loja"


class RegraComissao(enum.StrEnum):
    percentual_lucro = "percentual_lucro"
    percentual_venda = "percentual_venda"
    valor_fixo = "valor_fixo"


class StatusVenda(enum.StrEnum):
    ativa = "ativa"
    cancelada = "cancelada"


class StatusComissao(enum.StrEnum):
    pendente = "pendente"
    paga = "paga"
    cancelada = "cancelada"


def _enum(tipo: type[enum.Enum]) -> SAEnum:
    return SAEnum(
        tipo, native_enum=False, length=30, values_callable=lambda e: [m.value for m in e]
    )


Dinheiro = Numeric(12, 2)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[Perfil] = mapped_column(_enum(Perfil))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # Módulo "gastos pessoais investidos na loja": só o dono e quem ele habilitar.
    acesso_aportes: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    # Regra de comissão do vendedor (nula = não gera comissão).
    comissao_regra: Mapped[RegraComissao | None] = mapped_column(_enum(RegraComissao))
    comissao_valor: Mapped[Decimal | None] = mapped_column(Dinheiro)
    # Incrementado ao trocar senha/desativar: invalida as sessões abertas.
    versao_sessao: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    tentativas_login: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Veiculo(Base):
    __tablename__ = "veiculos"
    __table_args__ = (
        Index("ix_veiculos_situacao", "situacao"),
        Index(
            "uq_veiculos_placa", "placa", unique=True, postgresql_where=text("placa IS NOT NULL")
        ),
        Index(
            "uq_veiculos_chassi", "chassi", unique=True, postgresql_where=text("chassi IS NOT NULL")
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoVeiculo] = mapped_column(_enum(TipoVeiculo))
    marca: Mapped[str] = mapped_column(String(60))
    modelo: Mapped[str] = mapped_column(String(120))
    ano_fabricacao: Mapped[int | None] = mapped_column(Integer)
    ano_modelo: Mapped[int | None] = mapped_column(Integer)
    cor: Mapped[str | None] = mapped_column(String(40))
    km: Mapped[int | None] = mapped_column(Integer)
    placa: Mapped[str | None] = mapped_column(String(8))
    chassi: Mapped[str | None] = mapped_column(String(17))
    renavam: Mapped[str | None] = mapped_column(String(11))
    valor_compra: Mapped[Decimal] = mapped_column(Dinheiro)
    data_compra: Mapped[date | None] = mapped_column(Date)
    preco_venda: Mapped[Decimal | None] = mapped_column(Dinheiro)
    situacao: Mapped[Situacao] = mapped_column(_enum(Situacao), default=Situacao.compra)
    # Quando entrou na situação atual: base do alerta de "parado há muito tempo".
    situacao_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    custos: Mapped[list["CustoVeiculo"]] = relationship(
        back_populates="veiculo", cascade="all, delete-orphan", order_by="CustoVeiculo.id"
    )
    fotos: Mapped[list["FotoVeiculo"]] = relationship(
        back_populates="veiculo",
        cascade="all, delete-orphan",
        order_by="FotoVeiculo.ordem, FotoVeiculo.id",
    )
    vendas: Mapped[list["Venda"]] = relationship(back_populates="veiculo", order_by="Venda.id")

    @property
    def total_custos(self) -> Decimal:
        return sum((c.valor for c in self.custos), Decimal("0.00"))

    @property
    def custo_total(self) -> Decimal:
        """Tudo o que a loja investiu no veículo: compra + custos."""
        return self.valor_compra + self.total_custos

    @property
    def venda_ativa(self) -> "Venda | None":
        return next((v for v in self.vendas if v.status == StatusVenda.ativa), None)

    @property
    def descricao(self) -> str:
        partes = [self.marca, self.modelo]
        if self.ano_modelo:
            partes.append(str(self.ano_modelo))
        if self.placa:
            partes.append(f"({self.placa})")
        return " ".join(partes)


class CustoVeiculo(Base):
    __tablename__ = "custos_veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculos.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoCusto] = mapped_column(_enum(TipoCusto))
    descricao: Mapped[str] = mapped_column(String(200))
    valor: Mapped[Decimal] = mapped_column(Dinheiro)
    data: Mapped[date] = mapped_column(Date)
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    veiculo: Mapped[Veiculo] = relationship(back_populates="custos")


class FotoVeiculo(Base):
    __tablename__ = "fotos_veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculos.id", ondelete="CASCADE"), index=True
    )
    arquivo: Mapped[str] = mapped_column(String(255))  # relativo a UPLOADS_DIR
    miniatura: Mapped[str] = mapped_column(String(255))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    veiculo: Mapped[Veiculo] = relationship(back_populates="fotos")


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (
        Index(
            "uq_clientes_cpf_cnpj",
            "cpf_cnpj",
            unique=True,
            postgresql_where=text("cpf_cnpj IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160))
    cpf_cnpj: Mapped[str | None] = mapped_column(String(14))  # só dígitos
    telefone: Mapped[str | None] = mapped_column(String(20))  # só dígitos, com DDD
    email: Mapped[str | None] = mapped_column(String(255))
    endereco: Mapped[str | None] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Venda(Base):
    __tablename__ = "vendas"
    __table_args__ = (
        # Um veículo só pode ter uma venda ativa por vez.
        Index(
            "uq_vendas_veiculo_ativa",
            "veiculo_id",
            unique=True,
            postgresql_where=text("status = 'ativa'"),
        ),
        Index("ix_vendas_data", "data_venda"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(ForeignKey("veiculos.id"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    vendedor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    registrada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    data_venda: Mapped[date] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Dinheiro)
    forma: Mapped[FormaPagamento] = mapped_column(_enum(FormaPagamento))
    # Financiado no banco
    banco: Mapped[str | None] = mapped_column(String(80))
    # Entrada (financiado ou parcelado) e plano do parcelado na loja
    entrada: Mapped[Decimal | None] = mapped_column(Dinheiro)
    numero_parcelas: Mapped[int | None] = mapped_column(Integer)
    valor_parcela: Mapped[Decimal | None] = mapped_column(Dinheiro)
    primeiro_vencimento: Mapped[date | None] = mapped_column(Date)
    # Retrato do custo no momento da venda: lucro = valor − valor_compra − total_custos
    valor_compra: Mapped[Decimal] = mapped_column(Dinheiro)
    total_custos: Mapped[Decimal] = mapped_column(Dinheiro)
    lucro: Mapped[Decimal] = mapped_column(Dinheiro)
    status: Mapped[StatusVenda] = mapped_column(_enum(StatusVenda), default=StatusVenda.ativa)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(300))
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    veiculo: Mapped[Veiculo] = relationship(back_populates="vendas")
    cliente: Mapped[Cliente] = relationship()
    vendedor: Mapped[Usuario] = relationship(foreign_keys=[vendedor_id])
    comissao: Mapped["Comissao | None"] = relationship(back_populates="venda", uselist=False)


class Comissao(Base):
    __tablename__ = "comissoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(ForeignKey("vendas.id"), unique=True)
    vendedor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    # Retrato da regra do vendedor no momento da venda
    regra: Mapped[RegraComissao] = mapped_column(_enum(RegraComissao))
    regra_valor: Mapped[Decimal] = mapped_column(Dinheiro)
    valor: Mapped[Decimal] = mapped_column(Dinheiro)
    status: Mapped[StatusComissao] = mapped_column(
        _enum(StatusComissao), default=StatusComissao.pendente
    )
    paga_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    venda: Mapped[Venda] = relationship(back_populates="comissao")
    vendedor: Mapped[Usuario] = relationship()


class Aporte(Base):
    """Gastos pessoais do dono investidos na loja."""

    __tablename__ = "aportes"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Dinheiro)
    descricao: Mapped[str] = mapped_column(String(200))
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    registrado_por: Mapped[Usuario | None] = relationship()


class AuditLog(Base):
    """Histórico de ações: quem, quando, o quê. Só inserção — nunca é alterado."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_entidade", "entidade", "entidade_id"),
        Index("ix_audit_criado_em", "criado_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    usuario_nome: Mapped[str | None] = mapped_column(String(120))
    acao: Mapped[str] = mapped_column(String(30))  # criou | alterou | excluiu | entrou | ...
    entidade: Mapped[str] = mapped_column(String(40))
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    # Veículo relacionado (custos, fotos e vendas apontam para o veículo)
    veiculo_id: Mapped[int | None] = mapped_column(Integer, index=True)
    resumo: Mapped[str | None] = mapped_column(String(300))
    alteracoes: Mapped[dict | None] = mapped_column(JSONB)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
