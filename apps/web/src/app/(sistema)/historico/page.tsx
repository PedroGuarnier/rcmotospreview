"use client";

import { useState } from "react";
import useSWRInfinite from "swr/infinite";
import { ListaEventos } from "@/components/Eventos";
import { Exigir } from "@/components/Sessao";
import { Aviso, Botao, Carregando, Cartao, Selecao, Titulo, Vazio } from "@/components/ui";
import { buscar, mensagemDe } from "@/lib/api";
import type { Evento } from "@/lib/tipos";

const LIMITE = 50;
const ENTIDADES = [
  { valor: "", rotulo: "Tudo" },
  { valor: "veiculo", rotulo: "Veículos" },
  { valor: "custo", rotulo: "Custos" },
  { valor: "venda", rotulo: "Vendas" },
  { valor: "laudo", rotulo: "Procedência" },
  { valor: "comissao", rotulo: "Comissões" },
  { valor: "cliente", rotulo: "Clientes" },
  { valor: "aporte", rotulo: "Aportes" },
  { valor: "usuario", rotulo: "Equipe" },
  { valor: "sessao", rotulo: "Entradas no sistema" },
];

function Conteudo() {
  const [entidade, setEntidade] = useState("");
  const { data, error, size, setSize, isValidating } = useSWRInfinite<Evento[]>(
    (indice, anterior: Evento[] | null) => {
      if (anterior && anterior.length < LIMITE) return null;
      const params = new URLSearchParams({ limite: String(LIMITE) });
      if (entidade) params.set("entidade", entidade);
      if (indice > 0 && anterior) params.set("antes_de", String(anterior[anterior.length - 1].id));
      return `/historico?${params}`;
    },
    buscar,
    { revalidateFirstPage: false },
  );
  const eventos = data?.flat() ?? [];
  const temMais = data !== undefined && data[data.length - 1]?.length === LIMITE;

  return (
    <>
      <Titulo sobre="Quem fez o quê, e quando">Histórico</Titulo>
      <div className="mb-4 max-w-xs">
        <Selecao rotulo="Mostrar" valor={entidade} aoMudar={setEntidade} opcoes={ENTIDADES} />
      </div>
      {error && <Aviso>{mensagemDe(error)}</Aviso>}
      {!data && !error && <Carregando />}
      {data && eventos.length === 0 && <Vazio>Nada registrado ainda.</Vazio>}
      {eventos.length > 0 && (
        <Cartao className="px-5 py-2">
          <ListaEventos eventos={eventos} />
        </Cartao>
      )}
      {temMais && (
        <div className="mt-4 text-center">
          <Botao tom="neutro" ocupado={isValidating} onClick={() => setSize(size + 1)}>
            Carregar mais
          </Botao>
        </div>
      )}
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="historico.ver">
      <Conteudo />
    </Exigir>
  );
}
