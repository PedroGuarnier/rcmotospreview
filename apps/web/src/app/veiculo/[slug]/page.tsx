import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";
import {
  anoVeiculo,
  caminhoVeiculo,
  idDoSlug,
  nomeComAno,
  nomeVeiculo,
  precoVeiculo,
} from "@/components/site/anuncio";
import { Produto } from "@/components/site/Produto";
import { numero } from "@/lib/formato";
import { obterLoja } from "@/lib/loja";
import type { CatalogoPublico, ProcedenciaPublica, VeiculoPublico } from "@/lib/tipos";

// O anúncio é o estoque do sistema: a página é montada a cada visita, nunca fica velha.
export const dynamic = "force-dynamic";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const SITE_URL = process.env.SITE_URL?.replace(/\/$/, "") || undefined;
const OUTROS = 3;

type Parametros = { params: Promise<{ slug: string }> };

/**
 * O veículo, se ainda estiver à venda. `null` = fora da vitrine (vendido, retirado ou nunca existiu).
 * Com `cache`, a metadata e a página dividem a mesma consulta.
 */
const carregarVeiculo = cache(async (id: number): Promise<VeiculoPublico | null> => {
  const resposta = await fetch(`${API_URL}/publico/veiculos/${id}`, { cache: "no-store" });
  if (resposta.status === 404) return null;
  if (!resposta.ok) throw new Error(`A vitrine respondeu ${resposta.status}`);
  return resposta.json();
});

/** O que complementa a página; se falhar, o anúncio abre sem esse bloco. */
async function carregarExtra<T>(caminho: string): Promise<T | null> {
  try {
    const resposta = await fetch(`${API_URL}${caminho}`, { cache: "no-store" });
    return resposta.ok ? await resposta.json() : null;
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: Parametros): Promise<Metadata> {
  const id = idDoSlug((await params).slug);
  let veiculo: VeiculoPublico | null = null;
  if (id !== null) {
    try {
      veiculo = await carregarVeiculo(id);
    } catch {
      // vitrine fora do ar: a página mostra o aviso de erro, sem título de anúncio
      return { title: { absolute: "RC Motos" }, robots: { index: false, follow: false } };
    }
  }
  if (!veiculo) return {}; // fora da vitrine: vale a metadata de reserva de ../layout.tsx

  const { cidade } = obterLoja();
  const titulo = `${nomeComAno(veiculo)} — RC Motos${cidade ? `, ${cidade}` : ""}`;
  const detalhes = [
    nomeVeiculo(veiculo),
    anoVeiculo(veiculo),
    veiculo.km !== null ? `${numero(veiculo.km)} km` : null,
    veiculo.cor?.toLowerCase(),
  ].filter(Boolean);
  const descricao = `${detalhes.join(", ")}, por R$ ${precoVeiculo(veiculo.preco)} na RC Motos${
    cidade ? ` em ${cidade}, Piauí` : ""
  }. Veja as fotos e o laudo de procedência e chame a loja no WhatsApp.`;
  const endereco = SITE_URL ? `${SITE_URL}${caminhoVeiculo(veiculo)}` : undefined;
  const capa = SITE_URL && veiculo.fotos[0] ? `${SITE_URL}${veiculo.fotos[0].url}` : undefined;

  return {
    title: { absolute: titulo },
    description: descricao,
    robots: { index: true, follow: true },
    alternates: endereco ? { canonical: endereco } : undefined,
    openGraph: {
      title: titulo,
      description: descricao,
      locale: "pt_BR",
      type: "website",
      url: endereco,
      images: capa ? [{ url: capa, alt: nomeComAno(veiculo) }] : undefined,
    },
  };
}

export default async function Pagina({ params }: Parametros) {
  const id = idDoSlug((await params).slug);
  if (id === null) notFound();
  const veiculo = await carregarVeiculo(id);
  if (!veiculo) notFound();

  const loja = obterLoja();
  const [laudo, catalogo] = await Promise.all([
    carregarExtra<ProcedenciaPublica>(`/publico/veiculos/${id}/procedencia`),
    carregarExtra<CatalogoPublico>("/publico/veiculos"),
  ]);
  // outros anúncios: primeiro os do mesmo tipo, sempre do mais novo para o mais antigo
  const demais = (catalogo?.veiculos ?? []).filter((v) => v.id !== veiculo.id);
  const outros = [
    ...demais.filter((v) => v.tipo === veiculo.tipo),
    ...demais.filter((v) => v.tipo !== veiculo.tipo),
  ].slice(0, OUTROS);
  const ilustrativo = catalogo?.ilustrativo ?? false;
  const endereco = SITE_URL ? `${SITE_URL}${caminhoVeiculo(veiculo)}` : undefined;

  // Dados estruturados do anúncio: só o que está no cadastro, e nunca com dados ilustrativos.
  const dadosEstruturados = !catalogo || ilustrativo
    ? null
    : {
        "@context": "https://schema.org",
        "@type": veiculo.tipo === "moto" ? "Motorcycle" : "Car",
        name: nomeComAno(veiculo),
        brand: { "@type": "Brand", name: veiculo.marca },
        model: veiculo.modelo,
        vehicleModelDate: veiculo.ano_modelo ?? undefined,
        productionDate: veiculo.ano_fabricacao ?? undefined,
        color: veiculo.cor ?? undefined,
        mileageFromOdometer:
          veiculo.km === null ? undefined : { "@type": "QuantitativeValue", value: veiculo.km, unitCode: "KMT" },
        itemCondition: "https://schema.org/UsedCondition",
        image: SITE_URL && veiculo.fotos.length > 0 ? veiculo.fotos.map((f) => `${SITE_URL}${f.url}`) : undefined,
        url: endereco,
        offers: {
          "@type": "Offer",
          price: veiculo.preco,
          priceCurrency: "BRL",
          availability: "https://schema.org/InStock",
          itemCondition: "https://schema.org/UsedCondition",
          url: endereco,
          seller: {
            "@type": "AutoDealer",
            name: "RC Motos",
            url: SITE_URL,
            telephone: loja.whatsapp ? `+55${loja.whatsapp}` : undefined,
          },
        },
      };

  return (
    <>
      {dadosEstruturados && (
        <script
          type="application/ld+json"
          // JSON gerado no servidor; "<" escapado para não fechar a tag
          dangerouslySetInnerHTML={{ __html: JSON.stringify(dadosEstruturados).replace(/</g, "\\u003c") }}
        />
      )}
      <Produto veiculo={veiculo} laudo={laudo} outros={outros} ilustrativo={ilustrativo} loja={loja} pagina={endereco} />
    </>
  );
}
