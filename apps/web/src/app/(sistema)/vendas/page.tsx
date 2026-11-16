"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { usePode } from "@/components/Sessao";
import { Aviso, Botao, Campo, Carregando, Cartao, Etiqueta, Modal, SeletorMes, Titulo, Vazio, useAcao } from "@/components/ui";
import { api, buscar, mensagemDe } from "@/lib/api";
import {
  FORMA,
  cpfCnpj,
  data,
  mensagemDeTransferencia,
  mesAtual,
  mesLongo,
  mesVizinho,
  moeda,
  prazoEmPalavras,
  regraDescrita,
  telefone,
  whatsappCliente,
} from "@/lib/formato";
import type { Venda } from "@/lib/tipos";

function Linha({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5">
      <dt className="text-suave">{rotulo}</dt>
      <dd className="num text-right font-medium">{children}</dd>
    </div>
  );
}

const COR_TRANSFERENCIA = { transferida: "verde", no_prazo: "cinza", cobrar: "amarelo", vencida: "vermelho" } as const;

function BlocoTransferencia({ venda, aoMudar }: { venda: Venda; aoMudar: (v: Venda) => void }) {
  const pode = usePode();
  const { ocupado, erro, executar } = useAcao();
  const t = venda.transferencia;
  if (!t) return null;
  const rotulo =
    t.situacao === "transferida"
      ? `Transferida em ${data(t.transferida_em)}`
      : `Prazo ${data(t.prazo)} · ${prazoEmPalavras(t.dias_restantes)}`;
  const mudar = (metodo: "POST" | "DELETE") =>
    executar(async () =>
      aoMudar(await api<Venda>(`/vendas/${venda.id}/transferencia`, { metodo, corpo: metodo === "POST" ? {} : undefined })),
    );

  return (
    <div className="mt-5 rounded-xl bg-gelo px-4 py-3.5 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <b>Transferência para o comprador</b>
        <Etiqueta cor={COR_TRANSFERENCIA[t.situacao]}>{rotulo}</Etiqueta>
      </p>
      {t.situacao !== "transferida" && (
        <p className="mt-1 text-xs text-suave">O comprador tem 30 dias, a partir da venda, para passar o veículo para o nome dele.</p>
      )}
      {erro && <p className="mt-2 font-medium text-vermelho">{erro}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {t.situacao !== "transferida" && venda.cliente.telefone && (
          <a
            href={whatsappCliente(
              venda.cliente.telefone,
              mensagemDeTransferencia(venda.cliente.nome, venda.veiculo.descricao, t.prazo, t.dias_restantes),
            )}
            target="_blank"
            rel="noopener"
            className="inline-flex min-h-9 items-center rounded-full bg-verde px-3.5 text-sm font-semibold text-white hover:opacity-90"
          >
            Cobrar no WhatsApp
          </a>
        )}
        {pode("transferencia.gerir") &&
          (t.situacao === "transferida" ? (
            <Botao tom="fantasma" pequeno ocupado={ocupado} onClick={() => mudar("DELETE")}>
              Desfazer
            </Botao>
          ) : (
            <Botao tom="neutro" pequeno ocupado={ocupado} onClick={() => mudar("POST")}>
              Marcar como transferida
            </Botao>
          ))}
      </div>
    </div>
  );
}

function DetalheVenda({
  venda,
  aoFechar,
  aoMudar,
  aoTrocar,
}: {
  venda: Venda;
  aoFechar: () => void;
  aoMudar: () => void;
  /** a venda mudou e continua aberta (ex.: transferência marcada) */
  aoTrocar: (venda: Venda) => void;
}) {
  const pode = usePode();
  const [cancelando, setCancelando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const { ocupado, erro, executar } = useAcao();

  function cancelar(e: React.FormEvent) {
    e.preventDefault();
    executar(async () => {
      await api(`/vendas/${venda.id}/cancelar`, { corpo: { motivo } });
      aoMudar();
      aoFechar();
    });
  }

  return (
    <Modal titulo={`Venda nº ${venda.id}`} aoFechar={aoFechar}>
      <dl className="divide-y divide-borda text-sm">
        <Linha rotulo="Veículo">
          <Link href={`/estoque/${venda.veiculo.id}`} className="text-azul hover:underline">
            {venda.veiculo.descricao}
          </Link>
        </Linha>
        <Linha rotulo="Data">{data(venda.data_venda)}</Linha>
        <Linha rotulo="Comprador">{venda.cliente.nome}</Linha>
        {venda.cliente.telefone && <Linha rotulo="WhatsApp">{telefone(venda.cliente.telefone)}</Linha>}
        {venda.cliente.cpf_cnpj && <Linha rotulo="CPF/CNPJ">{cpfCnpj(venda.cliente.cpf_cnpj)}</Linha>}
        <Linha rotulo="Vendedor">{venda.vendedor.nome}</Linha>
        <Linha rotulo="Valor">{moeda(venda.valor)}</Linha>
        <Linha rotulo="Forma">
          {FORMA[venda.forma]}
          {venda.banco && ` · ${venda.banco}`}
        </Linha>
        {venda.entrada && <Linha rotulo="Entrada">{moeda(venda.entrada)}</Linha>}
        {venda.numero_parcelas && (
          <Linha rotulo="Parcelas">
            {venda.numero_parcelas}× {moeda(venda.valor_parcela)} · 1º venc. {data(venda.primeiro_vencimento)}
          </Linha>
        )}
        {venda.lucro !== null && (
          <>
            <Linha rotulo="Compra + custos">
              {moeda(Number(venda.valor_compra) + Number(venda.total_custos))}
            </Linha>
            <Linha rotulo="Lucro">
              <span className={Number(venda.lucro) < 0 ? "text-vermelho" : "text-verde"}>{moeda(venda.lucro)}</span>
            </Linha>
          </>
        )}
        {venda.comissao && (
          <Linha rotulo="Comissão">
            {moeda(venda.comissao.valor)}{" "}
            <span className="font-normal text-suave">
              ({regraDescrita(venda.comissao.regra, venda.comissao.regra_valor)})
            </span>
          </Linha>
        )}
        {venda.observacoes && <Linha rotulo="Observações">{venda.observacoes}</Linha>}
        {venda.status === "cancelada" && (
          <Linha rotulo="Cancelada">{venda.motivo_cancelamento ?? "—"}</Linha>
        )}
      </dl>

      <BlocoTransferencia venda={venda} aoMudar={aoTrocar} />

      {venda.status === "ativa" && pode("vendas.cancelar") && (
        <div className="mt-5 border-t border-borda pt-4">
          {cancelando ? (
            <form onSubmit={cancelar} className="space-y-3">
              <Campo
                rotulo="Motivo do cancelamento"
                required
                autoFocus
                maxLength={300}
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                dica="O veículo volta para “à venda” e a comissão é cancelada."
              />
              <Aviso>{erro}</Aviso>
              <div className="flex justify-end gap-2">
                <Botao tom="neutro" pequeno onClick={() => setCancelando(false)}>
                  Voltar
                </Botao>
                <Botao tom="perigo" pequeno type="submit" ocupado={ocupado}>
                  Cancelar a venda
                </Botao>
              </div>
            </form>
          ) : (
            <Botao tom="perigo" pequeno onClick={() => setCancelando(true)}>
              Cancelar venda…
            </Botao>
          )}
        </div>
      )}
    </Modal>
  );
}

export default function Vendas() {
  const pode = usePode();
  const [mes, setMes] = useState(mesAtual());
  const [canceladas, setCanceladas] = useState(false);
  const [aberta, setAberta] = useState<Venda | null>(null);
  const { mutate: atualizarAvisos } = useSWRConfig();
  const { data: vendas, error, mutate } = useSWR<Venda[]>(
    `/vendas?mes=${mes}${canceladas ? "&incluir_canceladas=true" : ""}`,
    buscar,
    { keepPreviousData: true },
  );

  const ativas = vendas?.filter((v) => v.status === "ativa") ?? [];
  const total = ativas.reduce((soma, v) => soma + Number(v.valor), 0);
  const verLucro = pode("custos.ver");
  const lucro = ativas.reduce((soma, v) => soma + Number(v.lucro ?? 0), 0);

  return (
    <>
      <Titulo
        sobre={pode("vendas.ver_todas") ? "Todas as vendas" : "Suas vendas"}
        acoes={
          <SeletorMes
            rotulo={mesLongo(mes)}
            aoAnterior={() => setMes(mesVizinho(mes, -1))}
            aoProximo={() => setMes(mesVizinho(mes, 1))}
            podeAvancar={mes < mesAtual()}
          />
        }
      >
        Vendas
      </Titulo>

      {error && <Aviso>{mensagemDe(error)}</Aviso>}
      {!vendas && !error && <Carregando />}
      {vendas && (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="num text-sm">
              <b>{ativas.length}</b> {ativas.length === 1 ? "venda" : "vendas"} · <b>{moeda(total)}</b>
              {verLucro && (
                <>
                  {" "}
                  · lucro <b className={lucro < 0 ? "text-vermelho" : "text-verde"}>{moeda(lucro)}</b>
                </>
              )}
            </p>
            {pode("vendas.cancelar") && (
              <label className="flex items-center gap-2 text-sm text-suave">
                <input
                  type="checkbox"
                  checked={canceladas}
                  onChange={(e) => setCanceladas(e.target.checked)}
                  className="size-4 accent-azul"
                />
                Mostrar canceladas
              </label>
            )}
          </div>

          {vendas.length === 0 ? (
            <Vazio>
              Nenhuma venda em {mesLongo(mes)}.{" "}
              {pode("vendas.registrar") && (
                <>
                  Para dar baixa, abra o{" "}
                  <Link href="/estoque" className="font-semibold text-azul hover:underline">
                    estoque
                  </Link>{" "}
                  e toque em “Vender”.
                </>
              )}
            </Vazio>
          ) : (
            <Cartao className="divide-y divide-borda">
              {vendas.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => setAberta(v)}
                  className="flex w-full items-center justify-between gap-4 px-4 py-3.5 text-left hover:bg-gelo/60 sm:px-5"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{v.veiculo.descricao}</span>
                    <span className="block truncate text-sm text-suave">
                      {data(v.data_venda)} · {v.cliente.nome} · {v.vendedor.nome}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className={`num block font-bold ${v.status === "cancelada" ? "text-suave line-through" : ""}`}>
                      {moeda(v.valor)}
                    </span>
                    {v.status === "cancelada" ? (
                      <Etiqueta cor="vermelho">Cancelada</Etiqueta>
                    ) : v.transferencia && ["cobrar", "vencida"].includes(v.transferencia.situacao) ? (
                      <Etiqueta cor={COR_TRANSFERENCIA[v.transferencia.situacao]}>
                        {v.transferencia.situacao === "vencida" ? "Transferência vencida" : "Cobrar transferência"}
                      </Etiqueta>
                    ) : (
                      <span className="text-xs text-suave">{FORMA[v.forma]}</span>
                    )}
                  </span>
                </button>
              ))}
            </Cartao>
          )}
        </>
      )}

      {aberta && (
        <DetalheVenda
          venda={aberta}
          aoFechar={() => setAberta(null)}
          aoMudar={() => mutate()}
          aoTrocar={(nova) => {
            setAberta(nova);
            mutate();
            atualizarAvisos("/avisos");
          }}
        />
      )}
    </>
  );
}
