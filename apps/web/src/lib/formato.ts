import type {
  FormaPagamento,
  Perfil,
  RegraComissao,
  Situacao,
  StatusComissao,
  TipoCusto,
  TipoVeiculo,
} from "./tipos";

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const NUMERO = new Intl.NumberFormat("pt-BR");

/** "14900.00" → "R$ 14.900,00" */
export function moeda(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  return BRL.format(Number(valor));
}

/** Versão curta para eixos e cartões apertados: R$ 44,5 mil */
export function moedaCurta(valor: string | number): string {
  const n = Number(valor);
  if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  if (Math.abs(n) >= 1_000) return `R$ ${(n / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  return BRL.format(n);
}

export function numero(valor: number | null | undefined): string {
  return valor === null || valor === undefined ? "—" : NUMERO.format(valor);
}

/** "2026-11-10" → "10/11/2026" (sem passar por fuso horário) */
export function data(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

/** Instante ISO → "10/11/2026 14:32" no horário do Piauí */
export function dataHora(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: "America/Fortaleza",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MESES_LONGOS = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

/** "2026-11" → "nov/26" */
export function mesCurto(mes: string): string {
  const [ano, numeroMes] = mes.split("-");
  return `${MESES[Number(numeroMes) - 1]}/${ano.slice(2)}`;
}

/** "2026-11" → "novembro de 2026" */
export function mesLongo(mes: string): string {
  const [ano, numeroMes] = mes.split("-");
  return `${MESES_LONGOS[Number(numeroMes) - 1]} de ${ano}`;
}

export function mesAtual(): string {
  // Data de hoje no fuso da loja, no formato AAAA-MM
  return new Date().toLocaleDateString("sv-SE", { timeZone: "America/Fortaleza" }).slice(0, 7);
}

export function hojeIso(): string {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "America/Fortaleza" });
}

export function mesVizinho(mes: string, passo: number): string {
  const [ano, numeroMes] = mes.split("-").map(Number);
  const d = new Date(Date.UTC(ano, numeroMes - 1 + passo, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function placa(valor: string | null): string {
  if (!valor) return "sem placa";
  return `${valor.slice(0, 3)}-${valor.slice(3)}`;
}

export function telefone(valor: string | null): string {
  if (!valor) return "—";
  const ddd = valor.slice(0, 2);
  const resto = valor.slice(2);
  return `(${ddd}) ${resto.slice(0, resto.length - 4)}-${resto.slice(-4)}`;
}

export function cpfCnpj(valor: string | null): string {
  if (!valor) return "—";
  if (valor.length === 11) return valor.replace(/(.{3})(.{3})(.{3})(.{2})/, "$1.$2.$3-$4");
  return valor.replace(/(.{2})(.{3})(.{3})(.{4})(.{2})/, "$1.$2.$3/$4-$5");
}

/** Texto digitado ("14.900,50" ou "14900.5") → "14900.50" para a API; null se vazio/inválido. */
export function valorParaApi(texto: string): string | null {
  const limpo = texto.replace(/[R$\s]/g, "");
  if (!limpo) return null;
  const normal = limpo.includes(",") ? limpo.replace(/\./g, "").replace(",", ".") : limpo;
  const n = Number(normal);
  return Number.isFinite(n) ? n.toFixed(2) : null;
}

/** "14900.00" → "14.900,00" para preencher o campo */
export function valorParaCampo(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "";
  return Number(valor).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export const SITUACAO: Record<Situacao, string> = {
  compra: "Compra",
  documentacao: "Documentação",
  preparacao: "Preparação",
  a_venda: "À venda",
  vendido: "Vendido",
  pos_venda: "Pós-venda",
  concluido: "Concluído",
};
export const SITUACOES_ESTOQUE: Situacao[] = ["compra", "documentacao", "preparacao", "a_venda"];
export const SITUACOES_VENDIDO: Situacao[] = ["vendido", "pos_venda", "concluido"];

export const TIPO: Record<TipoVeiculo, string> = { moto: "Moto", carro: "Carro" };
export const TIPO_CUSTO: Record<TipoCusto, string> = {
  manutencao: "Manutenção",
  documentacao: "Documentação",
  debito: "Débito pago (IPVA, multa…)",
  outro: "Outro",
};
export const FORMA: Record<FormaPagamento, string> = {
  a_vista: "À vista",
  financiado_banco: "Financiado (banco)",
  parcelado_loja: "Parcelado na loja",
};
export const PERFIL: Record<Perfil, string> = {
  dono: "Dono",
  gerente: "Gerente",
  financeiro: "Financeiro",
  vendedor: "Vendedor",
};
export const REGRA: Record<RegraComissao, string> = {
  percentual_lucro: "% do lucro",
  percentual_venda: "% do valor da venda",
  valor_fixo: "Valor fixo por venda",
};
export const STATUS_COMISSAO: Record<StatusComissao, string> = {
  pendente: "Pendente",
  paga: "Paga",
  cancelada: "Cancelada",
};

export function regraDescrita(regra: RegraComissao, valor: string): string {
  if (regra === "valor_fixo") return `${moeda(valor)} por venda`;
  const pct = Number(valor).toLocaleString("pt-BR");
  return regra === "percentual_lucro" ? `${pct}% do lucro` : `${pct}% da venda`;
}

export const COR_SITUACAO: Record<Situacao, "azul" | "verde" | "amarelo" | "cinza" | "laranja"> = {
  compra: "cinza",
  documentacao: "laranja",
  preparacao: "amarelo",
  a_venda: "azul",
  vendido: "verde",
  pos_venda: "verde",
  concluido: "cinza",
};
