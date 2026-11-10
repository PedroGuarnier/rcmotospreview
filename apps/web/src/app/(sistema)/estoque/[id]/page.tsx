"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import useSWR from "swr";
import { ListaEventos } from "@/components/Eventos";
import { Semaforo } from "@/components/placa/Laudo";
import { FormVeiculo } from "@/components/FormVeiculo";
import { Exigir, usePode } from "@/components/Sessao";
import { VenderModal } from "@/components/VenderModal";
import {
  Aviso,
  Botao,
  Campo,
  CampoValor,
  Carregando,
  Cartao,
  Etiqueta,
  Modal,
  Selecao,
  useAcao,
} from "@/components/ui";
import { ErroApi, api, buscar, mensagemDe } from "@/lib/api";
import {
  COR_SITUACAO,
  FORMA,
  SITUACAO,
  SITUACOES_ESTOQUE,
  SITUACOES_VENDIDO,
  TIPO,
  TIPO_CUSTO,
  data,
  hojeIso,
  moeda,
  numero,
  placa,
  valorParaApi,
} from "@/lib/formato";
import type { Evento, Laudo, Situacao, TipoCusto, VeiculoDetalhe } from "@/lib/tipos";

function Dado({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-suave">{rotulo}</dt>
      <dd className="mt-0.5 text-[15px] font-medium">{children}</dd>
    </div>
  );
}

function Secao({ titulo, acoes, children }: { titulo: string; acoes?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Cartao className="p-5 sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold">{titulo}</h2>
        {acoes}
      </div>
      {children}
    </Cartao>
  );
}

function Fotos({ v, aoMudar }: { v: VeiculoDetalhe; aoMudar: (v: VeiculoDetalhe) => void }) {
  const pode = usePode();
  const editar = pode("estoque.editar");
  const entrada = useRef<HTMLInputElement>(null);
  const [aberta, setAberta] = useState<number | null>(null);
  const { ocupado, erro, executar } = useAcao();

  function enviar(arquivos: FileList | null) {
    if (!arquivos?.length) return;
    executar(async () => {
      for (const arquivo of Array.from(arquivos)) {
        aoMudar(await api<VeiculoDetalhe>(`/veiculos/${v.id}/fotos`, { arquivo }));
      }
    }).finally(() => {
      if (entrada.current) entrada.current.value = "";
    });
  }

  const foto = v.fotos.find((f) => f.id === aberta);
  return (
    <Secao
      titulo={`Fotos (${v.fotos.length})`}
      acoes={
        editar && (
          <>
            <input
              ref={entrada}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              hidden
              onChange={(e) => enviar(e.target.files)}
            />
            <Botao tom="neutro" pequeno ocupado={ocupado} onClick={() => entrada.current?.click()}>
              + Adicionar fotos
            </Botao>
          </>
        )
      }
    >
      <Aviso>{erro}</Aviso>
      {v.fotos.length === 0 ? (
        <p className="text-sm text-suave">Nenhuma foto ainda.</p>
      ) : (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
          {v.fotos.map((f, i) => (
            <li key={f.id} className="relative">
              <button
                type="button"
                onClick={() => setAberta(f.id)}
                className="block aspect-square w-full overflow-hidden rounded-xl bg-gelo"
                aria-label={`Abrir foto ${i + 1}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- miniatura já otimizada pela API */}
                <img src={f.miniatura_url} alt="" loading="lazy" className="size-full object-cover" />
              </button>
              {i === 0 && (
                <span className="absolute left-1.5 top-1.5">
                  <Etiqueta sobreFoto cor="amarelo">
                    Capa
                  </Etiqueta>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {foto && (
        <Modal titulo="Foto" aoFechar={() => setAberta(null)} largo>
          {/* eslint-disable-next-line @next/next/no-img-element -- foto servida pela API */}
          <img src={foto.url} alt={v.descricao} className="max-h-[65dvh] w-full rounded-xl object-contain" />
          {editar && (
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              {v.fotos[0]?.id !== foto.id && (
                <Botao
                  tom="neutro"
                  pequeno
                  ocupado={ocupado}
                  onClick={() =>
                    executar(async () => {
                      aoMudar(
                        await api<VeiculoDetalhe>(`/veiculos/${v.id}/fotos/${foto.id}/capa`, { metodo: "POST" }),
                      );
                      setAberta(null);
                    })
                  }
                >
                  Usar como capa
                </Botao>
              )}
              <Botao
                tom="perigo"
                pequeno
                ocupado={ocupado}
                onClick={() =>
                  executar(async () => {
                    aoMudar(await api<VeiculoDetalhe>(`/veiculos/${v.id}/fotos/${foto.id}`, { metodo: "DELETE" }));
                    setAberta(null);
                  })
                }
              >
                Excluir foto
              </Botao>
            </div>
          )}
        </Modal>
      )}
    </Secao>
  );
}

function Custos({ v, aoMudar }: { v: VeiculoDetalhe; aoMudar: (v: VeiculoDetalhe) => void }) {
  const pode = usePode();
  const editar = pode("estoque.editar");
  const [tipo, setTipo] = useState<TipoCusto>("manutencao");
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [dia, setDia] = useState(hojeIso());
  const { ocupado, erro, executar } = useAcao();
  if (v.custos === null) return null;

  function lancar(e: React.FormEvent) {
    e.preventDefault();
    executar(async () => {
      aoMudar(
        await api<VeiculoDetalhe>(`/veiculos/${v.id}/custos`, {
          corpo: { tipo, descricao, valor: valorParaApi(valor), data: dia },
        }),
      );
      setDescricao("");
      setValor("");
    });
  }

  return (
    <Secao titulo="Custos">
      {v.custos.length > 0 && (
        <ul className="mb-4 divide-y divide-borda">
          {v.custos.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium">{c.descricao}</p>
                <p className="text-xs text-suave">
                  {TIPO_CUSTO[c.tipo]} · {data(c.data)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="num font-semibold">{moeda(c.valor)}</span>
                {editar && (
                  <button
                    type="button"
                    aria-label={`Remover custo ${c.descricao}`}
                    disabled={ocupado}
                    onClick={() => {
                      if (!confirm(`Remover o custo "${c.descricao}"?`)) return;
                      executar(async () =>
                        aoMudar(
                          await api<VeiculoDetalhe>(`/veiculos/${v.id}/custos/${c.id}`, { metodo: "DELETE" }),
                        ),
                      );
                    }}
                    className="grid size-8 place-items-center rounded-full text-suave hover:bg-vermelho/10 hover:text-vermelho"
                  >
                    ×
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <dl className="num space-y-1 rounded-xl bg-gelo px-4 py-3 text-sm">
        <div className="flex justify-between">
          <dt>Valor de compra</dt>
          <dd>{moeda(v.valor_compra)}</dd>
        </div>
        <div className="flex justify-between">
          <dt>Custos</dt>
          <dd>{moeda(v.total_custos)}</dd>
        </div>
        <div className="flex justify-between border-t border-borda pt-1 font-bold">
          <dt>Investido no veículo</dt>
          <dd>{moeda(v.custo_total)}</dd>
        </div>
        {v.venda?.lucro != null ? (
          <div className="flex justify-between font-bold">
            <dt>Lucro da venda</dt>
            <dd className={Number(v.venda.lucro) < 0 ? "text-vermelho" : "text-verde"}>{moeda(v.venda.lucro)}</dd>
          </div>
        ) : (
          v.lucro_previsto !== null && (
            <div className="flex justify-between font-bold">
              <dt>Lucro previsto (no preço anunciado)</dt>
              <dd className={Number(v.lucro_previsto) < 0 ? "text-vermelho" : "text-verde"}>
                {moeda(v.lucro_previsto)}
              </dd>
            </div>
          )
        )}
      </dl>

      {editar && (
        <form onSubmit={lancar} className="mt-5 space-y-3 border-t border-borda pt-5">
          <h3 className="text-sm font-bold">Lançar custo</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <Selecao
              rotulo="Tipo"
              valor={tipo}
              aoMudar={setTipo}
              opcoes={(Object.keys(TIPO_CUSTO) as TipoCusto[]).map((t) => ({ valor: t, rotulo: TIPO_CUSTO[t] }))}
            />
            <Campo
              rotulo="Descrição"
              placeholder="Ex.: troca de óleo"
              required
              maxLength={200}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
            />
            <CampoValor rotulo="Valor" valor={valor} aoMudar={setValor} required />
            <Campo
              rotulo="Data"
              type="date"
              required
              max={hojeIso()}
              value={dia}
              onChange={(e) => setDia(e.target.value)}
            />
          </div>
          <Aviso>{erro}</Aviso>
          <Botao type="submit" tom="neutro" ocupado={ocupado}>
            Lançar custo
          </Botao>
        </form>
      )}
    </Secao>
  );
}

const SINAL = { verde: "Nada consta", amarelo: "Ponto de atenção", vermelho: "Restrição encontrada" } as const;
const COR_ITEM = { ok: "bg-verde", atencao: "bg-amarelo-escuro", alerta: "bg-vermelho" } as const;

function Procedencia({ v }: { v: VeiculoDetalhe }) {
  const pode = usePode();
  const { data: laudos } = useSWR<Laudo[]>(`/veiculos/${v.id}/laudos`, buscar);
  const ultimo = laudos?.[0];
  return (
    <Secao
      titulo="Procedência"
      acoes={
        pode("procedencia.consultar") &&
        v.placa && (
          <Link
            href={`/procedencia?placa=${v.placa}`}
            className="inline-flex min-h-9 items-center rounded-full border border-borda bg-white px-3.5 text-sm font-semibold hover:border-azul"
          >
            {ultimo ? "Consultar de novo" : "Consultar pela placa"}
          </Link>
        )
      }
    >
      {!laudos ? (
        <Carregando />
      ) : !ultimo ? (
        <p className="text-sm text-suave">
          {v.placa ? "Nenhuma consulta feita para esta placa." : "Cadastre a placa para consultar a procedência."}
        </p>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <Semaforo cor={ultimo.semaforo} deitado tamanho="1.1rem" />
            <p>
              <b>{SINAL[ultimo.semaforo]}</b>
              <span className="text-sm text-suave">
                {" "}
                · {data(ultimo.criado_em)}
                {ultimo.consultado_por && ` · ${ultimo.consultado_por}`}
              </span>
              {ultimo.ilustrativo && (
                <span className="ml-2">
                  <Etiqueta cor="amarelo">Ilustrativo</Etiqueta>
                </span>
              )}
            </p>
          </div>
          <ul className="mt-3 divide-y divide-borda text-sm">
            {ultimo.itens.map((item) => (
              <li key={item.chave} className="flex items-start gap-3 py-2">
                <i aria-hidden className={`mt-1.5 size-2.5 shrink-0 rounded-full ${COR_ITEM[item.situacao]}`} />
                <span>
                  <b>{item.titulo}</b>
                  <span className="block text-suave">{item.detalhe}</span>
                </span>
              </li>
            ))}
          </ul>
          {laudos.length > 1 && (
            <p className="mt-2 text-xs text-suave">{laudos.length} consultas guardadas para este veículo.</p>
          )}
        </>
      )}
    </Secao>
  );
}

function Veiculo() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pode = usePode();
  const { data: v, error, mutate } = useSWR<VeiculoDetalhe>(`/veiculos/${id}`, buscar);
  const verHistorico = pode("historico.veiculo_ver");
  const { data: eventos, mutate: recarregarHistorico } = useSWR<Evento[]>(
    verHistorico ? `/veiculos/${id}/historico` : null,
    buscar,
  );
  const [editando, setEditando] = useState(false);
  const [vendendo, setVendendo] = useState(false);
  const situacao = useAcao();

  if (error) {
    return (
      <Aviso>
        {error instanceof ErroApi && error.status === 404 ? "Veículo não encontrado." : mensagemDe(error)}
      </Aviso>
    );
  }
  if (!v) return <Carregando />;

  const atualizar = (novo: VeiculoDetalhe) => {
    mutate(novo, { revalidate: false });
    recarregarHistorico();
  };
  const editar = pode("estoque.editar");
  const etapas = v.venda ? SITUACOES_VENDIDO : SITUACOES_ESTOQUE;

  function mudarSituacao(nova: Situacao) {
    situacao.executar(async () =>
      atualizar(await api<VeiculoDetalhe>(`/veiculos/${v!.id}`, { metodo: "PATCH", corpo: { situacao: nova } })),
    );
  }

  function excluir() {
    if (!confirm(`Excluir ${v!.descricao}? Esta ação não pode ser desfeita.`)) return;
    situacao.executar(async () => {
      await api(`/veiculos/${v!.id}`, { metodo: "DELETE" });
      router.replace("/estoque");
    });
  }

  return (
    <>
      <Link href="/estoque" className="mb-4 inline-block text-sm font-semibold text-azul hover:underline">
        ‹ Estoque
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Etiqueta cor={COR_SITUACAO[v.situacao]}>{SITUACAO[v.situacao]}</Etiqueta>
            <span className="text-xs text-suave">
              há {v.dias_na_situacao} {v.dias_na_situacao === 1 ? "dia" : "dias"} nesta etapa
            </span>
          </div>
          <h1 className="display text-3xl leading-tight sm:text-4xl">
            {v.marca} {v.modelo}
          </h1>
          <p className="num mt-1 text-2xl font-bold text-azul">
            {v.preco_venda ? moeda(v.preco_venda) : "Sem preço de venda"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {editar && (
            <Botao tom="neutro" onClick={() => setEditando(true)}>
              Editar
            </Botao>
          )}
          {v.situacao === "a_venda" && pode("vendas.registrar") && (
            <Botao tom="amarelo" onClick={() => setVendendo(true)}>
              Vender
            </Botao>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {v.venda && (
          <Cartao className="border-verde/30 bg-verde/5 p-5">
            <p className="text-sm">
              <b>Vendido em {data(v.venda.data_venda)}</b> para {v.venda.cliente.nome} por{" "}
              <b className="num">{moeda(v.venda.valor)}</b> ({FORMA[v.venda.forma].toLowerCase()}) — vendedor:{" "}
              {v.venda.vendedor.nome}.{" "}
              <Link href="/vendas" className="font-semibold text-azul hover:underline">
                Ver vendas
              </Link>
            </p>
          </Cartao>
        )}

        {editar && (
          <Secao titulo="Etapa do veículo">
            <div className="flex flex-wrap gap-2">
              {etapas.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={situacao.ocupado || s === v.situacao || s === "vendido"}
                  aria-pressed={s === v.situacao}
                  onClick={() => mudarSituacao(s)}
                  className={`min-h-10 rounded-full border px-4 text-sm font-semibold transition-colors ${
                    s === v.situacao
                      ? "border-azul bg-azul text-white"
                      : "border-borda bg-white hover:border-azul disabled:opacity-50"
                  }`}
                >
                  {SITUACAO[s]}
                </button>
              ))}
            </div>
            <div className="mt-3">
              <Aviso>{situacao.erro}</Aviso>
            </div>
          </Secao>
        )}

        <Fotos v={v} aoMudar={atualizar} />

        <Secao titulo="Dados do veículo">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4">
            <Dado rotulo="Tipo">{TIPO[v.tipo]}</Dado>
            <Dado rotulo="Ano">
              {v.ano_fabricacao ?? "—"}/{v.ano_modelo ?? "—"}
            </Dado>
            <Dado rotulo="Cor">{v.cor ?? "—"}</Dado>
            <Dado rotulo="Km">{numero(v.km)}</Dado>
            <Dado rotulo="Placa">{placa(v.placa)}</Dado>
            <Dado rotulo="Chassi">{v.chassi ?? "—"}</Dado>
            <Dado rotulo="RENAVAM">{v.renavam ?? "—"}</Dado>
            <Dado rotulo="Data da compra">{data(v.data_compra)}</Dado>
          </dl>
          {v.observacoes && <p className="mt-4 whitespace-pre-line text-sm text-suave">{v.observacoes}</p>}
        </Secao>

        <Procedencia v={v} />

        <Custos v={v} aoMudar={atualizar} />

        {verHistorico && (
          <Secao titulo="Histórico do veículo">
            {!eventos ? <Carregando /> : <ListaEventos eventos={eventos} />}
          </Secao>
        )}

        {pode("usuarios.gerir") && !v.venda && (
          <div className="text-right">
            <Botao tom="perigo" pequeno onClick={excluir} disabled={situacao.ocupado}>
              Excluir veículo
            </Botao>
          </div>
        )}
      </div>

      {editando && (
        <Modal titulo="Editar veículo" aoFechar={() => setEditando(false)} largo>
          <FormVeiculo
            veiculo={v}
            aoCancelar={() => setEditando(false)}
            aoSalvar={(novo) => {
              atualizar(novo);
              setEditando(false);
            }}
          />
        </Modal>
      )}
      {vendendo && (
        <VenderModal
          veiculo={v}
          aoFechar={() => setVendendo(false)}
          aoVender={() => {
            setVendendo(false);
            mutate();
            recarregarHistorico();
          }}
        />
      )}
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="estoque.ver">
      <Veiculo />
    </Exigir>
  );
}
