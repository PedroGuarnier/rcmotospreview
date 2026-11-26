import type { Metadata } from "next";
import { notFound } from "next/navigation";
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
import type { ProcedenciaPublica } from "@/lib/tipos";
import { API_URL, ROBOTS_DEMONSTRACAO, carregarCatalogo, carregarVeiculo, siteUrl, urlBase } from "@/lib/vitrine";

// O anúncio é o estoque do sistema: a página é montada a cada visita, nunca fica velha.
export const dynamic = "force-dynamic";

const OUTROS = 3;

type Parametros = { params: Promise<{ slug: string }> };

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
  let veiculo = null;
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
  const [base, catalogo] = await Promise.all([urlBase(), carregarCatalogo()]);
  const titulo = `${nomeComAno(veiculo)} — RC Motos${cidade ? `, ${cidade}` : ""}`;
  const detalhes = [
    nomeVeiculo(veiculo),
    anoVeiculo(veiculo),
    veiculo.km !== null ? `${numero(veiculo.km)} km` : null,
    veiculo.cor?.toLowerCase(),
  ].filter(Boolean);
  // só fala das fotos e do laudo que o anúncio tem
  const ver = [veiculo.fotos.length > 0 && "as fotos", veiculo.semaforo && "o laudo de procedência"].filter(Boolean);
  const convite = ver.length
    ? `Veja ${ver.join(" e ")} e chame a loja no WhatsApp.`
    : "Chame a loja no WhatsApp.";
  const descricao = `${detalhes.join(", ")}, por R$ ${precoVeiculo(veiculo.preco)} na RC Motos${
    cidade ? ` em ${cidade}, Piauí` : ""
  }. ${convite}`;
  const canonico = siteUrl();
  const capa = veiculo.fotos[0];
  // com foto, a prévia do link é a foto de capa; sem foto, um pôster com nome, ano, km e preço
  const imagens = !base
    ? undefined
    : capa
      ? [{ url: `${base}${capa.url}`, alt: nomeComAno(veiculo) }]
      : [
          {
            url: `${base}/og/veiculo/${veiculo.id}?v=${encodeURIComponent(veiculo.atualizado_em)}`,
            width: 1200,
            height: 630,
            type: "image/png",
            alt: nomeComAno(veiculo),
          },
        ];

  return {
    title: { absolute: titulo },
    description: descricao,
    robots: catalogo?.ilustrativo ? ROBOTS_DEMONSTRACAO : { index: true, follow: true },
    alternates: canonico ? { canonical: `${canonico}${caminhoVeiculo(veiculo)}` } : undefined,
    openGraph: {
      title: titulo,
      description: descricao,
      locale: "pt_BR",
      type: "website",
      siteName: "RC Motos",
      url: base ? `${base}${caminhoVeiculo(veiculo)}` : undefined,
      images: imagens,
    },
    twitter: { card: "summary_large_image", title: titulo, description: descricao, images: imagens },
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
    carregarCatalogo(),
  ]);
  const SITE_URL = siteUrl();
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
