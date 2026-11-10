"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { flushSync } from "react-dom";
import useSWR from "swr";
import { LaudoVisual, Semaforo } from "@/components/placa/Laudo";
import { type FormatoPlaca, PlacaMercosul, filtrarPlaca, placaCompleta } from "@/components/placa/PlacaMercosul";
import { Exigir } from "@/components/Sessao";
import { Aviso, Botao, Carregando, Cartao, Titulo, Vazio } from "@/components/ui";
import { api, buscar, mensagemDe } from "@/lib/api";
import { dataHora, placa as formatarPlaca } from "@/lib/formato";
import type { Laudo } from "@/lib/tipos";

const pausa = (ms: number) => new Promise((ok) => setTimeout(ok, ms));
const semMovimento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function Conteudo() {
  const { data: situacao } = useSWR<{ disponivel: boolean; ilustrativo: boolean }>("/procedencia/situacao", buscar);
  const { data: ultimas, mutate } = useSWR<Laudo[]>("/procedencia", buscar);
  // /procedencia?placa=ABC1D23 (vindo da página do veículo): já abre preenchida
  const daUrl = useSearchParams().get("placa") ?? "";
  const [placa, setPlaca] = useState(() => filtrarPlaca(daUrl).valor);
  const [formato, setFormato] = useState<FormatoPlaca>("moto");
  const [consultando, setConsultando] = useState(false);
  const [laudo, setLaudo] = useState<Laudo | null>(null);
  const [erro, setErro] = useState("");

  function trocarFormato(novo: FormatoPlaca) {
    if (novo === formato) return;
    if (document.startViewTransition && !semMovimento()) {
      document.startViewTransition(() => flushSync(() => setFormato(novo)));
    } else setFormato(novo);
  }

  async function consultar() {
    setErro("");
    setLaudo(null);
    setConsultando(true);
    try {
      const [novo] = await Promise.all([
        api<Laudo>("/procedencia/consultar", { corpo: { placa } }),
        pausa(semMovimento() ? 0 : 1150), // o feixe passa pela chapa ao menos uma vez
      ]);
      setLaudo(novo);
      mutate();
    } catch (e) {
      setErro(mensagemDe(e));
    } finally {
      setConsultando(false);
    }
  }

  function abrir(antigo: Laudo) {
    setErro("");
    setPlaca(antigo.placa);
    if (antigo.dados_veiculo.tipo) setFormato(antigo.dados_veiculo.tipo);
    setLaudo(antigo);
    window.scrollTo({ top: 0, behavior: semMovimento() ? "auto" : "smooth" });
  }

  const indisponivel = situacao?.disponivel === false;

  return (
    <>
      <Titulo sobre="Roubo e furto · leilão · Renajud · cadastro">Procedência pela placa</Titulo>

      {indisponivel && (
        <div className="mb-4">
          <Aviso tom="info">
            A consulta ainda não está conectada ao provedor nacional. Assim que a conta da loja no provedor
            for criada e configurada, este botão passa a consultar de verdade.
          </Aviso>
        </div>
      )}
      {situacao?.ilustrativo && (
        <div className="mb-4">
          <Aviso tom="info">
            Modo demonstração: os resultados são <b>ilustrativos</b>, não vêm de base oficial. Para ver os três
            sinais, use placas terminadas em 3 (atenção) e em 7 (alerta).
          </Aviso>
        </div>
      )}

      <div className="grid gap-8 rounded-3xl bg-tinta p-5 text-white sm:p-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)] lg:gap-12">
        <div className="grid content-start justify-items-center gap-4">
          <div className="inline-grid grid-flow-col rounded-lg p-[3px] shadow-[inset_0_0_0_2px_rgb(255_255_255/0.28)]" role="group" aria-label="Formato da placa">
            {(["moto", "carro"] as const).map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={formato === f}
                onClick={() => trocarFormato(f)}
                className={`min-h-10 rounded-[5px] px-4 text-xs font-bold uppercase tracking-widest transition-colors ${
                  formato === f ? "bg-amarelo text-tinta" : ""
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          <PlacaMercosul
            valor={placa}
            formato={formato}
            aoMudar={(v) => {
              setPlaca(v);
              setLaudo(null);
              setErro("");
            }}
            aoConfirmar={() => !indisponivel && consultar()}
            estado={consultando ? "consultando" : "livre"}
            rotulo="Placa do veículo (7 caracteres)"
            transicao
            autoFoco
          />

          <Botao
            tom="amarelo"
            disabled={!placaCompleta(placa) || indisponivel}
            ocupado={consultando}
            onClick={consultar}
            className="min-w-56"
          >
            Consultar procedência
          </Botao>
          <p className="max-w-xs text-center text-xs text-nevoa">
            Cada consulta fica guardada no histórico. Se a placa já é de um veículo do estoque, o laudo entra
            na página dele.
          </p>
        </div>

        <div className="min-h-64" aria-live="polite">
          {erro && <Aviso>{erro}</Aviso>}
          {!laudo && !erro && (
            <div className="grid gap-4 text-nevoa">
              <div className="flex items-center gap-4">
                <Semaforo cor={null} />
                <p className="display text-3xl text-white/30">
                  {consultando ? "Conferindo…" : "O laudo aparece aqui"}
                </p>
              </div>
              <p className="text-sm">
                Digite a placa (antiga ou Mercosul). A chapa recusa letra onde vai número.
              </p>
            </div>
          )}
          {laudo && (
            <div key={laudo.id}>
              <div className="mb-6 border-b-[3px] border-amarelo pb-5">
                <p className="text-xs font-bold uppercase tracking-widest text-amarelo">
                  {formatarPlaca(laudo.placa)} · {dataHora(laudo.criado_em)}
                  {laudo.consultado_por && ` · por ${laudo.consultado_por}`}
                </p>
                <p className="display mt-1 text-4xl">
                  {laudo.veiculo_descricao ?? laudo.dados_veiculo.marca_modelo ?? "Veículo"}
                </p>
                <p className="mt-1 text-sm text-nevoa">
                  {[
                    laudo.dados_veiculo.ano_fabricacao && laudo.dados_veiculo.ano_modelo
                      ? `${laudo.dados_veiculo.ano_fabricacao}/${laudo.dados_veiculo.ano_modelo}`
                      : null,
                    laudo.dados_veiculo.cor,
                    laudo.dados_veiculo.municipio && `${laudo.dados_veiculo.municipio}/${laudo.dados_veiculo.uf}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                {laudo.veiculo_id ? (
                  <Link href={`/estoque/${laudo.veiculo_id}`} className="mt-2 inline-block text-sm font-semibold text-amarelo underline underline-offset-4">
                    Abrir o veículo no estoque
                  </Link>
                ) : (
                  <p className="mt-2 text-sm text-nevoa">
                    Ainda não está no estoque. Se a loja comprar, o laudo vai junto no cadastro.
                  </p>
                )}
              </div>
              <LaudoVisual
                semaforo={laudo.semaforo}
                itens={laudo.itens}
                historico={laudo.historico}
                consultadoEm={laudo.criado_em}
                ilustrativo={laudo.ilustrativo}
              />
            </div>
          )}
        </div>
      </div>

      <h2 className="mb-3 mt-8 text-lg font-bold">Últimas consultas</h2>
      {!ultimas && <Carregando />}
      {ultimas && ultimas.length === 0 && <Vazio>Nenhuma placa consultada ainda.</Vazio>}
      {ultimas && ultimas.length > 0 && (
        <Cartao className="divide-y divide-borda">
          {ultimas.map((l) => (
            <button
              key={l.id}
              type="button"
              onClick={() => abrir(l)}
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-gelo/60 sm:px-5"
            >
              <span className="flex min-w-0 items-center gap-3">
                <Semaforo cor={l.semaforo} deitado tamanho="0.8rem" />
                <span className="min-w-0">
                  <span className="block font-bold tracking-wider">{formatarPlaca(l.placa)}</span>
                  <span className="block truncate text-sm text-suave">
                    {l.veiculo_descricao ?? l.dados_veiculo.marca_modelo ?? "Fora do estoque"}
                  </span>
                </span>
              </span>
              <span className="shrink-0 text-right text-xs text-suave">
                {dataHora(l.criado_em)}
                {l.consultado_por && <span className="block">{l.consultado_por}</span>}
              </span>
            </button>
          ))}
        </Cartao>
      )}
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="procedencia.consultar">
      <Suspense fallback={<Carregando />}>
        <Conteudo />
      </Suspense>
    </Exigir>
  );
}
