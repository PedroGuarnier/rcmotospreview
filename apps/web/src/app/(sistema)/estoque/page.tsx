"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { Exigir, usePode } from "@/components/Sessao";
import { VenderModal } from "@/components/VenderModal";
import { Aviso, Botao, Carregando, Etiqueta, Titulo, Vazio } from "@/components/ui";
import { buscar, mensagemDe } from "@/lib/api";
import { COR_SITUACAO, SITUACAO, moeda, numero, placa } from "@/lib/formato";
import type { Situacao, TipoVeiculo, Veiculo } from "@/lib/tipos";

type Filtro = "estoque" | "vendidos" | Situacao;

const FILTROS: { valor: Filtro; rotulo: string }[] = [
  { valor: "estoque", rotulo: "Em estoque" },
  { valor: "a_venda", rotulo: "À venda" },
  { valor: "preparacao", rotulo: "Preparação" },
  { valor: "documentacao", rotulo: "Documentação" },
  { valor: "compra", rotulo: "Compra" },
  { valor: "vendidos", rotulo: "Vendidos" },
];

function Chip({ ativo, children, onClick }: { ativo: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={ativo}
      onClick={onClick}
      className={`min-h-9 whitespace-nowrap rounded-full border px-4 text-sm font-semibold transition-colors ${
        ativo ? "border-azul bg-azul text-white" : "border-borda bg-white text-tinta hover:border-azul"
      }`}
    >
      {children}
    </button>
  );
}

function CartaoVeiculo({ v, aoVender }: { v: Veiculo; aoVender?: () => void }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-borda bg-white">
      <Link href={`/estoque/${v.id}`} className="group block">
        <div className={`relative bg-gelo ${v.foto_capa ? "aspect-[4/3]" : "h-28 sm:aspect-[4/3] sm:h-auto"}`}>
          {v.foto_capa ? (
            // eslint-disable-next-line @next/next/no-img-element -- miniatura já otimizada pela API
            <img src={v.foto_capa} alt="" loading="lazy" className="size-full object-cover" />
          ) : (
            <div className="grid size-full place-items-center text-sm text-suave">Sem foto</div>
          )}
          <span className="absolute left-3 top-3">
            <Etiqueta sobreFoto cor={COR_SITUACAO[v.situacao]}>
              {SITUACAO[v.situacao]}
            </Etiqueta>
          </span>
        </div>
        <div className="px-4 pt-3">
          <h2 className="font-bold leading-snug group-hover:text-azul">
            {v.marca} {v.modelo}
          </h2>
          <p className="mt-0.5 text-sm text-suave">
            {[v.ano_modelo, v.cor, v.km !== null ? `${numero(v.km)} km` : null, placa(v.placa)]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </Link>
      <div className="mt-auto flex items-end justify-between gap-3 px-4 pb-4 pt-3">
        <div>
          <p className="num text-xl font-bold">{v.preco_venda ? moeda(v.preco_venda) : "Sem preço"}</p>
          {v.custo_total !== null && (
            <p className="num text-xs text-suave">
              Custo {moeda(v.custo_total)}
              {v.lucro_previsto !== null && (
                <>
                  {" · "}
                  <span className={Number(v.lucro_previsto) < 0 ? "text-vermelho" : "text-verde"}>
                    lucro previsto {moeda(v.lucro_previsto)}
                  </span>
                </>
              )}
            </p>
          )}
        </div>
        {aoVender && (
          <Botao tom="amarelo" pequeno onClick={aoVender}>
            Vender
          </Botao>
        )}
      </div>
    </article>
  );
}

function Estoque() {
  const router = useRouter();
  const pode = usePode();
  const [filtro, setFiltro] = useState<Filtro>("estoque");
  const [tipo, setTipo] = useState<TipoVeiculo | "">("");
  const [texto, setTexto] = useState("");
  const [busca, setBusca] = useState("");
  const [vendendo, setVendendo] = useState<Veiculo | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setBusca(texto.trim()), 300);
    return () => clearTimeout(t);
  }, [texto]);

  const params = new URLSearchParams();
  if (filtro === "estoque" || filtro === "vendidos") params.set("grupo", filtro);
  else params.set("situacao", filtro);
  if (tipo) params.set("tipo", tipo);
  if (busca) params.set("busca", busca);
  const { data: veiculos, error, mutate } = useSWR<Veiculo[]>(`/veiculos?${params}`, buscar, {
    keepPreviousData: true,
  });

  return (
    <>
      <Titulo
        sobre="Motos e carros"
        acoes={
          pode("estoque.editar") && (
            <Link
              href="/estoque/novo"
              className="inline-flex min-h-11 items-center rounded-full bg-azul px-5 text-[15px] font-semibold text-white hover:bg-azul-escuro"
            >
              + Novo veículo
            </Link>
          )
        }
      >
        Estoque
      </Titulo>

      <div className="mb-5 space-y-3">
        <input
          type="search"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Buscar por modelo, marca, placa, cor…"
          aria-label="Buscar no estoque"
          className="min-h-11 w-full rounded-full border border-borda bg-white px-5 text-[15px] focus:border-azul focus:outline-none focus:ring-2 focus:ring-azul/20"
        />
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0">
          {FILTROS.map((f) => (
            <Chip key={f.valor} ativo={filtro === f.valor} onClick={() => setFiltro(f.valor)}>
              {f.rotulo}
            </Chip>
          ))}
          <span className="mx-1 w-px shrink-0 bg-borda" aria-hidden />
          <Chip ativo={tipo === "moto"} onClick={() => setTipo(tipo === "moto" ? "" : "moto")}>
            Motos
          </Chip>
          <Chip ativo={tipo === "carro"} onClick={() => setTipo(tipo === "carro" ? "" : "carro")}>
            Carros
          </Chip>
        </div>
      </div>

      {error && <Aviso>{mensagemDe(error)}</Aviso>}
      {!veiculos && !error && <Carregando />}
      {veiculos && veiculos.length === 0 && (
        <Vazio>{busca || tipo ? "Nenhum veículo encontrado com esses filtros." : "Nenhum veículo aqui ainda."}</Vazio>
      )}
      {veiculos && veiculos.length > 0 && (
        <>
          <p className="mb-3 text-sm text-suave">
            {veiculos.length} {veiculos.length === 1 ? "veículo" : "veículos"}
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {veiculos.map((v) => (
              <CartaoVeiculo
                key={v.id}
                v={v}
                aoVender={
                  v.situacao === "a_venda" && pode("vendas.registrar") ? () => setVendendo(v) : undefined
                }
              />
            ))}
          </div>
        </>
      )}

      {vendendo && (
        <VenderModal
          veiculo={vendendo}
          aoFechar={() => setVendendo(null)}
          aoVender={() => {
            setVendendo(null);
            mutate();
            router.push("/vendas");
          }}
        />
      )}
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="estoque.ver">
      <Estoque />
    </Exigir>
  );
}
