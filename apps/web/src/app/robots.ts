import type { MetadataRoute } from "next";
import { carregarCatalogo, siteUrl } from "@/lib/vitrine";

// Lido a cada pedido: depende do catálogo (demonstração ou não) e do SITE_URL do ambiente.
export const dynamic = "force-dynamic";

/** Área da equipe e o repasse para a API: fora da busca (as páginas também são noindex). */
const AREA_DA_EQUIPE = [
  "/login",
  "/api/",
  "/painel",
  "/estoque",
  "/vendas",
  "/comissoes",
  "/aportes",
  "/historico",
  "/usuarios",
  "/conta",
  "/procedencia",
  "/configuracoes",
  "/assistente",
];

/**
 * Buscadores: o site e as fotos dos anúncios (/arquivos, já públicas e usadas na prévia do link)
 * podem ser lidos; a área da equipe, não. Em demonstração, nada é indexado.
 * Sem SITE_URL o site continua liberado, só não aponta o sitemap (que fica vazio).
 */
export default async function robots(): Promise<MetadataRoute.Robots> {
  const catalogo = await carregarCatalogo();
  if (catalogo?.ilustrativo) {
    return { rules: { userAgent: "*", disallow: "/" } };
  }
  const base = siteUrl();
  return {
    rules: { userAgent: "*", allow: "/", disallow: AREA_DA_EQUIPE },
    sitemap: base ? `${base}/sitemap.xml` : undefined,
  };
}
