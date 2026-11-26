import { imagemInicio } from "@/lib/imagemCompartilhar";
import { obterLoja } from "@/lib/loja";

// A cidade vem do ambiente (LOJA_CIDADE), lido a cada pedido.
export const dynamic = "force-dynamic";

/** Imagem da prévia do link da página inicial (og:image), 1200×630. */
export async function GET() {
  return imagemInicio(obterLoja().cidade);
}
