"use client";

import "@/components/site/site.css";

/** A vitrine (API) não respondeu: a página avisa e deixa tentar de novo, sem inventar anúncio. */
export default function Erro({ retry }: { error: unknown; retry: () => void }) {
  return (
    <div className="site">
      <main className="claro aviso-pagina aviso-pagina--sozinho">
        <h1 className="outdoor aviso-pagina__titulo">
          A vitrine não respondeu <em>agora.</em>
        </h1>
        <p className="aviso-pagina__texto">Não deu para carregar este anúncio. Tente de novo em instantes.</p>
        <div className="aviso-pagina__acoes">
          <button type="button" className="acao acao--tinta acao--sem-seta" onClick={() => retry()}>
            Tentar de novo
          </button>
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- recarrega tudo de propósito */}
          <a className="acao acao--linha" href="/#vitrine">
            Ver a vitrine
          </a>
        </div>
      </main>
    </div>
  );
}
