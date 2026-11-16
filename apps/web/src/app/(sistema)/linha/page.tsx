"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Exigir, usePode } from "@/components/Sessao";
import { Aviso, Carregando, Etiqueta, Titulo } from "@/components/ui";
import { api, buscar, mensagemDe } from "@/lib/api";
import { COR_NIVEL, SITUACAO, data, placa } from "@/lib/formato";
import type { Situacao, Veiculo } from "@/lib/tipos";

// A linha do contrato, na ordem. "Concluído" fica só como contagem, para o quadro não crescer sem fim.
const ETAPAS: Situacao[] = ["compra", "documentacao", "preparacao", "a_venda", "vendido", "pos_venda"];
const PROXIMA: Partial<Record<Situacao, Situacao>> = {
  compra: "documentacao",
  documentacao: "preparacao",
  preparacao: "a_venda",
  vendido: "pos_venda",
  pos_venda: "concluido",
};

function Cartao({ v, aoAvancar, ocupado }: { v: Veiculo; aoAvancar?: () => void; ocupado: boolean }) {
  const proxima = PROXIMA[v.situacao];
  return (
    <li className="rounded-xl border border-borda bg-white p-3">
      <Link href={`/estoque/${v.id}`} className="block font-semibold leading-snug hover:text-azul">
        {v.marca} {v.modelo}
      </Link>
      <p className="mt-0.5 text-xs text-suave">
        {[v.ano_modelo, placa(v.placa)].filter(Boolean).join(" · ")}
      </p>
      <p className="mt-2 flex flex-wrap gap-1.5">
        <Etiqueta cor={v.parado ? "vermelho" : "cinza"}>
          {v.parado ? "Parado · " : ""}
          {v.dias_na_situacao} {v.dias_na_situacao === 1 ? "dia" : "dias"}
        </Etiqueta>
        {v.debitos_abertos > 0 && v.nivel_debito && (
          <Etiqueta cor={COR_NIVEL[v.nivel_debito]}>
            {v.debitos_abertos} {v.debitos_abertos === 1 ? "débito" : "débitos"}
            {v.proximo_prazo && ` · ${data(v.proximo_prazo).slice(0, 5)}`}
          </Etiqueta>
        )}
      </p>
      {aoAvancar && proxima && (
        <button
          type="button"
          disabled={ocupado}
          onClick={aoAvancar}
          className="mt-3 w-full rounded-lg border border-borda px-2 py-1.5 text-xs font-semibold text-azul hover:border-azul disabled:opacity-50"
        >
          Avançar para {SITUACAO[proxima].toLowerCase()} →
        </button>
      )}
      {v.situacao === "a_venda" && (
        <Link
          href={`/estoque/${v.id}`}
          className="mt-3 block rounded-lg bg-amarelo px-2 py-1.5 text-center text-xs font-semibold text-tinta hover:bg-amarelo-escuro"
        >
          Abrir para vender
        </Link>
      )}
    </li>
  );
}

function Quadro() {
  const pode = usePode();
  const { data: veiculos, error, mutate } = useSWR<Veiculo[]>("/veiculos", buscar);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");

  async function avancar(v: Veiculo) {
    const proxima = PROXIMA[v.situacao];
    if (!proxima) return;
    setOcupado(true);
    setErro("");
    try {
      await api(`/veiculos/${v.id}`, { metodo: "PATCH", corpo: { situacao: proxima } });
      await mutate();
    } catch (e) {
      setErro(`${v.marca} ${v.modelo}: ${mensagemDe(e)}`);
    } finally {
      setOcupado(false);
    }
  }

  if (error) return <Aviso>{mensagemDe(error)}</Aviso>;
  if (!veiculos) return <Carregando />;

  const concluidos = veiculos.filter((v) => v.situacao === "concluido").length;
  const parados = veiculos.filter((v) => v.parado).length;

  return (
    <>
      <Titulo sobre="Da compra ao pós-venda">Linha do veículo</Titulo>
      <p className="-mt-3 mb-4 text-sm text-suave">
        {parados > 0 ? (
          <>
            <b className="text-vermelho">
              {parados} {parados === 1 ? "veículo parado" : "veículos parados"}
            </b>{" "}
            há muito tempo na mesma etapa.{" "}
          </>
        ) : (
          "Nenhum veículo parado. "
        )}
        {concluidos > 0 && (
          <Link href="/estoque" className="font-semibold text-azul hover:underline">
            {concluidos} {concluidos === 1 ? "concluído" : "concluídos"}
          </Link>
        )}
      </p>
      {erro && (
        <div className="mb-4">
          <Aviso>{erro}</Aviso>
        </div>
      )}

      {/* No celular o quadro rola de lado; a página em si não. */}
      <div className="-mx-4 overflow-x-auto px-4 pb-3 sm:-mx-6 sm:px-6">
        <div className="grid min-w-[72rem] grid-cols-6 gap-3">
          {ETAPAS.map((etapa) => {
            const daEtapa = veiculos
              .filter((v) => v.situacao === etapa)
              .sort((a, b) => b.dias_na_situacao - a.dias_na_situacao);
            return (
              <section key={etapa} aria-label={SITUACAO[etapa]} className="rounded-2xl bg-white/60 p-2.5">
                <h2 className="flex items-center justify-between px-1 pb-2 text-sm font-bold">
                  {SITUACAO[etapa]}
                  <span className="num grid min-w-6 place-items-center rounded-full bg-tinta px-1.5 text-xs text-white">
                    {daEtapa.length}
                  </span>
                </h2>
                {daEtapa.length === 0 ? (
                  <p className="px-1 py-6 text-center text-xs text-suave">Vazio</p>
                ) : (
                  <ul className="grid gap-2">
                    {daEtapa.map((v) => (
                      <Cartao
                        key={v.id}
                        v={v}
                        ocupado={ocupado}
                        aoAvancar={pode("estoque.editar") ? () => avancar(v) : undefined}
                      />
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      </div>
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="estoque.ver">
      <Quadro />
    </Exigir>
  );
}
