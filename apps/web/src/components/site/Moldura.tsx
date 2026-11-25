"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { type Loja, linkWhats } from "@/lib/loja";
import { useFocoPreso } from "./foco";
import { Barras, IconeZap } from "./pecas";
import "./site.css";

const SECOES = [
  { id: "vitrine", rotulo: "Vitrine" },
  { id: "pagamento", rotulo: "Como pagar" },
  { id: "procedencia", rotulo: "Procedência" },
  { id: "loja", rotulo: "A loja" },
];

/** Link para uma seção: âncora na página inicial; nas outras páginas, volta para ela. */
function Secao({
  id,
  inicio,
  children,
  ...resto
}: { id: string; inicio: boolean; children: React.ReactNode } & Omit<React.ComponentProps<"a">, "href">) {
  return inicio ? (
    <a href={`#${id}`} {...resto}>
      {children}
    </a>
  ) : (
    <Link href={`/#${id}`} {...resto}>
      {children}
    </Link>
  );
}

/** Menu do celular, em tela cheia: Esc fecha, o Tab não sai dele e a página não rola por baixo. */
function Gaveta({ inicio, linkLoja, aoFechar }: { inicio: boolean; linkLoja: string; aoFechar: () => void }) {
  const caixa = useRef<HTMLDivElement>(null);
  useFocoPreso(caixa);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    document.addEventListener("keydown", tecla);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tecla);
      document.body.style.overflow = "";
    };
  }, [aoFechar]);

  return (
    <div ref={caixa} id="gaveta" className="gaveta" role="dialog" aria-modal="true" aria-label="Menu">
      <div className="gaveta__topo">
        <span className="topo__marca">RC Motos</span>
        <button type="button" className="botao-redondo" onClick={aoFechar} aria-label="Fechar menu">
          ✕
        </button>
      </div>
      <nav className="gaveta__links" aria-label="Seções do site">
        {SECOES.map((s, i) => (
          <Secao key={s.id} id={s.id} inicio={inicio} onClick={aoFechar} style={{ "--i": i } as React.CSSProperties}>
            <span>0{i + 1}</span>
            {s.rotulo}
          </Secao>
        ))}
      </nav>
      <a className="acao acao--tinta" href={linkLoja} target="_blank" rel="noopener">
        Chamar no WhatsApp
      </a>
    </div>
  );
}

/**
 * O que toda página do site tem em volta: cabeçalho fixo, menu do celular, rodapé e o botão
 * flutuante do WhatsApp.
 */
export function Moldura({
  loja,
  inicio = false,
  linkZap,
  children,
}: {
  loja: Loja;
  /** página inicial: cabeçalho transparente no topo e links de seção como âncoras */
  inicio?: boolean;
  /** conversa do botão flutuante (na página de um veículo, já fala dele) */
  linkZap?: string;
  children: React.ReactNode;
}) {
  const raiz = useRef<HTMLDivElement>(null);
  const [rolou, setRolou] = useState(false);
  const [gaveta, setGaveta] = useState(false);
  const [zapOculto, setZapOculto] = useState(true);
  const fecharGaveta = useCallback(() => setGaveta(false), []);

  const linkLoja = linkWhats(loja.whatsapp, "Olá! Vim pelo site da RC Motos.");
  const local = loja.cidade ? `${loja.cidade}, Piauí` : "Piauí";

  // revelação ao rolar + cabeçalho sólido depois do topo
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
    const rolar = () => setRolou(window.scrollY > 24);
    rolar();
    window.addEventListener("scroll", rolar, { passive: true });

    // O botão flutuante some onde já existe uma ação de WhatsApp na tela (e no rodapé). E só
    // aparece depois que a pessoa passou pela primeira delas: antes, ele só cobriria conteúdo.
    const comZap = new Set<Element>();
    const alvosZap = el.querySelectorAll("[data-sem-zap]");
    let antesDaPrimeira = false;
    const vigia = new IntersectionObserver((entradas) => {
      for (const entrada of entradas) {
        if (entrada.isIntersecting) comZap.add(entrada.target);
        else comZap.delete(entrada.target);
        if (entrada.target === alvosZap[0]) {
          antesDaPrimeira = !entrada.isIntersecting && entrada.boundingClientRect.top > 0;
        }
      }
      setZapOculto(comZap.size > 0 || antesDaPrimeira);
    });
    alvosZap.forEach((alvo) => vigia.observe(alvo));

    // Âncoras da própria página deslizam até a seção. Fica aqui, e não em `scroll-behavior` no
    // <html>, para a troca de página e o "voltar" do navegador continuarem instantâneos.
    const ancorar = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = (e.target as Element).closest<HTMLAnchorElement>('a[href^="#"]');
      const id = link?.getAttribute("href")?.slice(1);
      const alvo = id ? document.getElementById(id) : null;
      if (!id || !alvo) return;
      e.preventDefault();
      const parado = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      alvo.scrollIntoView({ behavior: parado ? "auto" : "smooth" });
      // o foco acompanha, para teclado e leitor de tela seguirem dali
      if (!alvo.hasAttribute("tabindex")) alvo.setAttribute("tabindex", "-1");
      alvo.focus({ preventScroll: true });
    };
    el.addEventListener("click", ancorar);

    // Chegou por um link com âncora (/#vitrine): a rolagem já aconteceu. Sem a âncora no
    // endereço, o "voltar" devolve a página onde a pessoa estava, e não o topo da seção.
    const semAncora = window.setTimeout(() => {
      const { hash, pathname, search } = window.location;
      if (hash.length > 1 && document.getElementById(decodeURIComponent(hash.slice(1)))) {
        window.history.replaceState(null, "", pathname + search);
      }
    }, 300);
    return () => {
      observador.disconnect();
      vigia.disconnect();
      window.removeEventListener("scroll", rolar);
      el.removeEventListener("click", ancorar);
      window.clearTimeout(semAncora);
    };
  }, []);

  const marca = (
    <>
      <Image src="/logo.png" alt="" width={44} height={44} loading="eager" />
      <span>
        RC <em>Motos</em>
      </span>
    </>
  );

  return (
    <div ref={raiz} className="site">
      <a href="#conteudo" className="pulo">
        Pular para o conteúdo
      </a>

      <header className="topo" data-solido={!inicio || rolou}>
        {inicio ? (
          <a href="#topo" className="topo__marca" aria-label="RC Motos — início">
            {marca}
          </a>
        ) : (
          <Link href="/" className="topo__marca" aria-label="RC Motos — início">
            {marca}
          </Link>
        )}
        <nav className="topo__nav" aria-label="Seções do site">
          {SECOES.map((s) => (
            <Secao key={s.id} id={s.id} inicio={inicio}>
              {s.rotulo}
            </Secao>
          ))}
          <a className="acao acao--sem-seta" href={linkLoja} target="_blank" rel="noopener">
            WhatsApp
          </a>
        </nav>
        <button
          type="button"
          className="topo__menu"
          aria-expanded={gaveta}
          aria-controls="gaveta"
          onClick={() => setGaveta(true)}
        >
          Menu <Barras />
        </button>
      </header>

      {gaveta && <Gaveta inicio={inicio} linkLoja={linkLoja} aoFechar={fecharGaveta} />}

      <main id="conteudo" tabIndex={-1}>
        {children}
      </main>

      <footer className="rodape" data-sem-zap>
        <div className="rodape__lema">
          <Barras />
          <p className="outdoor">Deus é fiel.</p>
        </div>
        <div className="rodape__base">
          <p>
            © {new Date().getFullYear()} RC Motos · {local}
          </p>
          <nav aria-label="Rodapé">
            {SECOES.map((s) => (
              <Secao key={s.id} id={s.id} inicio={inicio}>
                {s.rotulo}
              </Secao>
            ))}
            <a href="/login">Área da equipe</a>
          </nav>
        </div>
      </footer>

      <a
        className="zap"
        href={linkZap ?? linkLoja}
        target="_blank"
        rel="noopener"
        data-oculto={zapOculto || gaveta}
      >
        <IconeZap />
        <span className="so-leitor">Chamar a loja no WhatsApp</span>
      </a>
    </div>
  );
}
