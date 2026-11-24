"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { type Loja, linkWhats } from "@/lib/loja";
import type { TipoVeiculo, VeiculoPublico } from "@/lib/tipos";
import { ORDENS } from "./anuncio";
import { Dobra } from "./Dobra";
import { Moldura } from "./Moldura";
import { Pagamento } from "./Pagamento";
import { Barras } from "./pecas";
import { Procedencia } from "./Procedencia";
import { Vitrine } from "./Vitrine";

/**
 * O que pode vir no endereço da página inicial (/?tipo=moto&ordem=menor&busca=cg&veiculo=12):
 * atalhos da primeira dobra, link compartilhado, "Montar proposta" e a volta de um anúncio.
 */
function lerFiltros(consulta: URLSearchParams) {
  const tipo = consulta.get("tipo");
  return {
    tipo: (tipo === "moto" || tipo === "carro" ? tipo : "") as TipoVeiculo | "",
    ordem: ORDENS.find((o) => o.valor === consulta.get("ordem"))?.valor ?? "recentes",
    busca: (consulta.get("busca") ?? "").slice(0, 60),
    /** veículo já escolhido em "Como pagar" */
    veiculo: consulta.get("veiculo") ?? "",
  };
}

/** Página inicial: primeira dobra com destaques → vitrine → como pagar → procedência → a loja. */
export function Site({
  veiculos,
  ilustrativo,
  loja,
}: {
  veiculos: VeiculoPublico[];
  ilustrativo: boolean;
  loja: Loja;
}) {
  // lidos uma vez, ao montar: depois disso quem manda são os controles da vitrine
  const consulta = useSearchParams();
  const [filtros] = useState(() => lerFiltros(consulta));
  const [tipo, setTipo] = useState(filtros.tipo);
  const linkLoja = linkWhats(loja.whatsapp, "Olá! Vim pelo site da RC Motos.");
  const local = loja.cidade ? `${loja.cidade}, Piauí` : "Piauí";

  /** Atalho da primeira dobra: filtra e desce até a vitrine sem recarregar a página. */
  function filtrar(novo: TipoVeiculo, evento: React.MouseEvent<HTMLAnchorElement>) {
    if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.button !== 0) return; // abrir em outra aba
    evento.preventDefault();
    setTipo(novo); // a vitrine põe o filtro no endereço
    const parado = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById("vitrine")?.scrollIntoView({ behavior: parado ? "auto" : "smooth" });
  }

  return (
    <Moldura loja={loja} inicio>
      <Dobra veiculos={veiculos} local={local} linkLoja={linkLoja} aoFiltrar={filtrar} />

      <Vitrine
        veiculos={veiculos}
        ilustrativo={ilustrativo}
        whatsapp={loja.whatsapp}
        linkLoja={linkLoja}
        tipo={tipo}
        aoMudarTipo={setTipo}
        ordemInicial={filtros.ordem}
        buscaInicial={filtros.busca}
      />

      <Pagamento veiculos={veiculos} whatsapp={loja.whatsapp} veiculoInicial={filtros.veiculo} />

      <Procedencia whatsapp={loja.whatsapp} linkLoja={linkLoja} />

      <section id="loja" className="claro endereco" aria-labelledby="titulo-loja">
        <div className="endereco__grade">
          <div>
            <p className="sobretitulo" data-revelar>
              <Barras /> A loja
            </p>
            <h2 id="titulo-loja" className="outdoor endereco__titulo" data-revelar>
              Venha ver <em>de perto.</em>
            </h2>
            <p className="endereco__texto" data-revelar>
              Foto ajuda, laudo ajuda, mas nada substitui dar a partida. Passe na loja, ou chame antes para saber se
              o veículo que você quer ainda está no pátio.
            </p>
            <a className="acao acao--tinta" href={linkLoja} target="_blank" rel="noopener" data-revelar data-sem-zap>
              Chamar no WhatsApp
            </a>
          </div>
          <dl className="contatos" data-revelar>
            {loja.endereco && (
              <div>
                <dt>Endereço</dt>
                <dd>
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`RC Motos ${loja.endereco}`)}`}
                    target="_blank"
                    rel="noopener"
                  >
                    {loja.endereco}
                  </a>
                </dd>
              </div>
            )}
            {loja.horario && (
              <div>
                <dt>Horário</dt>
                <dd>{loja.horario}</dd>
              </div>
            )}
            <div>
              <dt>WhatsApp</dt>
              <dd>
                <a href={linkLoja} target="_blank" rel="noopener">
                  {loja.whatsapp
                    ? `(${loja.whatsapp.slice(0, 2)}) ${loja.whatsapp.slice(2, -4)}-${loja.whatsapp.slice(-4)}`
                    : "Abrir conversa"}
                </a>
              </dd>
            </div>
            {loja.instagram && (
              <div>
                <dt>Instagram</dt>
                <dd>
                  <a href={`https://instagram.com/${loja.instagram}`} target="_blank" rel="noopener">
                    @{loja.instagram}
                  </a>
                </dd>
              </div>
            )}
            <div>
              <dt>Onde</dt>
              <dd>{local}</dd>
            </div>
          </dl>
        </div>
      </section>
    </Moldura>
  );
}
