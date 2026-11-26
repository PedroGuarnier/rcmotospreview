import type { MetadataRoute } from "next";
import { caminhoVeiculo } from "@/components/site/anuncio";
import { carregarCatalogo, siteUrl } from "@/lib/vitrine";

// A vitrine é o estoque: o sitemap é montado a cada pedido, com o que está à venda agora.
export const dynamic = "force-dynamic";

/**
 * Início + uma URL por veículo à venda (com a data da última mudança no anúncio).
 *
 * Só com SITE_URL: o sitemap declara os endereços oficiais do site, e o host da requisição pode
 * ser um endereço interno, de teste ou forjado (cabeçalho Host). Sem SITE_URL ele sai vazio,
 * como as páginas, que também só têm endereço canônico com SITE_URL.
 * Em demonstração também sai vazio (e o robots.txt bloqueia tudo).
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  if (!base) return [];
  const catalogo = await carregarCatalogo();
  // API fora do ar: erro (o buscador tenta de novo) em vez de um sitemap sem os anúncios
  if (!catalogo) throw new Error("Não foi possível ler a vitrine para o sitemap.");
  if (catalogo.ilustrativo) return [];

  const veiculos = catalogo.veiculos;
  const ultima = veiculos.map((v) => v.atualizado_em).sort().at(-1);
  return [
    { url: `${base}/`, lastModified: ultima, changeFrequency: "daily", priority: 1 },
    ...veiculos.map((v) => ({
      url: `${base}${caminhoVeiculo(v)}`,
      lastModified: v.atualizado_em,
      changeFrequency: "weekly" as const,
      priority: 0.8,
      images: v.fotos.slice(0, 10).map((f) => `${base}${f.url}`),
    })),
    { url: `${base}/privacidade`, changeFrequency: "yearly", priority: 0.2 },
  ];
}
