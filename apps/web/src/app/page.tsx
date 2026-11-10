import type { Metadata } from "next";
import { Site } from "@/components/site/Site";
import { obterLoja } from "@/lib/loja";
import type { CatalogoPublico } from "@/lib/tipos";

// A vitrine é o estoque do sistema: a página é montada a cada visita, nunca fica velha.
export const dynamic = "force-dynamic";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const SITE_URL = process.env.SITE_URL?.replace(/\/$/, "") || undefined;

async function carregarCatalogo(): Promise<CatalogoPublico> {
  try {
    const resposta = await fetch(`${API_URL}/publico/veiculos`, { cache: "no-store" });
    if (resposta.ok) return await resposta.json();
  } catch {
    // API fora do ar: o site abre mesmo assim, com a vitrine vazia e o WhatsApp à mão
  }
  return { veiculos: [], ilustrativo: false };
}

export function generateMetadata(): Metadata {
  const { cidade } = obterLoja();
  const onde = cidade ? `em ${cidade}, Piauí` : "no Piauí";
  const titulo = `RC Motos — loja de motos e carros seminovos ${onde}`;
  const descricao = `Motos e carros seminovos ${onde}, revisados e com laudo de procedência pela placa. Veja a vitrine, confira o laudo e chame a loja no WhatsApp.`;
  return {
    title: { absolute: titulo },
    description: descricao,
    robots: { index: true, follow: true },
    alternates: SITE_URL ? { canonical: SITE_URL } : undefined,
    openGraph: { title: titulo, description: descricao, locale: "pt_BR", type: "website", url: SITE_URL },
  };
}

export default async function Pagina() {
  const loja = obterLoja();
  const catalogo = await carregarCatalogo();

  // Dados estruturados para busca local: só o que é verdade e está configurado.
  const dadosEstruturados = {
    "@context": "https://schema.org",
    "@type": "AutoDealer",
    name: "RC Motos",
    url: SITE_URL,
    telephone: loja.whatsapp ? `+55${loja.whatsapp}` : undefined,
    address: {
      "@type": "PostalAddress",
      streetAddress: loja.endereco ?? undefined,
      addressLocality: loja.cidade ?? undefined,
      addressRegion: "PI",
      addressCountry: "BR",
    },
    makesOffer: catalogo.ilustrativo
      ? undefined
      : catalogo.veiculos.map((v) => ({
          "@type": "Offer",
          price: v.preco,
          priceCurrency: "BRL",
          itemCondition: "https://schema.org/UsedCondition",
          itemOffered: {
            "@type": v.tipo === "moto" ? "Motorcycle" : "Car",
            name: `${v.marca} ${v.modelo}`,
            brand: v.marca,
            vehicleModelDate: v.ano_modelo ?? undefined,
            color: v.cor ?? undefined,
            mileageFromOdometer: v.km ?? undefined,
          },
        })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        // JSON gerado no servidor; "<" escapado para não fechar a tag
        dangerouslySetInnerHTML={{ __html: JSON.stringify(dadosEstruturados).replace(/</g, "\\u003c") }}
      />
      <Site veiculos={catalogo.veiculos} ilustrativo={catalogo.ilustrativo} loja={loja} />
    </>
  );
}
