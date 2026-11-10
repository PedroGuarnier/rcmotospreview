"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect } from "react";
import useSWR, { useSWRConfig } from "swr";
import { ErroApi, api, buscar } from "@/lib/api";
import { PERFIL } from "@/lib/formato";
import type { Eu, Permissao } from "@/lib/tipos";
import { Carregando } from "./ui";

const Contexto = createContext<Eu | null>(null);

export function useEu(): Eu {
  const eu = useContext(Contexto);
  if (!eu) throw new Error("useEu fora da área logada");
  return eu;
}

export function usePode() {
  const eu = useEu();
  return (permissao: Permissao) => eu.permissoes.includes(permissao);
}

const ICONES = {
  painel: <path d="M4 20V11M10 20V4M16 20v-7M21 20H3" />,
  estoque: (
    <>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
    </>
  ),
  vendas: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.5 3 3 5-6.5" />
    </>
  ),
  comissoes: (
    <>
      <path d="M19 5 5 19" />
      <circle cx="7" cy="7" r="2.5" />
      <circle cx="17" cy="17" r="2.5" />
    </>
  ),
  aportes: <path d="M12 3v12m0 0-4.5-4.5M12 15l4.5-4.5M4 20h16" />,
  equipe: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5M16 4.8a3.5 3.5 0 0 1 0 6.4M18.5 14.9c1.7.8 2.7 2.5 3 5.1" />
    </>
  ),
  historico: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </>
  ),
  conta: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20.5c1-4 4-6 8-6s7 2 8 6" />
    </>
  ),
} as const;

function Icone({ nome }: { nome: keyof typeof ICONES }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ICONES[nome]}
    </svg>
  );
}

interface ItemMenu {
  href: string;
  rotulo: string;
  icone: keyof typeof ICONES;
  permissao?: Permissao;
  /** aparece na barra inferior do celular */
  principal?: boolean;
}

const MENU: ItemMenu[] = [
  { href: "/painel", rotulo: "Painel", icone: "painel", permissao: "painel.ver", principal: true },
  { href: "/estoque", rotulo: "Estoque", icone: "estoque", permissao: "estoque.ver", principal: true },
  { href: "/vendas", rotulo: "Vendas", icone: "vendas", principal: true },
  { href: "/comissoes", rotulo: "Comissões", icone: "comissoes", principal: true },
  { href: "/aportes", rotulo: "Aportes", icone: "aportes", permissao: "aportes.ver" },
  { href: "/usuarios", rotulo: "Equipe", icone: "equipe", permissao: "usuarios.gerir" },
  { href: "/historico", rotulo: "Histórico", icone: "historico", permissao: "historico.ver" },
  { href: "/conta", rotulo: "Minha conta", icone: "conta" },
];

export function paginaInicial(eu: Eu): string {
  return eu.permissoes.includes("painel.ver") ? "/painel" : "/estoque";
}

export function AreaLogada({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const caminho = usePathname();
  const { mutate } = useSWRConfig();
  const { data: eu, error } = useSWR<Eu>("/auth/eu", buscar, {
    shouldRetryOnError: false,
    revalidateOnFocus: true,
  });

  const deslogado = error instanceof ErroApi && error.status === 401;
  useEffect(() => {
    if (deslogado) router.replace("/login");
  }, [deslogado, router]);

  if (error && !deslogado) {
    return (
      <div className="grid min-h-dvh place-items-center p-6 text-center">
        <div>
          <p className="mb-4 text-suave">Não foi possível carregar o sistema.</p>
          <button className="font-semibold text-azul underline" onClick={() => location.reload()}>
            Tentar de novo
          </button>
        </div>
      </div>
    );
  }
  if (!eu) return <Carregando />;

  const itens = MENU.filter((i) => !i.permissao || eu.permissoes.includes(i.permissao));
  const ativo = (href: string) => caminho === href || caminho.startsWith(`${href}/`);

  async function sair() {
    await api("/auth/sair", { metodo: "POST" }).catch(() => null);
    await mutate(() => true, undefined, { revalidate: false }); // limpa os dados em memória
    router.replace("/login");
  }

  return (
    <Contexto.Provider value={eu}>
      <div className="lg:flex">
        {/* Menu lateral (computador) */}
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col bg-tinta text-white lg:flex">
          <Link href={paginaInicial(eu)} className="flex items-center gap-3 px-5 py-5">
            <Image src="/logo.png" alt="" width={44} height={44} priority />
            <span className="display text-xl">
              RC <span className="text-amarelo">Motos</span>
            </span>
          </Link>
          <nav className="flex-1 space-y-1 overflow-y-auto px-3" aria-label="Menu principal">
            {itens.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={ativo(item.href) ? "page" : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition-colors ${
                  ativo(item.href)
                    ? "bg-amarelo font-semibold text-tinta"
                    : "text-nevoa hover:bg-white/10 hover:text-white"
                }`}
              >
                <Icone nome={item.icone} />
                {item.rotulo}
              </Link>
            ))}
          </nav>
          <div className="border-t border-white/10 p-4">
            <p className="truncate text-sm font-semibold">{eu.nome}</p>
            <p className="text-xs text-nevoa">{PERFIL[eu.perfil]}</p>
            <button onClick={sair} className="mt-2 text-sm font-semibold text-amarelo hover:underline">
              Sair
            </button>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          {/* Barra superior (celular) */}
          <header className="sticky top-0 z-30 flex items-center justify-between bg-tinta px-4 py-2.5 text-white lg:hidden">
            <Link href={paginaInicial(eu)} className="flex items-center gap-2.5">
              <Image src="/logo.png" alt="" width={36} height={36} priority />
              <span className="display text-lg">
                RC <span className="text-amarelo">Motos</span>
              </span>
            </Link>
            <details className="relative">
              <summary className="cursor-pointer list-none rounded-full bg-white/10 px-3.5 py-1.5 text-sm font-semibold [&::-webkit-details-marker]:hidden">
                Menu
              </summary>
              <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-white p-2 text-tinta shadow-xl">
                <p className="border-b border-borda px-3 pb-2 pt-1 text-sm">
                  <b className="block truncate">{eu.nome}</b>
                  <span className="text-xs text-suave">{PERFIL[eu.perfil]}</span>
                </p>
                {itens
                  .filter((i) => !i.principal)
                  .map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="block rounded-lg px-3 py-2.5 text-sm font-medium hover:bg-gelo"
                    >
                      {item.rotulo}
                    </Link>
                  ))}
                <button
                  onClick={sair}
                  className="block w-full rounded-lg px-3 py-2.5 text-left text-sm font-semibold text-vermelho hover:bg-gelo"
                >
                  Sair
                </button>
              </div>
            </details>
          </header>

          {eu.dados_demo && (
            <p className="bg-amarelo px-4 py-1.5 text-center text-xs font-semibold text-tinta">
              Ambiente de demonstração — todos os números e nomes são ilustrativos.
            </p>
          )}

          <main className="mx-auto max-w-6xl px-4 pb-28 pt-6 sm:px-6 lg:pb-12 lg:pt-8">{children}</main>
        </div>

        {/* Barra inferior (celular) */}
        <nav
          aria-label="Menu principal"
          className="fixed inset-x-0 bottom-0 z-30 flex border-t border-borda bg-white pb-[env(safe-area-inset-bottom)] lg:hidden"
        >
          {itens
            .filter((i) => i.principal)
            .map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={ativo(item.href) ? "page" : undefined}
                className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-semibold ${
                  ativo(item.href) ? "text-azul" : "text-suave"
                }`}
              >
                <span
                  className={`grid h-7 w-12 place-items-center rounded-full ${
                    ativo(item.href) ? "bg-azul/10" : ""
                  }`}
                >
                  <Icone nome={item.icone} />
                </span>
                {item.rotulo}
              </Link>
            ))}
        </nav>
      </div>
    </Contexto.Provider>
  );
}

/** Bloqueia a página para quem não tem a permissão (a API também bloqueia). */
export function Exigir({ permissao, children }: { permissao: Permissao; children: React.ReactNode }) {
  const pode = usePode();
  if (!pode(permissao)) {
    return (
      <div className="rounded-2xl bg-white p-10 text-center text-suave">
        Seu perfil não tem acesso a esta página.
      </div>
    );
  }
  return <>{children}</>;
}
