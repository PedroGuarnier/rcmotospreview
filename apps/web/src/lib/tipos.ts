// Espelha os schemas da API (apps/api/app/schemas.py). Dinheiro vem como texto ("14900.00").

export type Perfil = "dono" | "gerente" | "financeiro" | "vendedor";
export type TipoVeiculo = "moto" | "carro";
export type Situacao =
  | "compra"
  | "documentacao"
  | "preparacao"
  | "a_venda"
  | "vendido"
  | "pos_venda"
  | "concluido";
export type TipoCusto = "manutencao" | "documentacao" | "debito" | "outro";
export type FormaPagamento = "a_vista" | "financiado_banco" | "parcelado_loja";
export type RegraComissao = "percentual_lucro" | "percentual_venda" | "valor_fixo";
export type StatusComissao = "pendente" | "paga" | "cancelada";

export type Permissao =
  | "estoque.ver"
  | "estoque.editar"
  | "custos.ver"
  | "procedencia.consultar"
  | "vendas.registrar"
  | "vendas.ver_todas"
  | "vendas.cancelar"
  | "clientes.ver"
  | "comissoes.ver_todas"
  | "comissoes.pagar"
  | "painel.ver"
  | "usuarios.gerir"
  | "aportes.ver"
  | "historico.ver"
  | "historico.veiculo_ver";

export interface Usuario {
  id: number;
  nome: string;
  email: string;
  perfil: Perfil;
  ativo: boolean;
  acesso_aportes: boolean;
  comissao_regra: RegraComissao | null;
  comissao_valor: string | null;
}

export interface Eu extends Usuario {
  permissoes: Permissao[];
  dados_demo: boolean;
}

export interface PessoaRef {
  id: number;
  nome: string;
}

export interface Veiculo {
  id: number;
  tipo: TipoVeiculo;
  marca: string;
  modelo: string;
  descricao: string;
  ano_fabricacao: number | null;
  ano_modelo: number | null;
  cor: string | null;
  km: number | null;
  placa: string | null;
  preco_venda: string | null;
  situacao: Situacao;
  situacao_desde: string;
  dias_na_situacao: number;
  foto_capa: string | null;
  valor_compra: string | null;
  total_custos: string | null;
  custo_total: string | null;
  lucro_previsto: string | null;
}

export interface Custo {
  id: number;
  tipo: TipoCusto;
  descricao: string;
  valor: string;
  data: string;
}

export interface Foto {
  id: number;
  url: string;
  miniatura_url: string;
}

export interface VeiculoDetalhe extends Veiculo {
  chassi: string | null;
  renavam: string | null;
  data_compra: string | null;
  observacoes: string | null;
  fotos: Foto[];
  custos: Custo[] | null;
  venda: {
    id: number;
    data_venda: string;
    valor: string;
    forma: FormaPagamento;
    cliente: PessoaRef;
    vendedor: PessoaRef;
    lucro: string | null;
  } | null;
}

export interface Cliente {
  id: number;
  nome: string;
  cpf_cnpj: string | null;
  telefone: string | null;
  email: string | null;
  endereco: string | null;
}

export interface ComissaoResumo {
  id: number;
  valor: string;
  status: StatusComissao;
  regra: RegraComissao;
  regra_valor: string;
}

export interface Venda {
  id: number;
  data_venda: string;
  valor: string;
  forma: FormaPagamento;
  status: "ativa" | "cancelada";
  veiculo: { id: number; descricao: string; tipo: TipoVeiculo; placa: string | null };
  cliente: Cliente;
  vendedor: PessoaRef;
  banco: string | null;
  entrada: string | null;
  numero_parcelas: number | null;
  valor_parcela: string | null;
  primeiro_vencimento: string | null;
  observacoes: string | null;
  motivo_cancelamento: string | null;
  cancelada_em: string | null;
  valor_compra: string | null;
  total_custos: string | null;
  lucro: string | null;
  comissao: ComissaoResumo | null;
}

export interface Comissao extends ComissaoResumo {
  paga_em: string | null;
  vendedor: PessoaRef;
  venda_id: number;
  data_venda: string;
  valor_venda: string;
  veiculo: string;
}

export interface ComissaoPorVendedor {
  vendedor: PessoaRef;
  vendas: number;
  total: string;
  pago: string;
  pendente: string;
}

export interface RelatorioComissoes {
  mes: string;
  itens: Comissao[];
  por_vendedor: ComissaoPorVendedor[];
  total: string;
  pendente: string;
}

export interface Aportes {
  itens: { id: number; data: string; valor: string; descricao: string; registrado_por: string | null }[];
  total: string;
}

export interface Evento {
  id: number;
  usuario_id: number | null;
  usuario_nome: string | null;
  acao: string;
  entidade: string;
  entidade_id: number | null;
  veiculo_id: number | null;
  resumo: string | null;
  alteracoes: Record<string, unknown> | null;
  criado_em: string;
}

export interface NumerosPeriodo {
  vendas: number;
  faturamento: string;
  lucro: string;
  ticket_medio: string | null;
}

export interface MesPainel {
  mes: string;
  total: NumerosPeriodo;
  moto: NumerosPeriodo;
  carro: NumerosPeriodo;
}

export interface Painel {
  hoje: string;
  mes_atual: MesPainel;
  meses: MesPainel[];
  estoque: {
    por_situacao: Record<Situacao, number>;
    em_estoque: number;
    capital_investido: string;
    potencial_venda: string;
  };
  parados: { id: number; descricao: string; situacao: Situacao; dias: number }[];
  dias_parado_alerta: number;
  comissoes_mes: ComissaoPorVendedor[];
}

// ---------- Procedência e site público ----------

export type Semaforo = "verde" | "amarelo" | "vermelho";

export interface ItemLaudo {
  chave: string;
  titulo: string;
  situacao: "ok" | "atencao" | "alerta";
  detalhe: string;
}

export interface MarcoHistorico {
  quando: string;
  titulo: string;
  detalhe: string | null;
}

export interface Laudo {
  id: number;
  placa: string;
  semaforo: Semaforo;
  ilustrativo: boolean;
  provedor: string;
  criado_em: string;
  consultado_por: string | null;
  veiculo_id: number | null;
  veiculo_descricao: string | null;
  dados_veiculo: {
    marca_modelo?: string;
    ano_fabricacao?: number | null;
    ano_modelo?: number | null;
    cor?: string | null;
    tipo?: TipoVeiculo;
    municipio?: string;
    uf?: string;
  };
  itens: ItemLaudo[];
  historico: MarcoHistorico[];
}

export interface VeiculoPublico {
  id: number;
  tipo: TipoVeiculo;
  marca: string;
  modelo: string;
  ano_fabricacao: number | null;
  ano_modelo: number | null;
  cor: string | null;
  km: number | null;
  preco: string;
  placa_mascarada: string | null;
  fotos: Foto[];
  dias_na_loja: number;
  semaforo: Semaforo | null;
}

export interface CatalogoPublico {
  veiculos: VeiculoPublico[];
  ilustrativo: boolean;
}

export interface ProcedenciaPublica {
  placa: string;
  veiculo: VeiculoPublico;
  semaforo: Semaforo | null;
  consultado_em: string | null;
  ilustrativo: boolean;
  itens: ItemLaudo[];
  historico: MarcoHistorico[];
}
