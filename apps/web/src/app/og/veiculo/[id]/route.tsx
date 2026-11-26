import { imagemVeiculo } from "@/lib/imagemCompartilhar";
import { obterLoja } from "@/lib/loja";
import { carregarCatalogo, carregarVeiculo } from "@/lib/vitrine";

export const dynamic = "force-dynamic";

/**
 * Imagem da prévia do link de um veículo sem foto (og:image), 1200×630: nome, ano, km e preço.
 * Só para veículo à venda; fora da vitrine, 404.
 */
export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^\d{1,9}$/.test(id)) return new Response("Veículo não encontrado.", { status: 404 });
  let veiculo;
  try {
    veiculo = await carregarVeiculo(Number(id));
  } catch {
    return new Response("Vitrine fora do ar.", { status: 503 });
  }
  if (!veiculo) return new Response("Este veículo não está mais à venda.", { status: 404 });
  const catalogo = await carregarCatalogo();
  return imagemVeiculo(veiculo, { cidade: obterLoja().cidade, ilustrativo: catalogo?.ilustrativo ?? false });
}
