"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { moeda } from "@/lib/formato";
import { type Loja, linkWhats } from "@/lib/loja";
import type { VeiculoPublico } from "@/lib/tipos";
import { Pagamento } from "./Pagamento";
import { type ControleProcedencia, Procedencia } from "./Procedencia";
import { Vitrine } from "./Vitrine";
import "./site.css";

const SECOES = [
  { href: "#vitrine", rotulo: "Vitrine" },
  { href: "#procedencia", rotulo: "Procedência" },
  { href: "#pagamento", rotulo: "Como pagar" },
  { href: "#loja", rotulo: "A loja" },
];

function Barras() {
  return (
    <span className="barras" aria-hidden>
      <i />
      <i />
      <i />
    </span>
  );
}

function IconeZap() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5.1-1.3A10 10 0 1 0 12 2Zm0 1.8a8.2 8.2 0 1 1-4.2 15.25l-.3-.18-3 .77.8-2.9-.2-.3A8.2 8.2 0 0 1 12 3.8Zm-3.1 3.9c-.2 0-.5.07-.75.35-.26.28-1 .97-1 2.37 0 1.4 1 2.75 1.16 2.94.14.19 2 3.05 4.84 4.27 2.36 1.01 2.84.81 3.35.76.51-.05 1.65-.67 1.88-1.32.23-.65.23-1.2.16-1.32-.07-.12-.26-.19-.54-.33-.28-.14-1.65-.81-1.9-.9-.26-.1-.44-.14-.63.14-.19.28-.72.9-.89 1.09-.16.19-.33.21-.6.07-.28-.14-1.19-.44-2.26-1.4-.84-.74-1.4-1.66-1.56-1.94-.16-.28-.02-.43.12-.57.13-.13.28-.33.42-.49.14-.16.19-.28.28-.47.09-.19.05-.35-.02-.49-.07-.14-.63-1.51-.86-2.07-.23-.54-.46-.47-.63-.48l-.54-.01Z" />
    </svg>
  );
}

export function Site({
  veiculos,
  ilustrativo,
  loja,
}: {
  veiculos: VeiculoPublico[];
  ilustrativo: boolean;
  loja: Loja;
}) {
  const raiz = useRef<HTMLDivElement>(null);
  const [solido, setSolido] = useState(false);
  const [gaveta, setGaveta] = useState(false);
  const procedencia = useRef<ControleProcedencia>(null);
  const [zapOculto, setZapOculto] = useState(true);

  const linkLoja = linkWhats(loja.whatsapp, "Olá! Vim pelo site da RC Motos.");
  const linkVeiculo = useCallback(
    (v: VeiculoPublico) =>
      linkWhats(
        loja.whatsapp,
        `Olá! Vi no site ${v.tipo === "moto" ? "a" : "o"} ${v.marca} ${v.modelo}${v.ano_modelo ? ` ${v.ano_modelo}` : ""} por ${moeda(v.preco)} e quero saber mais.`,
      ),
    [loja.whatsapp],
  );

  // revelação ao rolar + cabeçalho sólido depois da primeira dobra
  useEffect(() => {
    const el = raiz.current;
    if (!el) return;
    el.dataset.js = "";
    const observador = new IntersectionObserver(
      (entradas) => {
        for (const entrada of entradas) {
          if (entrada.isIntersecting) {
            (entrada.target as HTMLElement).dataset.visivel = "";
            observador.unobserve(entrada.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    el.querySelectorAll("[data-revelar]").forEach((alvo) => observador.observe(alvo));
    const rolar = () => setSolido(window.scrollY > 24);
    rolar();
    window.addEventListener("scroll", rolar, { passive: true });

    // o botão flutuante some onde já existe uma ação de WhatsApp na tela (e no rodapé)
    const comZap = new Set<Element>();
    const vigia = new IntersectionObserver((entradas) => {
      for (const entrada of entradas) {
        if (entrada.isIntersecting) comZap.add(entrada.target);
        else comZap.delete(entrada.target);
      }
      setZapOculto(comZap.size > 0);
    });
    el.querySelectorAll("[data-sem-zap]").forEach((alvo) => vigia.observe(alvo));
    return () => {
      observador.disconnect();
      vigia.disconnect();
      window.removeEventListener("scroll", rolar);
    };
  }, [veiculos.length]);

  // menu do celular: Esc fecha e a página não rola por baixo
  useEffect(() => {
    if (!gaveta) return;
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && setGaveta(false);
    document.addEventListener("keydown", tecla);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tecla);
      document.body.style.overflow = "";
    };
  }, [gaveta]);

  function verLaudo(v: VeiculoPublico) {
    procedencia.current?.abrirDoAnuncio(v);
    document.getElementById("procedencia")?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }

  const motos = veiculos.filter((v) => v.tipo === "moto").length;
  const carros = veiculos.length - motos;
  const local = loja.cidade ? `${loja.cidade}, Piauí` : "Piauí";

  return (
    <div ref={raiz} className="site">
      <a
        href="#vitrine"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[80] focus:rounded focus:bg-white focus:px-4 focus:py-3 focus:font-bold focus:text-[#0a0940]"
      >
        Pular para a vitrine
      </a>

      <header className="topo" data-solido={solido}>
        <a href="#topo" className="topo__marca" aria-label="RC Motos — início">
          <Image src="/logo.png" alt="" width={44} height={44} priority />
          <span>
            RC <em>Motos</em>
          </span>
        </a>
        <nav className="topo__nav" aria-label="Seções do site">
          {SECOES.map((s) => (
            <a key={s.href} href={s.href}>
              {s.rotulo}
            </a>
          ))}
          <a className="acao acao--sem-seta" href={linkLoja} target="_blank" rel="noopener">
            WhatsApp
          </a>
        </nav>
        <button type="button" className="topo__menu" aria-expanded={gaveta} aria-controls="gaveta" onClick={() => setGaveta(true)}>
          Menu <Barras />
        </button>
      </header>

      {gaveta && (
        <div id="gaveta" className="gaveta" role="dialog" aria-modal="true" aria-label="Menu">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="topo__marca">RC Motos</span>
            <button type="button" className="botao-redondo" onClick={() => setGaveta(false)} aria-label="Fechar menu" autoFocus>
              ✕
            </button>
          </div>
          <nav className="gaveta__links" aria-label="Seções do site">
            {SECOES.map((s, i) => (
              <a key={s.href} href={s.href} onClick={() => setGaveta(false)} style={{ "--i": i } as React.CSSProperties}>
                <span>0{i + 1}</span>
                {s.rotulo}
              </a>
            ))}
          </nav>
          <a className="acao acao--tinta" href={linkLoja} target="_blank" rel="noopener">
            Chamar no WhatsApp
          </a>
        </div>
      )}

      <main>
        {/* 1. O farol */}
        <section id="topo" className="farol" aria-labelledby="titulo-site" data-sem-zap>
          <div className="farol__disco" aria-hidden>
            <svg className="farol__anel" viewBox="0 0 200 200">
              <defs>
                <path id="anel" d="M100 100m-92 0a92 92 0 1 1 184 0a92 92 0 1 1-184 0" />
              </defs>
              <text>
                <textPath href="#anel">
                  DEUS É FIEL · RC MOTOS · MOTOS E CARROS · PIAUÍ · DEUS É FIEL · RC MOTOS · MOTOS E CARROS · PIAUÍ ·
                </textPath>
              </text>
            </svg>
          </div>
          <div className="farol__estrada" aria-hidden>
            <div className="farol__pista" />
          </div>

          <div className="farol__conteudo">
            {/* mesmo truque do título: branco em "diferença", para não sumir sobre o disco */}
            <p className="sobretitulo" style={{ color: "#fff", mixBlendMode: "difference" }}>
              <Barras /> Motos e carros seminovos · {local}
            </p>
            <h1 id="titulo-site" className="outdoor farol__titulo">
              {["Moto boa", "tem passado", "limpo."].map((linha, i) => (
                <span key={linha} style={{ "--i": i } as React.CSSProperties}>
                  {linha}
                </span>
              ))}
            </h1>
            <div className="farol__base">
              <p className="farol__texto">
                Seminovos revisados, com a procedência conferida pela placa. O laudo de cada veículo da loja está
                aqui no site — você vê antes de sair de casa.
              </p>
              <div className="farol__lado">
                <div className="farol__acoes">
                  <a className="acao" href="#vitrine">
                    Ver a vitrine
                  </a>
                  <a className="acao acao--linha" href="#procedencia">
                    Puxar uma placa
                  </a>
                </div>
                {veiculos.length > 0 && (
                  <p className="dado farol__fato">
                    <i aria-hidden />
                    <b>{veiculos.length}</b> na loja agora
                    <span>
                      · {motos} {motos === 1 ? "moto" : "motos"} · {carros} {carros === 1 ? "carro" : "carros"}
                    </span>
                  </p>
                )}
              </div>
            </div>
          </div>
        </section>

        <Vitrine
          veiculos={veiculos}
          ilustrativo={ilustrativo}
          linkVeiculo={linkVeiculo}
          linkLoja={linkLoja}
          aoVerLaudo={verLaudo}
        />

        <Procedencia veiculos={veiculos} controle={procedencia} linkVeiculo={linkVeiculo} linkLoja={linkLoja} />

        <Pagamento veiculos={veiculos} whatsapp={loja.whatsapp} />

        {/* 5. A loja */}
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
                Foto ajuda, laudo ajuda, mas nada substitui dar a partida. Passe na loja, ou chame antes para
                saber se o veículo que você quer ainda está no pátio.
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
      </main>

      {/* 6. O farol se põe */}
      <footer className="poente" data-sem-zap>
        <div className="poente__disco" aria-hidden />
        <p className="outdoor poente__lema">
          Deus é fiel.
        </p>
        <div className="poente__base">
          <p>© {new Date().getFullYear()} RC Motos · {local}</p>
          <nav aria-label="Rodapé">
            {SECOES.map((s) => (
              <a key={s.href} href={s.href}>
                {s.rotulo}
              </a>
            ))}
            <a href="/login">Área da equipe</a>
          </nav>
        </div>
      </footer>

      <a className="zap" href={linkLoja} target="_blank" rel="noopener" data-oculto={zapOculto || gaveta}>
        <IconeZap />
        <span>WhatsApp</span>
      </a>
    </div>
  );
}
