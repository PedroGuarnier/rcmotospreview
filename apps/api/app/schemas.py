from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app import validacao
from app.models import (
    FormaPagamento,
    Perfil,
    RegraComissao,
    Semaforo,
    Situacao,
    StatusComissao,
    StatusVenda,
    TipoCusto,
    TipoVeiculo,
)


def _vazio_para_none(fn):
    def _aplicar(valor: str | None) -> str | None:
        if valor is None or not valor.strip():
            return None
        return fn(valor)

    return _aplicar


Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Valor = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
ValorPositivo = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Placa = Annotated[str | None, AfterValidator(_vazio_para_none(validacao.normalizar_placa))]
Chassi = Annotated[str | None, AfterValidator(_vazio_para_none(validacao.normalizar_chassi))]
Renavam = Annotated[str | None, AfterValidator(_vazio_para_none(validacao.normalizar_renavam))]
Telefone = Annotated[str | None, AfterValidator(_vazio_para_none(validacao.normalizar_telefone))]
CpfCnpj = Annotated[str | None, AfterValidator(_vazio_para_none(validacao.normalizar_cpf_cnpj))]
TextoOpcional = Annotated[str | None, AfterValidator(_vazio_para_none(str.strip))]
Senha = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class Modelo(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth / usuários ----------


class Credenciais(BaseModel):
    email: str
    senha: str


class TrocaSenha(BaseModel):
    senha_atual: str
    nova_senha: Senha


class UsuarioOut(Modelo):
    id: int
    nome: str
    email: str
    perfil: Perfil
    ativo: bool
    acesso_aportes: bool
    comissao_regra: RegraComissao | None
    comissao_valor: Decimal | None


class EuOut(UsuarioOut):
    permissoes: list[str]
    dados_demo: bool


class _RegraComissaoMixin(BaseModel):
    @model_validator(mode="after")
    def _conferir_comissao(self) -> Self:
        regra = getattr(self, "comissao_regra", None)
        valor = getattr(self, "comissao_valor", None)
        if regra is not None:
            if valor is None:
                raise ValueError("Informe o valor da regra de comissão.")
            if regra != RegraComissao.valor_fixo and valor > 100:
                raise ValueError("O percentual de comissão não pode passar de 100%.")
        return self


class UsuarioCriar(_RegraComissaoMixin):
    nome: Texto
    email: EmailStr
    senha: Senha
    perfil: Perfil
    acesso_aportes: bool = False
    comissao_regra: RegraComissao | None = None
    comissao_valor: Valor | None = None


class UsuarioAtualizar(_RegraComissaoMixin):
    nome: Texto | None = None
    email: EmailStr | None = None
    perfil: Perfil | None = None
    ativo: bool | None = None
    acesso_aportes: bool | None = None
    comissao_regra: RegraComissao | None = None
    comissao_valor: Valor | None = None


class NovaSenha(BaseModel):
    nova_senha: Senha


class PessoaRef(Modelo):
    id: int
    nome: str


# ---------- Estoque ----------

SITUACOES_MANUAIS_ESTOQUE = {
    Situacao.compra,
    Situacao.documentacao,
    Situacao.preparacao,
    Situacao.a_venda,
}


class VeiculoCriar(BaseModel):
    tipo: TipoVeiculo
    marca: Texto
    modelo: Texto
    ano_fabricacao: int | None = Field(None, ge=1950, le=2100)
    ano_modelo: int | None = Field(None, ge=1950, le=2100)
    cor: TextoOpcional = None
    km: int | None = Field(None, ge=0, le=9_999_999)
    placa: Placa = None
    chassi: Chassi = None
    renavam: Renavam = None
    valor_compra: Valor
    data_compra: date | None = None
    preco_venda: ValorPositivo | None = None
    situacao: Situacao = Situacao.compra
    observacoes: TextoOpcional = None


class VeiculoAtualizar(BaseModel):
    tipo: TipoVeiculo | None = None
    marca: Texto | None = None
    modelo: Texto | None = None
    ano_fabricacao: int | None = Field(None, ge=1950, le=2100)
    ano_modelo: int | None = Field(None, ge=1950, le=2100)
    cor: TextoOpcional = None
    km: int | None = Field(None, ge=0, le=9_999_999)
    placa: Placa = None
    chassi: Chassi = None
    renavam: Renavam = None
    valor_compra: Valor | None = None
    data_compra: date | None = None
    preco_venda: ValorPositivo | None = None
    situacao: Situacao | None = None
    observacoes: TextoOpcional = None


class CustoCriar(BaseModel):
    tipo: TipoCusto
    descricao: Texto = Field(max_length=200)
    valor: ValorPositivo
    data: date | None = None


class CustoOut(Modelo):
    id: int
    tipo: TipoCusto
    descricao: str
    valor: Decimal
    data: date


class FotoOut(BaseModel):
    id: int
    url: str
    miniatura_url: str


class VendaDoVeiculo(BaseModel):
    id: int
    data_venda: date
    valor: Decimal
    forma: FormaPagamento
    cliente: PessoaRef
    vendedor: PessoaRef
    lucro: Decimal | None = None


class VeiculoOut(BaseModel):
    id: int
    tipo: TipoVeiculo
    marca: str
    modelo: str
    descricao: str
    ano_fabricacao: int | None
    ano_modelo: int | None
    cor: str | None
    km: int | None
    placa: str | None
    preco_venda: Decimal | None
    situacao: Situacao
    situacao_desde: datetime
    dias_na_situacao: int
    foto_capa: str | None
    # Só para quem tem a permissão custos.ver
    valor_compra: Decimal | None = None
    total_custos: Decimal | None = None
    custo_total: Decimal | None = None
    lucro_previsto: Decimal | None = None


class VeiculoDetalhe(VeiculoOut):
    chassi: str | None
    renavam: str | None
    data_compra: date | None
    observacoes: str | None
    fotos: list[FotoOut]
    custos: list[CustoOut] | None = None
    venda: VendaDoVeiculo | None = None


# ---------- Clientes ----------


class ClienteCriar(BaseModel):
    nome: Texto = Field(max_length=160)
    cpf_cnpj: CpfCnpj = None
    telefone: Telefone = None
    email: EmailStr | None = None
    endereco: TextoOpcional = None


class ClienteAtualizar(BaseModel):
    nome: Texto | None = Field(None, max_length=160)
    cpf_cnpj: CpfCnpj = None
    telefone: Telefone = None
    email: EmailStr | None = None
    endereco: TextoOpcional = None


class ClienteOut(Modelo):
    id: int
    nome: str
    cpf_cnpj: str | None
    telefone: str | None
    email: str | None
    endereco: str | None


# ---------- Vendas / comissões ----------


class VendaCriar(BaseModel):
    veiculo_id: int
    cliente_id: int | None = None
    cliente_novo: ClienteCriar | None = None
    vendedor_id: int | None = None  # padrão: quem está registrando
    valor: ValorPositivo
    forma: FormaPagamento
    data_venda: date | None = None  # padrão: hoje
    banco: TextoOpcional = None
    entrada: Valor | None = None
    numero_parcelas: int | None = Field(None, ge=1, le=120)
    valor_parcela: ValorPositivo | None = None
    primeiro_vencimento: date | None = None
    observacoes: TextoOpcional = None

    @model_validator(mode="after")
    def _conferir(self) -> Self:
        if (self.cliente_id is None) == (self.cliente_novo is None):
            raise ValueError("Informe o comprador: escolha um cliente ou cadastre um novo.")
        if self.entrada is not None and self.entrada > self.valor:
            raise ValueError("A entrada não pode ser maior que o valor da venda.")
        if self.forma == FormaPagamento.parcelado_loja:
            if not (self.numero_parcelas and self.valor_parcela and self.primeiro_vencimento):
                raise ValueError(
                    "No parcelado na loja, informe número de parcelas, valor da parcela "
                    "e primeiro vencimento."
                )
            total = (self.entrada or Decimal(0)) + self.numero_parcelas * self.valor_parcela
            tolerancia = Decimal("0.01") * self.numero_parcelas
            if total < self.valor - tolerancia:
                raise ValueError("Entrada + parcelas não cobrem o valor da venda.")
        else:
            if self.numero_parcelas or self.valor_parcela or self.primeiro_vencimento:
                raise ValueError("Parcelas só se aplicam ao parcelado na loja.")
        if self.forma == FormaPagamento.a_vista and self.entrada:
            raise ValueError("Venda à vista não tem entrada.")
        return self


class VendaCancelar(BaseModel):
    motivo: Texto = Field(max_length=300)


class ComissaoResumo(BaseModel):
    id: int
    valor: Decimal
    status: StatusComissao
    regra: RegraComissao
    regra_valor: Decimal


class VeiculoRef(BaseModel):
    id: int
    descricao: str
    tipo: TipoVeiculo
    placa: str | None


class VendaOut(BaseModel):
    id: int
    data_venda: date
    valor: Decimal
    forma: FormaPagamento
    status: StatusVenda
    veiculo: VeiculoRef
    cliente: ClienteOut
    vendedor: PessoaRef
    banco: str | None
    entrada: Decimal | None
    numero_parcelas: int | None
    valor_parcela: Decimal | None
    primeiro_vencimento: date | None
    observacoes: str | None
    motivo_cancelamento: str | None
    cancelada_em: datetime | None
    # custos.ver
    valor_compra: Decimal | None = None
    total_custos: Decimal | None = None
    lucro: Decimal | None = None
    # comissoes.ver_todas ou a própria
    comissao: ComissaoResumo | None = None


class ComissaoOut(BaseModel):
    id: int
    valor: Decimal
    status: StatusComissao
    regra: RegraComissao
    regra_valor: Decimal
    paga_em: datetime | None
    vendedor: PessoaRef
    venda_id: int
    data_venda: date
    valor_venda: Decimal
    veiculo: str


class ComissaoPorVendedor(BaseModel):
    vendedor: PessoaRef
    vendas: int
    total: Decimal
    pago: Decimal
    pendente: Decimal


class RelatorioComissoes(BaseModel):
    mes: str
    itens: list[ComissaoOut]
    por_vendedor: list[ComissaoPorVendedor]
    total: Decimal
    pendente: Decimal


# ---------- Aportes ----------


class AporteCriar(BaseModel):
    data: date | None = None
    valor: ValorPositivo
    descricao: Texto = Field(max_length=200)


class AporteOut(BaseModel):
    id: int
    data: date
    valor: Decimal
    descricao: str
    registrado_por: str | None


class AportesOut(BaseModel):
    itens: list[AporteOut]
    total: Decimal


# ---------- Histórico ----------


class EventoOut(Modelo):
    id: int
    usuario_id: int | None
    usuario_nome: str | None
    acao: str
    entidade: str
    entidade_id: int | None
    veiculo_id: int | None
    resumo: str | None
    alteracoes: dict | None
    criado_em: datetime


# ---------- Painel ----------


class NumerosPeriodo(BaseModel):
    vendas: int
    faturamento: Decimal
    lucro: Decimal
    ticket_medio: Decimal | None


class MesPainel(BaseModel):
    mes: str  # AAAA-MM
    total: NumerosPeriodo
    moto: NumerosPeriodo
    carro: NumerosPeriodo


class EstoquePainel(BaseModel):
    por_situacao: dict[str, int]
    em_estoque: int
    capital_investido: Decimal
    potencial_venda: Decimal


class VeiculoParado(BaseModel):
    id: int
    descricao: str
    situacao: Situacao
    dias: int


class PainelOut(BaseModel):
    hoje: date
    mes_atual: MesPainel
    meses: list[MesPainel]
    estoque: EstoquePainel
    parados: list[VeiculoParado]
    dias_parado_alerta: int
    comissoes_mes: list[ComissaoPorVendedor]


# ---------- Procedência ----------


class ConsultaPlaca(BaseModel):
    placa: Annotated[str, AfterValidator(validacao.normalizar_placa)]


class ItemLaudo(BaseModel):
    chave: str
    titulo: str
    situacao: str  # ok | atencao | alerta
    detalhe: str


class MarcoHistorico(BaseModel):
    """Um ponto da linha do tempo do veículo."""

    quando: str  # "2021" ou "10/11/2026"
    titulo: str
    detalhe: str | None = None


class LaudoOut(BaseModel):
    id: int
    placa: str
    semaforo: Semaforo
    ilustrativo: bool
    provedor: str
    criado_em: datetime
    consultado_por: str | None
    veiculo_id: int | None
    veiculo_descricao: str | None
    dados_veiculo: dict
    itens: list[ItemLaudo]
    historico: list[MarcoHistorico]


class SituacaoProcedencia(BaseModel):
    disponivel: bool
    ilustrativo: bool


# ---------- Site público ----------


class VeiculoPublico(BaseModel):
    id: int
    tipo: TipoVeiculo
    marca: str
    modelo: str
    ano_fabricacao: int | None
    ano_modelo: int | None
    cor: str | None
    km: int | None
    preco: Decimal
    # A placa completa não é publicada (evita clonagem): só o início e o final.
    placa_mascarada: str | None
    fotos: list[FotoOut]
    dias_na_loja: int
    semaforo: Semaforo | None


class CatalogoPublico(BaseModel):
    veiculos: list[VeiculoPublico]
    ilustrativo: bool


class ProcedenciaPublica(BaseModel):
    placa: str  # completa quando o visitante digitou; mascarada quando veio do anúncio
    veiculo: VeiculoPublico
    semaforo: Semaforo | None
    consultado_em: datetime | None
    ilustrativo: bool
    itens: list[ItemLaudo]
    historico: list[MarcoHistorico]
