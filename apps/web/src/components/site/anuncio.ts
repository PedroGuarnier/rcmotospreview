/** O que o site diz de cada veículo: nome, endereço da página, ficha, preço e a mensagem do WhatsApp. */
import { moeda, numero } from "@/lib/formato";
import { linkWhats } from "@/lib/loja";
import type { Semaforo, TipoVeiculo, VeiculoPublico } from "@/lib/tipos";

export const ROTULO_LAUDO: Record<Semaforo, string> = {
  verde: "Laudo: nada consta",
  amarelo: "Laudo: ponto de atenção",
  vermelho: "Laudo: restrição",
};

export const ROTULO_TIPO: Record<TipoVeiculo, string> = { moto: "Moto", carro: "Carro" };

/** "Quero essa" (a moto) / "Quero esse" (o carro) */
export const queroEsse = (tipo: TipoVeiculo) => (tipo === "moto" ? "Quero essa" : "Quero esse");

/** minúsculas e sem acento, para busca e para o endereço da página */
export function semAcento(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

export const nomeVeiculo = (v: VeiculoPublico) => `${v.marca} ${v.modelo}`;

export function nomeComAno(v: VeiculoPublico): string {
  return v.ano_modelo ? `${nomeVeiculo(v)} ${v.ano_modelo}` : nomeVeiculo(v);
}

/** "12-honda-cg-160-fan-2022": só o número inicial identifica; o resto é para gente (e busca) ler. */
export function slugVeiculo(v: VeiculoPublico): string {
  const legivel = semAcento(nomeComAno(v))
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return legivel ? `${v.id}-${legivel}` : String(v.id);
}

export const caminhoVeiculo = (v: VeiculoPublico) => `/veiculo/${slugVeiculo(v)}`;

export function idDoSlug(slug: string): number | null {
  const achado = /^(\d{1,9})(?:-|$)/.exec(slug);
  return achado ? Number(achado[1]) : null;
}

/** "2021/2022" quando fabricação e modelo diferem; senão o ano que houver */
export function anoVeiculo(v: VeiculoPublico): string | null {
  if (v.ano_modelo && v.ano_fabricacao && v.ano_fabricacao !== v.ano_modelo) {
    return `${v.ano_fabricacao}/${v.ano_modelo}`;
  }
  const ano = v.ano_modelo ?? v.ano_fabricacao;
  return ano ? String(ano) : null;
}

/** Linha de ficha dos cartões: só o que estiver preenchido. */
export function fichaVeiculo(v: VeiculoPublico): string[] {
  const itens: string[] = [];
  const ano = anoVeiculo(v);
  if (ano) itens.push(ano);
  if (v.km !== null) itens.push(`${numero(v.km)} km`);
  if (v.cor) itens.push(v.cor);
  return itens;
}

/** "26900.00" → "26.900"; os centavos só aparecem quando existem ("1.500,50") */
export function precoVeiculo(valor: string): string {
  const n = Number(valor);
  const casas = Number.isInteger(n) ? 0 : 2;
  return n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

export const chegouEstaSemana = (v: VeiculoPublico) => v.dias_na_loja <= 7;

/** Conversa já começada no WhatsApp; com `pagina`, o link do anúncio vai junto. */
export function linkVeiculo(whatsapp: string | null, v: VeiculoPublico, pagina?: string): string {
  const artigo = v.tipo === "moto" ? "a" : "o";
  const mensagem = `Olá! Vi no site ${artigo} ${nomeComAno(v)} por ${moeda(v.preco)} e quero saber mais.`;
  return linkWhats(whatsapp, pagina ? `${mensagem}\n${pagina}` : mensagem);
}

/** Filtros da vitrine, que também viajam no endereço (/?tipo=moto#vitrine). */
export type Ordem = "recentes" | "menor" | "maior";
export const ORDENS: { valor: Ordem; rotulo: string }[] = [
  { valor: "recentes", rotulo: "Mais recentes" },
  { valor: "menor", rotulo: "Menor preço" },
  { valor: "maior", rotulo: "Maior preço" },
];

export const caminhoVitrine = (tipo?: TipoVeiculo) => (tipo ? `/?tipo=${tipo}#vitrine` : "/#vitrine");
