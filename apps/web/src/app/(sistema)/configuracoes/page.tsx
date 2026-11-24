"use client";

import { useState } from "react";
import useSWR from "swr";
import { Exigir } from "@/components/Sessao";
import { Aviso, Botao, Campo, Carregando, Cartao, Titulo, useAcao } from "@/components/ui";
import { api, buscar, mensagemDe } from "@/lib/api";
import { moeda, percentual, percentualParaApi } from "@/lib/formato";
import type { Configuracao } from "@/lib/tipos";

// Só para mostrar a conta na tela; não é dado da loja.
const EXEMPLO = { venda: 14500, compra: 11500 };

function Conteudo() {
  const { data, error, mutate } = useSWR<Configuracao>("/configuracoes", buscar);
  if (error) return <Aviso>{mensagemDe(error)}</Aviso>;
  if (!data) return <Carregando />;
  return <Imposto atual={data.imposto_margem_aliquota} aoSalvar={(nova) => mutate(nova, { revalidate: false })} />;
}

function Imposto({ atual, aoSalvar }: { atual: string; aoSalvar: (nova: Configuracao) => void }) {
  const [aliquota, setAliquota] = useState(() => Number(atual).toLocaleString("pt-BR"));
  const [salvo, setSalvo] = useState(false);
  const { ocupado, erro, executar } = useAcao();

  const paraApi = percentualParaApi(aliquota);
  const invalida = aliquota.trim() !== "" && paraApi === null;
  const margem = EXEMPLO.venda - EXEMPLO.compra;

  function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (paraApi === null) return;
    setSalvo(false);
    executar(async () => {
      aoSalvar(await api<Configuracao>("/configuracoes", { metodo: "PUT", corpo: { imposto_margem_aliquota: paraApi } }));
      setSalvo(true);
    });
  }

  return (
    <>
      <Titulo sobre="Só o dono altera">Configurações</Titulo>
      <Cartao className="max-w-xl p-5 sm:p-6">
        <h2 className="text-lg font-bold">Imposto sobre a margem</h2>
        <p className="mt-1 text-sm text-suave">
          O sistema estima o imposto de cada venda aplicando esta alíquota sobre a margem (valor da venda − valor
          de compra). Use a alíquota informada pelo contador da loja. Com 0, nenhum imposto é calculado.
        </p>
        <form onSubmit={salvar} className="mt-4 space-y-3">
          <Campo
            rotulo="Alíquota (%)"
            inputMode="decimal"
            required
            placeholder="0"
            value={aliquota}
            onChange={(e) => {
              setSalvo(false);
              setAliquota(e.target.value.replace(/[^\d.,]/g, ""));
            }}
          />
          {invalida && <Aviso>Informe um percentual entre 0 e 100, com até duas casas.</Aviso>}
          {paraApi !== null && Number(paraApi) > 0 && (
            <p className="num rounded-xl bg-gelo px-4 py-3 text-sm">
              Exemplo ilustrativo: venda de {moeda(EXEMPLO.venda)} com compra de {moeda(EXEMPLO.compra)} tem margem
              de {moeda(margem)}; a {percentual(paraApi)} o imposto estimado é{" "}
              <b>{moeda((margem * Number(paraApi)) / 100)}</b>.
            </p>
          )}
          <Aviso>{erro}</Aviso>
          {salvo && <Aviso tom="info">Alíquota salva. Vale para as vendas registradas a partir de agora.</Aviso>}
          <Botao type="submit" ocupado={ocupado} disabled={paraApi === null}>
            Salvar alíquota
          </Botao>
        </form>
        <ul className="mt-5 list-disc space-y-1 pl-5 text-xs text-suave">
          <li>É uma estimativa para o lucro líquido; o valor a pagar é o apurado pelo contador.</li>
          <li>Cada venda guarda a alíquota do dia em que foi registrada; mudar aqui não altera vendas antigas.</li>
          <li>Os custos do veículo não entram na base do imposto, e venda com margem negativa não gera imposto.</li>
          <li>A comissão dos vendedores continua calculada sobre o lucro antes do imposto.</li>
        </ul>
      </Cartao>
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="configuracoes.editar">
      <Conteudo />
    </Exigir>
  );
}
