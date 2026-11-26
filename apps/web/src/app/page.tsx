import type { Metadata } from "next";
import { Site } from "@/components/site/Site";
import { obterLoja } from "@/lib/loja";
import { ROBOTS_DEMONSTRACAO, carregarCatalogo, siteUrl, urlBase } from "@/lib/vitrine";

// A vitrine é o estoque do sistema: a página é montada a cada visita, nunca fica velha.
export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const { cidade } = obterLoja();
  const onde = cidade ? `em ${cidade}, Piauí` : "no Piauí";
  const titulo = `RC Motos — loja de motos e carros seminovos ${onde}`;
  const descricao = `Motos e carros seminovos ${onde}: veja a vitrine com fotos e preço, consulte o laudo de procedência pela placa e chame a loja no WhatsApp.`;
  const [base, catalogo] = await Promise.all([urlBase(), carregarCatalogo()]);
  const canonico = siteUrl();
  const imagens = base
    ? [
        {
          url: `${base}/og/inicio`,
          width: 1200,
          height: 630,
          type: "image/png",
          alt: `RC Motos — motos e carros seminovos ${onde}`,
        },
      ]
    : undefined;
  return {
    title: { absolute: titulo },
    description: descricao,
    // em demonstração (veículos e preços ilustrativos) nada é indexado
    robots: catalogo?.ilustrativo ? ROBOTS_DEMONSTRACAO : { index: true, follow: true },
    alternates: canonico ? { canonical: `${canonico}/` } : undefined,
    openGraph: {
      title: titulo,
      description: descricao,
      locale: "pt_BR",
      type: "website",
      siteName: "RC Motos",
      url: base ? `${base}/` : undefined,
      images: imagens,
    },
    twitter: { card: "summary_large_image", title: titulo, description: descricao, images: imagens },
  };
}

export default async function Pagina() {
  const loja = obterLoja();
  // API fora do ar: o site abre mesmo assim, com a vitrine vazia e o WhatsApp à mão
  const catalogo = (await carregarCatalogo()) ?? { veiculos: [], ilustrativo: false };
  const SITE_URL = siteUrl();

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
