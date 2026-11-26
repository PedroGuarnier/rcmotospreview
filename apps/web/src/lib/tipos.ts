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
  | "historico.veiculo_ver"
  | "configuracoes.editar";

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
  /** o assistente responde perguntas sobre vendas, estoque e financeiro */
  ia_ligada: boolean;
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
  /** tem laudo de procedência que vale (a mesma regra do site) */
  laudo_valido: boolean;
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
  /** imposto estimado se vender pelo preço anunciado (só com custos.ver) */
  imposto_previsto: string | null;
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
    imposto: string | null;
    lucro_liquido: string | null;
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
  imposto_aliquota: string | null;
  imposto: string | null;
  lucro_liquido: string | null;
  comissao: ComissaoResumo | null;
}

export interface Configuracao {
  /** % do imposto estimado sobre a margem (venda − compra); "0.00" = não calcula */
  imposto_margem_aliquota: string;
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
  /** estimado, sobre a margem de cada venda */
  imposto: string;
  lucro_liquido: string;
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
    /** chassi no cadastro nacional (só provedor real) */
    chassi?: string;
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
  /** última mudança no anúncio (sitemap e versão da imagem de compartilhamento) */
  atualizado_em: string;
}

/** O que o site conta (POST /publico/eventos): visita à página e clique no WhatsApp, pela origem. */
export type TipoEventoSite = "visualizacao" | "whatsapp_cartao" | "whatsapp_pagina" | "whatsapp_proposta";

export interface NumerosProcura {
  visualizacoes: number;
  cliques: number;
  cliques_cartao: number;
  cliques_pagina: number;
  cliques_proposta: number;
}

export interface ProcuraVeiculo {
  /** tamanho da janela de `recente` */
  dias: number;
  recente: NumerosProcura;
  total: NumerosProcura;
}

export interface VeiculoProcurado {
  id: number;
  descricao: string;
  situacao: Situacao;
  foto_capa: string | null;
  visualizacoes: number;
  cliques: number;
}

export interface MaisProcurados {
  dias: number;
  veiculos: VeiculoProcurado[];
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

// ---------- Assistente (cadastro de veículo por mensagem) ----------

/** O que o assistente já entendeu: os campos do cadastro, todos opcionais. */
export interface RascunhoAssistente {
  tipo: TipoVeiculo | null;
  marca: string | null;
  modelo: string | null;
  ano_fabricacao: number | null;
  ano_modelo: number | null;
  cor: string | null;
  km: number | null;
  placa: string | null;
  chassi: string | null;
  renavam: string | null;
  valor_compra: string | null;
  preco_venda: string | null;
  situacao: Situacao | null;
  observacoes: string | null;
  /** AAAA-MM-DD */
  data_compra: string | null;
}

/** Venda por mensagem: os campos da baixa de venda, todos opcionais até a confirmação. */
export interface VendaRascunhoAssistente {
  veiculo_id: number | null;
  comprador: string | null;
  telefone: string | null;
  cpf_cnpj: string | null;
  valor: string | null;
  forma: FormaPagamento | null;
  banco: string | null;
  entrada: string | null;
  numero_parcelas: number | null;
  valor_parcela: string | null;
  primeiro_vencimento: string | null;
  vendedor_id: number | null;
  data_venda: string | null;
}

export type CampoRemovivelAssistente =
  | "preco_venda"
  | "placa"
  | "chassi"
  | "renavam"
  | "cor"
  | "km"
  | "ano_fabricacao"
  | "ano_modelo"
  | "observacoes"
  | "data_compra";

/** Alteração de um veículo do estoque por mensagem: o que muda e o que é apagado. */
export interface EdicaoRascunhoAssistente {
  veiculo_id: number | null;
  mudancas: RascunhoAssistente;
  remover: CampoRemovivelAssistente[];
}

/** Uma pergunta respondida pela IA, guardada para perguntas de seguimento ("e em setembro?"). */
export interface TrocaAssistente {
  pergunta: string;
  resposta: string;
}

/** Vai e volta a cada mensagem: o servidor não guarda a conversa. */
export interface EstadoAssistente {
  rascunho: RascunhoAssistente;
  /** últimas trocas com a IA (no máximo 6), só texto */
  historico: TrocaAssistente[];
  /** campo que o assistente acabou de perguntar, ou "confirmacao" */
  aguardando:
    | "tipo"
    | "marca"
    | "modelo"
    | "valor_compra"
    | "preco_venda"
    | "placa"
    | "chassi"
    | "confirmacao"
    | "data_compra"
    | "veiculo"
    | "comprador"
    | "valor_venda"
    | "forma"
    | "vendedor"
    | "numero_parcelas"
    | "valor_parcela"
    | "primeiro_vencimento"
    | "data_venda"
    | "mudanca"
    | null;
  /** o que está em andamento: cadastro (padrão), venda ou alteração de um veículo */
  modo: "cadastro" | "venda" | "edicao" | null;
  venda: VendaRascunhoAssistente | null;
  edicao: EdicaoRascunhoAssistente | null;
  /** veículos (ou vendedores) que o assistente listou para a pessoa escolher */
  candidatos: number[];
}

export interface ItemFicha {
  campo: string;
  rotulo: string;
  /** já formatado pelo servidor: "R$ 11.500,00", "18.500 km", "ABC-1D23" */
  valor: string;
  /** lucro previsto e imposto estimado (só com custos.ver) */
  calculado: boolean;
  /** na alteração de um veículo: o valor que está gravado hoje */
  antes: string | null;
}

/** Resposta pronta que a tela mostra como botão (ex.: um dos veículos listados). */
export interface OpcaoAssistente {
  rotulo: string;
  mensagem: string;
}

export interface VendaRegistradaAssistente {
  id: number;
  veiculo_id: number;
  descricao: string;
  comprador: string;
  valor: string;
}

export interface CampoAssistente {
  campo: string;
  rotulo: string;
}

export interface VeiculoCriadoAssistente {
  id: number;
  descricao: string;
  placa: string | null;
}

/** Veículo que já usa a placa ou o chassi do rascunho. */
export interface DuplicadoAssistente {
  id: number;
  descricao: string;
  campo: "placa" | "chassi";
}

export interface RespostaAssistente {
  /** texto simples, com quebras de linha */
  resposta: string;
  estado: EstadoAssistente;
  ficha: ItemFicha[];
  /** obrigatórios que faltam */
  faltando: CampoAssistente[];
  /** opcionais importantes que faltam */
  sugeridos: CampoAssistente[];
  /** obrigatórios preenchidos e válidos */
  pronto: boolean;
  acao: "nenhuma" | "confirmar" | "cancelado" | "criado" | "atualizado" | "registrado";
  /** quando acao === "criado" ou "atualizado" */
  veiculo: VeiculoCriadoAssistente | null;
  duplicado: DuplicadoAssistente | null;
  /** suposições feitas ("Considerei 2022 como ano de fabricação e do modelo.") */
  avisos: string[];
  /** "ia": resposta de pergunta sobre o negócio */
  origem: "regras" | "ia";
  /** quando acao === "registrado" */
  venda: VendaRegistradaAssistente | null;
  opcoes: OpcaoAssistente[];
}
