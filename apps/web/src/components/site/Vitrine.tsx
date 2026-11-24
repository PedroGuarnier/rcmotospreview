"use client";

import { useEffect, useRef, useState } from "react";
import type { TipoVeiculo, VeiculoPublico } from "@/lib/tipos";
import { ORDENS, type Ordem, semAcento } from "./anuncio";
import { Cartao } from "./Cartao";
import { Barras } from "./pecas";

const POR_VEZ = 12;

function IconeLupa() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.5 15.5 5 5" />
    </svg>
  );
}

/** A vitrine: grade de produtos igual ao estoque, com filtro por tipo, ordem e busca. */
export function Vitrine({
  veiculos,
  ilustrativo,
  whatsapp,
  linkLoja,
  tipo,
  aoMudarTipo,
  ordemInicial = "recentes",
  buscaInicial = "",
}: {
  veiculos: VeiculoPublico[];
  ilustrativo: boolean;
  whatsapp: string | null;
  linkLoja: string;
  /** o filtro de tipo mora na página: os atalhos da primeira dobra também mexem nele */
  tipo: TipoVeiculo | "";
  aoMudarTipo: (tipo: TipoVeiculo | "") => void;
  ordemInicial?: Ordem;
  buscaInicial?: string;
}) {
  const [ordem, setOrdem] = useState<Ordem>(ordemInicial);
  const [busca, setBusca] = useState(buscaInicial);
  const [limite, setLimite] = useState(POR_VEZ);

  const motos = veiculos.filter((v) => v.tipo === "moto").length;
  const carros = veiculos.length - motos;

  const termos = semAcento(busca).split(/\s+/).filter(Boolean);
  let lista = veiculos.filter((v) => {
    if (tipo && v.tipo !== tipo) return false;
    const texto = semAcento(`${v.marca} ${v.modelo} ${v.ano_modelo ?? ""}`);
    return termos.every((termo) => texto.includes(termo));
  });
  if (ordem !== "recentes") {
    const sentido = ordem === "menor" ? 1 : -1;
    lista = [...lista].sort((a, b) => sentido * (Number(a.preco) - Number(b.preco)));
  }
  const visiveis = lista.slice(0, limite);
  const filtrando = tipo !== "" || termos.length > 0;

  // Os filtros viajam no endereço: voltar de um anúncio (ou mandar o link) abre a vitrine igual.
  // Sem a âncora, para o "voltar" devolver a rolagem onde estava e não o topo da seção.
  const gravado = useRef({ tipo, ordem, busca });
  useEffect(() => {
    const antes = gravado.current;
    // Só quando um filtro muda de verdade: ao montar, o histórico ainda é do roteador.
    if (antes.tipo === tipo && antes.ordem === ordem && antes.busca === busca) return;
    gravado.current = { tipo, ordem, busca };
    const consulta = new URLSearchParams(window.location.search);
    const por = (nome: string, valor: string) => (valor ? consulta.set(nome, valor) : consulta.delete(nome));
    por("tipo", tipo);
    por("ordem", ordem === "recentes" ? "" : ordem);
    por("busca", busca.trim());
    const texto = consulta.toString();
    try {
      window.history.replaceState(null, "", `${window.location.pathname}${texto ? `?${texto}` : ""}`);
    } catch {
      // alguns navegadores limitam trocas de endereço seguidas; o filtro funciona do mesmo jeito
    }
  }, [tipo, ordem, busca]);

  function limpar() {
    aoMudarTipo("");
    setBusca("");
    setLimite(POR_VEZ);
  }

  const filtros: [TipoVeiculo | "", string, number][] = [
    ["", "Tudo", veiculos.length],
    ["moto", "Motos", motos],
    ["carro", "Carros", carros],
  ];

  return (
    <section id="vitrine" className="claro vitrine" aria-labelledby="titulo-vitrine">
      <div className="vitrine__cabeca">
        <p className="sobretitulo" data-revelar>
          <Barras /> Vitrine
        </p>
        <h2 id="titulo-vitrine" className="outdoor vitrine__titulo" data-revelar>
          Na loja <em>agora.</em>
        </h2>
      </div>

      {veiculos.length === 0 ? (
        <div className="vitrine__vazia" data-revelar>
          <p>A vitrine está sendo atualizada neste momento. Chame a loja e a gente diz o que tem no pátio hoje.</p>
          <a className="acao acao--tinta" href={linkLoja} target="_blank" rel="noopener">
            Perguntar no WhatsApp
          </a>
        </div>
      ) : (
        <>
          {veiculos.length > 1 && (
            <div className="vitrine__barra">
              {motos > 0 && carros > 0 && (
                <div className="vitrine__filtros" role="group" aria-label="Filtrar por tipo">
                  {filtros.map(([valor, rotulo, quantos]) => (
                    <button
                      key={valor}
                      type="button"
                      className="filtro"
                      aria-pressed={tipo === valor}
                      onClick={() => {
                        aoMudarTipo(valor);
                        setLimite(POR_VEZ);
                      }}
                    >
                      {rotulo} <span>{quantos}</span>
                    </button>
                  ))}
                </div>
              )}
              <div className="vitrine__campos">
                <label className="campo campo--busca">
                  <span className="so-leitor">Buscar por marca ou modelo</span>
                  <IconeLupa />
                  <input
                    type="search"
                    placeholder="Buscar marca ou modelo"
                    autoComplete="off"
                    enterKeyHint="search"
                    value={busca}
                    onChange={(e) => {
                      setBusca(e.target.value);
                      setLimite(POR_VEZ);
                    }}
                  />
                </label>
                <label className="campo campo--ordem">
                  <span className="dado">Ordenar</span>
                  <select value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
                    {ORDENS.map((o) => (
                      <option key={o.valor} value={o.valor}>
                        {o.rotulo}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          )}

          <p className="dado vitrine__conta" role="status">
            {filtrando
              ? `${lista.length} de ${veiculos.length} ${veiculos.length === 1 ? "veículo" : "veículos"}`
              : `${veiculos.length} ${veiculos.length === 1 ? "veículo" : "veículos"}`}
            {filtrando && (
              <button type="button" onClick={limpar}>
                Limpar filtros
              </button>
            )}
          </p>

          {lista.length === 0 ? (
            <div className="vitrine__vazia">
              <p>
                Nada encontrado com esse filtro. Pode ser que o veículo que você procura esteja chegando — pergunte à
                loja.
              </p>
              <div className="vitrine__vazia-acoes">
                <button type="button" className="acao acao--tinta acao--sem-seta" onClick={limpar}>
                  Limpar filtros
                </button>
                <a className="acao acao--linha" href={linkLoja} target="_blank" rel="noopener">
                  Perguntar no WhatsApp
                </a>
              </div>
            </div>
          ) : (
            <div className="grade">
              {visiveis.map((v, i) => (
                <Cartao key={v.id} veiculo={v} whatsapp={whatsapp} ordem={i % POR_VEZ} />
              ))}
            </div>
          )}

          {lista.length > limite && (
            <div className="vitrine__mais">
              <button type="button" className="acao acao--linha acao--sem-seta" onClick={() => setLimite(limite + POR_VEZ)}>
                Mostrar mais {Math.min(POR_VEZ, lista.length - limite)}
              </button>
              <p className="dado">
                {visiveis.length} de {lista.length}
              </p>
            </div>
          )}

          {ilustrativo && (
            <p className="dado vitrine__nota">Ambiente de demonstração: veículos, preços e laudos ilustrativos.</p>
          )}
        </>
      )}
    </section>
  );
}
