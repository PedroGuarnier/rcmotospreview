"use client";

import { useState } from "react";
import useSWR from "swr";
import { Exigir, usePode } from "@/components/Sessao";
import { Aviso, Botao, Campo, CampoValor, Carregando, Cartao, Titulo, Vazio, useAcao } from "@/components/ui";
import { api, buscar, mensagemDe } from "@/lib/api";
import { data, hojeIso, moeda, valorParaApi } from "@/lib/formato";
import type { Aportes } from "@/lib/tipos";

function Conteudo() {
  const pode = usePode();
  const { data: aportes, error, mutate } = useSWR<Aportes>("/aportes", buscar);
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [dia, setDia] = useState(hojeIso());
  const { ocupado, erro, executar } = useAcao();

  function lancar(e: React.FormEvent) {
    e.preventDefault();
    executar(async () => {
      await api("/aportes", { corpo: { descricao, valor: valorParaApi(valor), data: dia } });
      setDescricao("");
      setValor("");
      await mutate();
    });
  }

  return (
    <>
      <Titulo sobre="Gastos pessoais investidos na loja">Aportes</Titulo>
      <p className="-mt-3 mb-5 text-sm text-suave">
        Só o dono e quem ele habilitar enxergam esta página.
      </p>

      <Cartao className="mb-4 p-5 sm:p-6">
        <form onSubmit={lancar} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">
            <Campo
              rotulo="Descrição"
              placeholder="Ex.: capital de giro"
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
          <Botao type="submit" ocupado={ocupado}>
            Lançar aporte
          </Botao>
        </form>
      </Cartao>

      {error && <Aviso>{mensagemDe(error)}</Aviso>}
      {!aportes && !error && <Carregando />}
      {aportes && aportes.itens.length === 0 && <Vazio>Nenhum aporte lançado.</Vazio>}
      {aportes && aportes.itens.length > 0 && (
        <Cartao>
          <p className="num border-b border-borda px-5 py-4 text-sm">
            Total investido: <b className="text-lg">{moeda(aportes.total)}</b>
          </p>
          <ul className="divide-y divide-borda">
            {aportes.itens.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium">{a.descricao}</p>
                  <p className="text-xs text-suave">
                    {data(a.data)}
                    {a.registrado_por && ` · lançado por ${a.registrado_por}`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <b className="num">{moeda(a.valor)}</b>
                  {pode("usuarios.gerir") && (
                    <button
                      type="button"
                      aria-label={`Excluir aporte ${a.descricao}`}
                      disabled={ocupado}
                      onClick={() => {
                        if (!confirm(`Excluir o aporte "${a.descricao}"?`)) return;
                        executar(async () => {
                          await api(`/aportes/${a.id}`, { metodo: "DELETE" });
                          await mutate();
                        });
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
        </Cartao>
      )}
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="aportes.ver">
      <Conteudo />
    </Exigir>
  );
}
