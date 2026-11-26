/**
 * Leitura da vitrine no servidor (páginas do site, sitemap, robots e imagens de compartilhamento)
 * e os endereços públicos do site. Com `cache`, a metadata e a página dividem a mesma consulta.
 */
import { headers } from "next/headers";
import { cache } from "react";
import type { CatalogoPublico, VeiculoPublico } from "@/lib/tipos";

export const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** Endereço público configurado (SITE_URL), sem a barra do fim. É o único usado no sitemap. */
export function siteUrl(): string | undefined {
  return process.env.SITE_URL?.trim().replace(/\/+$/, "") || undefined;
}

/**
 * Base para os endereços absolutos das metatags (og:url, og:image). Com SITE_URL, ela; sem,
 * o endereço pelo qual a página foi pedida — é por ele que o WhatsApp ou o Facebook chegaram,
 * então a prévia funciona mesmo antes de a loja configurar o domínio.
 */
export async function urlBase(): Promise<string | undefined> {
  const fixa = siteUrl();
  if (fixa) return fixa;
  const h = await headers();
  const host = (h.get("x-forwarded-host") ?? h.get("host") ?? "").split(",")[0].trim();
  if (!/^[a-z0-9.-]+(:\d{1,5})?$/i.test(host)) return undefined;
  const protocolo = (h.get("x-forwarded-proto") ?? "").split(",")[0].trim();
  return `${protocolo === "https" || protocolo === "http" ? protocolo : "http"}://${host}`;
}

/** Catálogo do que está à venda; `null` quando a API não respondeu. */
export const carregarCatalogo = cache(async (): Promise<CatalogoPublico | null> => {
  try {
    const resposta = await fetch(`${API_URL}/publico/veiculos`, { cache: "no-store" });
    if (resposta.ok) return await resposta.json();
  } catch {
    // API fora do ar: quem chamou decide o que mostrar
  }
  return null;
});

/**
 * O veículo, se ainda estiver à venda. `null` = fora da vitrine (vendido, retirado ou nunca
 * existiu). Erro da API vira exceção: a página mostra o aviso de erro, não um 404.
 */
export const carregarVeiculo = cache(async (id: number): Promise<VeiculoPublico | null> => {
  const resposta = await fetch(`${API_URL}/publico/veiculos/${id}`, { cache: "no-store" });
  if (resposta.status === 404) return null;
  if (!resposta.ok) throw new Error(`A vitrine respondeu ${resposta.status}`);
  return resposta.json();
});

/** O site não deve ser indexado em ambiente de demonstração (veículos e preços ilustrativos). */
export const ROBOTS_DEMONSTRACAO = { index: false, follow: false } as const;
