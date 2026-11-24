import Link from "next/link";
import { caminhoVitrine } from "@/components/site/anuncio";
import { Moldura } from "@/components/site/Moldura";
import { Barras } from "@/components/site/pecas";
import { linkWhats, obterLoja } from "@/lib/loja";

/** Anúncio que saiu da vitrine (vendido, retirado) ou endereço que nunca existiu. */
export default function ForaDaVitrine() {
  const loja = obterLoja();
  return (
    <Moldura loja={loja}>
      <section className="claro aviso-pagina" aria-labelledby="titulo-fora">
        <p className="sobretitulo">
          <Barras /> Vitrine
        </p>
        <h1 id="titulo-fora" className="outdoor aviso-pagina__titulo">
          Este veículo não está mais <em>na vitrine.</em>
        </h1>
        <p className="aviso-pagina__texto">
          Ele pode ter sido vendido ou saído do anúncio. A vitrine do site é o estoque da loja: o que está lá, está
          no pátio.
        </p>
        <div className="aviso-pagina__acoes" data-sem-zap>
          <Link className="acao acao--tinta" href={caminhoVitrine()}>
            Ver a vitrine
          </Link>
          <a
            className="acao acao--linha acao--sem-seta"
            href={linkWhats(loja.whatsapp, "Olá! Vim pelo site da RC Motos.")}
            target="_blank"
            rel="noopener"
          >
            Falar no WhatsApp
          </a>
        </div>
      </section>
    </Moldura>
  );
}
