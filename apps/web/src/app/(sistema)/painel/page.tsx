"use client";

import Link from "next/link";
import useSWR from "swr";
import { GraficoMeses } from "@/components/GraficoMeses";
import { Exigir } from "@/components/Sessao";
import { Aviso, Carregando, Cartao, Etiqueta, Titulo } from "@/components/ui";
import { buscar, mensagemDe } from "@/lib/api";
import { COR_SITUACAO, SITUACAO, SITUACOES_ESTOQUE, mesLongo, moeda } from "@/lib/formato";
import type { Painel } from "@/lib/tipos";

function Numero({
  rotulo,
  valor,
  detalhe,
  destaque,
  largo,
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
  destaque?: boolean;
  /** ocupa a linha inteira no celular */
  largo?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border p-4 sm:p-5 ${largo ? "col-span-2 lg:col-span-1" : ""} ${
        destaque ? "border-tinta bg-tinta text-white" : "border-borda bg-white"
      }`}
    >
      <p className={`text-xs font-bold uppercase tracking-wider ${destaque ? "text-amarelo" : "text-suave"}`}>
        {rotulo}
      </p>
      <p className={`num mt-2 font-bold sm:text-[28px] ${largo ? "text-[28px]" : "text-xl"}`}>{valor}</p>
      {detalhe && <p className={`mt-1 text-xs ${destaque ? "text-nevoa" : "text-suave"}`}>{detalhe}</p>}
    </div>
  );
}

function Conteudo() {
  // Atualiza sozinho a cada 30 s: faturamento e lucro "em tempo real".
  const { data: p, error } = useSWR<Painel>("/painel", buscar, { refreshInterval: 30_000 });
  if (error) return <Aviso>{mensagemDe(error)}</Aviso>;
  if (!p) return <Carregando />;

  const mes = p.mes_atual;
  const margem =
    Number(mes.total.faturamento) > 0
      ? `${((Number(mes.total.lucro) / Number(mes.total.faturamento)) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% do faturamento`
      : undefined;

  return (
    <>
      <Titulo sobre={mesLongo(mes.mes)}>Painel</Titulo>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Numero
          destaque
          largo
          rotulo="Faturamento do mês"
          valor={moeda(mes.total.faturamento)}
          detalhe={`${mes.total.vendas} ${mes.total.vendas === 1 ? "venda" : "vendas"}`}
        />
        <Numero largo rotulo="Lucro do mês" valor={moeda(mes.total.lucro)} detalhe={margem} />
        <Numero
          rotulo="Ticket médio · motos"
          valor={moeda(mes.moto.ticket_medio)}
          detalhe={`${mes.moto.vendas} ${mes.moto.vendas === 1 ? "moto vendida" : "motos vendidas"}`}
        />
        <Numero
          rotulo="Ticket médio · carros"
          valor={moeda(mes.carro.ticket_medio)}
          detalhe={`${mes.carro.vendas} ${mes.carro.vendas === 1 ? "carro vendido" : "carros vendidos"}`}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Cartao className="p-5 sm:p-6 lg:col-span-2">
          <h2 className="mb-4 text-lg font-bold">Faturamento e lucro por mês</h2>
          <GraficoMeses meses={p.meses} />
        </Cartao>

        <Cartao className="p-5 sm:p-6">
          <h2 className="mb-4 text-lg font-bold">Estoque</h2>
          <p className="num text-3xl font-bold">{p.estoque.em_estoque}</p>
          <p className="text-sm text-suave">veículos em estoque</p>
          <ul className="mt-4 space-y-2 text-sm">
            {SITUACOES_ESTOQUE.map((s) => (
              <li key={s} className="flex items-center justify-between">
                <Etiqueta cor={COR_SITUACAO[s]}>{SITUACAO[s]}</Etiqueta>
                <b className="num">{p.estoque.por_situacao[s]}</b>
              </li>
            ))}
          </ul>
          <dl className="num mt-4 space-y-1.5 border-t border-borda pt-4 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-suave">Capital investido</dt>
              <dd className="font-semibold">{moeda(p.estoque.capital_investido)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-suave">Preço anunciado (à venda)</dt>
              <dd className="font-semibold">{moeda(p.estoque.potencial_venda)}</dd>
            </div>
          </dl>
        </Cartao>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Cartao className="p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-bold">Comissões do mês</h2>
            <Link href="/comissoes" className="text-sm font-semibold text-azul hover:underline">
              Relatório
            </Link>
          </div>
          {p.comissoes_mes.length === 0 ? (
            <p className="text-sm text-suave">Nenhuma comissão gerada este mês.</p>
          ) : (
            <ul className="divide-y divide-borda text-sm">
              {p.comissoes_mes.map((c) => (
                <li key={c.vendedor.id} className="flex items-center justify-between gap-3 py-2.5">
                  <span>
                    <b>{c.vendedor.nome}</b>
                    <span className="text-suave">
                      {" "}
                      · {c.vendas} {c.vendas === 1 ? "venda" : "vendas"}
                    </span>
                  </span>
                  <span className="num text-right">
                    <b>{moeda(c.total)}</b>
                    {Number(c.pendente) > 0 && (
                      <span className="block text-xs text-suave">{moeda(c.pendente)} a pagar</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Cartao>

        <Cartao className="p-5 sm:p-6">
          <h2 className="mb-1 text-lg font-bold">Parados há muito tempo</h2>
          <p className="mb-4 text-xs text-suave">Mais de {p.dias_parado_alerta} dias na mesma etapa.</p>
          {p.parados.length === 0 ? (
            <p className="text-sm text-suave">Nenhum veículo parado. 👏</p>
          ) : (
            <ul className="divide-y divide-borda text-sm">
              {p.parados.map((v) => (
                <li key={v.id}>
                  <Link href={`/estoque/${v.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:text-azul">
                    <span className="min-w-0 truncate font-medium">{v.descricao}</span>
                    <span className="flex shrink-0 items-center gap-2">
                      <Etiqueta cor={COR_SITUACAO[v.situacao]}>{SITUACAO[v.situacao]}</Etiqueta>
                      <b className="num">{v.dias} dias</b>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Cartao>
      </div>
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="painel.ver">
      <Conteudo />
    </Exigir>
  );
}
