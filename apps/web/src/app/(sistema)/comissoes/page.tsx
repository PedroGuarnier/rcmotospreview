"use client";

import { useState } from "react";
import useSWR from "swr";
import { usePode } from "@/components/Sessao";
import { Aviso, Botao, Carregando, Cartao, Etiqueta, SeletorMes, Titulo, Vazio, useAcao } from "@/components/ui";
import { api, buscar, mensagemDe } from "@/lib/api";
import { STATUS_COMISSAO, data, mesAtual, mesLongo, mesVizinho, moeda, regraDescrita } from "@/lib/formato";
import type { RelatorioComissoes } from "@/lib/tipos";

export default function Comissoes() {
  const pode = usePode();
  const todas = pode("comissoes.ver_todas");
  const [mes, setMes] = useState(mesAtual());
  const { data: rel, error, mutate } = useSWR<RelatorioComissoes>(`/comissoes?mes=${mes}`, buscar, {
    keepPreviousData: true,
  });
  const { ocupado, erro, executar } = useAcao();

  const mudar = (id: number, acao: "pagar" | "desfazer-pagamento") =>
    executar(async () => {
      await api(`/comissoes/${id}/${acao}`, { metodo: "POST" });
      await mutate();
    });

  return (
    <>
      <Titulo
        sobre={todas ? "Relatório do mês" : "Suas comissões"}
        acoes={
          <SeletorMes
            rotulo={mesLongo(mes)}
            aoAnterior={() => setMes(mesVizinho(mes, -1))}
            aoProximo={() => setMes(mesVizinho(mes, 1))}
            podeAvancar={mes < mesAtual()}
          />
        }
      >
        Comissões
      </Titulo>

      {error && <Aviso>{mensagemDe(error)}</Aviso>}
      <Aviso>{erro}</Aviso>
      {!rel && !error && <Carregando />}
      {rel && rel.itens.length === 0 && <Vazio>Nenhuma comissão em {mesLongo(mes)}.</Vazio>}
      {rel && rel.itens.length > 0 && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:max-w-md">
            <div className="rounded-2xl border border-tinta bg-tinta p-4 text-white">
              <p className="text-xs font-bold uppercase tracking-wider text-amarelo">Total do mês</p>
              <p className="num mt-1 text-2xl font-bold">{moeda(rel.total)}</p>
            </div>
            <div className="rounded-2xl border border-borda bg-white p-4">
              <p className="text-xs font-bold uppercase tracking-wider text-suave">
                {todas ? "A pagar" : "A receber"}
              </p>
              <p className="num mt-1 text-2xl font-bold">{moeda(rel.pendente)}</p>
            </div>
          </div>

          {todas && (
            <Cartao className="overflow-x-auto p-5">
              <h2 className="mb-3 text-lg font-bold">Por vendedor</h2>
              <table className="num w-full min-w-[440px] text-left text-sm">
                <thead className="text-xs uppercase text-suave">
                  <tr>
                    <th className="py-2 font-semibold">Vendedor</th>
                    <th className="py-2 text-right font-semibold">Vendas</th>
                    <th className="py-2 text-right font-semibold">Comissão</th>
                    <th className="py-2 text-right font-semibold">Pago</th>
                    <th className="py-2 text-right font-semibold">A pagar</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borda">
                  {rel.por_vendedor.map((g) => (
                    <tr key={g.vendedor.id}>
                      <td className="py-2.5 font-medium">{g.vendedor.nome}</td>
                      <td className="py-2.5 text-right">{g.vendas}</td>
                      <td className="py-2.5 text-right font-semibold">{moeda(g.total)}</td>
                      <td className="py-2.5 text-right">{moeda(g.pago)}</td>
                      <td className="py-2.5 text-right">{moeda(g.pendente)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Cartao>
          )}

          <Cartao className="divide-y divide-borda">
            {rel.itens.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5 sm:px-5">
                <div className="min-w-0">
                  <p className="truncate font-semibold">{c.veiculo}</p>
                  <p className="text-sm text-suave">
                    {data(c.data_venda)}
                    {todas && ` · ${c.vendedor.nome}`} · venda de {moeda(c.valor_venda)} ·{" "}
                    {regraDescrita(c.regra, c.regra_valor)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Etiqueta cor={c.status === "paga" ? "verde" : "amarelo"}>{STATUS_COMISSAO[c.status]}</Etiqueta>
                  <b className="num">{moeda(c.valor)}</b>
                  {pode("comissoes.pagar") &&
                    (c.status === "pendente" ? (
                      <Botao pequeno disabled={ocupado} onClick={() => mudar(c.id, "pagar")}>
                        Marcar paga
                      </Botao>
                    ) : (
                      <Botao tom="fantasma" pequeno disabled={ocupado} onClick={() => mudar(c.id, "desfazer-pagamento")}>
                        Desfazer
                      </Botao>
                    ))}
                </div>
              </div>
            ))}
          </Cartao>
        </div>
      )}
    </>
  );
}
