"use client";

import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { usePode } from "@/components/Sessao";
import { Aviso as Erro, Botao, Carregando, Cartao, Etiqueta, Titulo, Vazio, useAcao } from "@/components/ui";
import { api, buscar, mensagemDe } from "@/lib/api";
import { COR_NIVEL, data, mensagemDeTransferencia, moeda, prazoEmPalavras, whatsappCliente } from "@/lib/formato";
import type { Aviso, Avisos } from "@/lib/tipos";

const ROTULO_NIVEL = { vencido: "Vencido", hoje: "Hoje", urgente: "Urgente", atencao: "Atenção" } as const;

function Linha({ aviso, aoResolver }: { aviso: Aviso; aoResolver: () => void }) {
  const pode = usePode();
  const { ocupado, erro, executar } = useAcao();
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 px-4 py-4 sm:px-5">
      <div className="min-w-0 flex-1 basis-64">
        <p className="flex flex-wrap items-center gap-2">
          <Etiqueta cor={COR_NIVEL[aviso.nivel]}>{ROTULO_NIVEL[aviso.nivel]}</Etiqueta>
          <b>{aviso.titulo}</b>
        </p>
        <p className="mt-1 text-sm text-suave">
          <Link href={`/estoque/${aviso.veiculo_id}`} className="font-medium text-azul hover:underline">
            {aviso.veiculo}
          </Link>{" "}
          · prazo {data(aviso.prazo)} ({prazoEmPalavras(aviso.dias_restantes)})
          {aviso.valor && <> · {moeda(aviso.valor)}</>}
        </p>
        {erro && <p className="mt-1 text-sm font-medium text-vermelho">{erro}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        {aviso.tipo === "debito" && (
          <Link
            href={`/estoque/${aviso.veiculo_id}#debitos`}
            className="inline-flex min-h-9 items-center rounded-full border border-borda bg-white px-3.5 text-sm font-semibold hover:border-azul"
          >
            Abrir o débito
          </Link>
        )}
        {aviso.tipo === "transferencia" && (
          <>
            {aviso.cliente_telefone && aviso.cliente_nome && (
              <a
                href={whatsappCliente(
                  aviso.cliente_telefone,
                  mensagemDeTransferencia(aviso.cliente_nome, aviso.veiculo, aviso.prazo, aviso.dias_restantes),
                )}
                target="_blank"
                rel="noopener"
                className="inline-flex min-h-9 items-center rounded-full bg-verde px-3.5 text-sm font-semibold text-white hover:opacity-90"
              >
                Cobrar no WhatsApp
              </a>
            )}
            {pode("transferencia.gerir") && (
              <Botao
                tom="neutro"
                pequeno
                ocupado={ocupado}
                onClick={() =>
                  executar(async () => {
                    await api(`/vendas/${aviso.venda_id}/transferencia`, { corpo: {} });
                    aoResolver();
                  })
                }
              >
                Já transferiu
              </Botao>
            )}
          </>
        )}
      </div>
    </li>
  );
}

export default function PaginaAvisos() {
  const { mutate } = useSWRConfig();
  const { data: avisos, error } = useSWR<Avisos>("/avisos", buscar);

  return (
    <>
      <Titulo sobre="Prazos que pedem ação">Avisos</Titulo>
      <p className="-mt-3 mb-5 max-w-2xl text-sm text-suave">
        Débitos de veículos aparecem aqui faltando 15 dias, 7 dias e no dia. A transferência pelo comprador
        aparece a partir do 10º dia da venda, até ser marcada como feita.
      </p>
      {error && <Erro>{mensagemDe(error)}</Erro>}
      {!avisos && !error && <Carregando />}
      {avisos && avisos.total === 0 && <Vazio>Nenhum prazo pendente. Tudo em dia.</Vazio>}
      {avisos && avisos.total > 0 && (
        <Cartao>
          <ul className="divide-y divide-borda">
            {avisos.itens.map((aviso) => (
              <Linha
                key={`${aviso.tipo}-${aviso.venda_id ?? aviso.veiculo_id}-${aviso.titulo}`}
                aviso={aviso}
                aoResolver={() => mutate("/avisos")}
              />
            ))}
          </ul>
        </Cartao>
      )}
    </>
  );
}
