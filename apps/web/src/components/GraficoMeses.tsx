"use client";

import { useState } from "react";
import { mesCurto, mesLongo, moeda, moedaCurta } from "@/lib/formato";
import type { MesPainel } from "@/lib/tipos";

// Par validado (daltonismo e contraste em fundo claro) com o validador de paleta.
const SERIES = [
  { chave: "faturamento", rotulo: "Faturamento", cor: "#4A45E8" },
  { chave: "lucro", rotulo: "Lucro", cor: "#B8860B" },
] as const;

function teto(valor: number): number {
  if (valor <= 0) return 1;
  const base = 10 ** Math.floor(Math.log10(valor));
  return [1, 2, 2.5, 5, 10].map((m) => m * base).find((v) => v >= valor) ?? 10 * base;
}

/** Faturamento e lucro por mês: colunas agrupadas, mesma escala em R$. */
export function GraficoMeses({ meses }: { meses: MesPainel[] }) {
  const [foco, setFoco] = useState<number | null>(null);
  const valores = meses.flatMap((m) => [Number(m.total.faturamento), Number(m.total.lucro)]);
  const maximo = teto(Math.max(...valores, 0));
  const minimo = Math.min(...valores, 0) < 0 ? -teto(-Math.min(...valores)) : 0;
  const amplitude = maximo - minimo;
  const y = (valor: number) => ((maximo - valor) / amplitude) * 100; // % a partir do topo
  const linhas = [maximo, maximo / 2, 0, ...(minimo < 0 ? [minimo] : [])];

  return (
    <figure>
      <figcaption className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-suave">
        {SERIES.map((s) => (
          <span key={s.chave} className="inline-flex items-center gap-1.5">
            <i className="inline-block size-2.5 rounded-sm" style={{ background: s.cor }} /> {s.rotulo}
          </span>
        ))}
      </figcaption>

      <div className="flex gap-2">
        <div className="relative h-52 w-14 shrink-0 text-right text-[11px] text-suave" aria-hidden>
          {linhas.map((v) => (
            <span key={v} className="num absolute right-0 -translate-y-1/2" style={{ top: `${y(v)}%` }}>
              {v === 0 ? "0" : moedaCurta(v).replace("R$ ", "")}
            </span>
          ))}
        </div>
        <div className="relative h-52 flex-1">
          {linhas.map((v) => (
            <i
              key={v}
              aria-hidden
              className={`absolute inset-x-0 block h-px ${v === 0 ? "bg-suave/50" : "bg-borda"}`}
              style={{ top: `${y(v)}%` }}
            />
          ))}
          <div className="absolute inset-0 flex">
            {meses.map((m, i) => (
              <button
                key={m.mes}
                type="button"
                onMouseEnter={() => setFoco(i)}
                onMouseLeave={() => setFoco(null)}
                onFocus={() => setFoco(i)}
                onBlur={() => setFoco(null)}
                aria-label={`${mesLongo(m.mes)}: faturamento ${moeda(m.total.faturamento)}, lucro ${moeda(m.total.lucro)}, ${m.total.vendas} vendas`}
                className={`relative flex-1 rounded-md outline-offset-0 ${foco === i ? "bg-azul/5" : ""}`}
              >
                <span className="absolute inset-y-0 left-1/2 flex -translate-x-1/2 gap-0.5">
                  {SERIES.map((s) => {
                    const valor = Number(m.total[s.chave]);
                    const topo = y(Math.max(valor, 0));
                    const altura = (Math.abs(valor) / amplitude) * 100;
                    return (
                      <span key={s.chave} className="relative block w-3 sm:w-5">
                        <i
                          className={`absolute inset-x-0 block ${valor >= 0 ? "rounded-t" : "rounded-b"}`}
                          style={{ top: `${topo}%`, height: `${altura}%`, background: s.cor }}
                        />
                      </span>
                    );
                  })}
                </span>
              </button>
            ))}
          </div>
          {foco !== null && (
            <div
              role="status"
              className="pointer-events-none absolute top-0 z-10 w-44 -translate-x-1/2 rounded-xl border border-borda bg-white p-3 text-xs shadow-lg"
              style={{ left: `clamp(5.5rem, ${((foco + 0.5) / meses.length) * 100}%, calc(100% - 5.5rem))` }}
            >
              <p className="mb-1 font-bold first-letter:uppercase">{mesLongo(meses[foco].mes)}</p>
              {SERIES.map((s) => (
                <p key={s.chave} className="num flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5 text-suave">
                    <i className="inline-block size-2 rounded-sm" style={{ background: s.cor }} />
                    {s.rotulo}
                  </span>
                  <b>{moeda(meses[foco].total[s.chave])}</b>
                </p>
              ))}
              <p className="mt-1 text-suave">
                {meses[foco].total.vendas} {meses[foco].total.vendas === 1 ? "venda" : "vendas"}
              </p>
            </div>
          )}
        </div>
      </div>
      <div className="ml-16 flex text-center text-[11px] text-suave" aria-hidden>
        {meses.map((m) => (
          <span key={m.mes} className="flex-1 pt-1.5">
            {mesCurto(m.mes)}
          </span>
        ))}
      </div>

      <details className="mt-4 text-sm">
        <summary className="cursor-pointer font-semibold text-azul">Ver em tabela</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="num w-full min-w-[520px] text-left text-sm">
            <thead className="text-xs uppercase text-suave">
              <tr>
                <th className="py-1.5 font-semibold">Mês</th>
                <th className="py-1.5 text-right font-semibold">Vendas</th>
                <th className="py-1.5 text-right font-semibold">Faturamento</th>
                <th className="py-1.5 text-right font-semibold">Lucro</th>
                <th className="py-1.5 text-right font-semibold">Ticket moto</th>
                <th className="py-1.5 text-right font-semibold">Ticket carro</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borda">
              {meses.map((m) => (
                <tr key={m.mes}>
                  <td className="py-1.5">{mesCurto(m.mes)}</td>
                  <td className="py-1.5 text-right">{m.total.vendas}</td>
                  <td className="py-1.5 text-right">{moeda(m.total.faturamento)}</td>
                  <td className="py-1.5 text-right">{moeda(m.total.lucro)}</td>
                  <td className="py-1.5 text-right">{moeda(m.moto.ticket_medio)}</td>
                  <td className="py-1.5 text-right">{moeda(m.carro.ticket_medio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
