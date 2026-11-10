"use client";

import { useEffect, useState } from "react";
import { Semaforo } from "@/components/placa/Laudo";
import { numero } from "@/lib/formato";
import type { TipoVeiculo, VeiculoPublico } from "@/lib/tipos";

const LAUDO = {
  verde: "Laudo: nada consta",
  amarelo: "Laudo: ponto de atenção",
  vermelho: "Laudo: restrição",
} as const;

function Preco({ valor }: { valor: string }) {
  const [inteiro] = Number(valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 }).split(",");
  return (
    <p className="anuncio__preco">
      <small>R$</small>
      {inteiro}
    </p>
  );
}

function Galeria({ veiculo, aoFechar }: { veiculo: VeiculoPublico; aoFechar: () => void }) {
  const [i, setI] = useState(0);
  const total = veiculo.fotos.length;

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") aoFechar();
      if (e.key === "ArrowRight") setI((n) => (n + 1) % total);
      if (e.key === "ArrowLeft") setI((n) => (n - 1 + total) % total);
    };
    document.addEventListener("keydown", tecla);
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tecla);
      document.body.style.overflow = anterior;
    };
  }, [aoFechar, total]);

  return (
    <div className="galeria" role="dialog" aria-modal="true" aria-label={`Fotos: ${veiculo.marca} ${veiculo.modelo}`}>
      <div className="galeria__barra">
        <p className="outdoor" style={{ fontSize: "1.6rem" }}>
          {veiculo.marca} {veiculo.modelo}
        </p>
        <button type="button" className="botao-redondo" onClick={aoFechar} aria-label="Fechar fotos" autoFocus>
          ✕
        </button>
      </div>
      <div className="galeria__foto">
        {/* eslint-disable-next-line @next/next/no-img-element -- foto já otimizada pela API */}
        <img src={veiculo.fotos[i].url} alt={`${veiculo.marca} ${veiculo.modelo}, foto ${i + 1} de ${total}`} />
      </div>
      <div className="galeria__nav">
        <button
          type="button"
          className="botao-redondo"
          onClick={() => setI((n) => (n - 1 + total) % total)}
          aria-label="Foto anterior"
          disabled={total < 2}
        >
          ←
        </button>
        <span className="dado" style={{ fontSize: "0.8rem" }}>
          {i + 1} / {total}
        </span>
        <button
          type="button"
          className="botao-redondo"
          onClick={() => setI((n) => (n + 1) % total)}
          aria-label="Próxima foto"
          disabled={total < 2}
        >
          →
        </button>
      </div>
    </div>
  );
}

export function Vitrine({
  veiculos,
  ilustrativo,
  linkVeiculo,
  linkLoja,
  aoVerLaudo,
}: {
  veiculos: VeiculoPublico[];
  ilustrativo: boolean;
  linkVeiculo: (v: VeiculoPublico) => string;
  linkLoja: string;
  aoVerLaudo: (v: VeiculoPublico) => void;
}) {
  const [tipo, setTipo] = useState<TipoVeiculo | "">("");
  const [fotos, setFotos] = useState<VeiculoPublico | null>(null);
  const temMoto = veiculos.some((v) => v.tipo === "moto");
  const temCarro = veiculos.some((v) => v.tipo === "carro");
  const lista = tipo ? veiculos.filter((v) => v.tipo === tipo) : veiculos;

  return (
    <section id="vitrine" className="claro vitrine" aria-labelledby="titulo-vitrine">
      <div className="vitrine__cabeca">
        <div>
          <p className="sobretitulo" data-revelar>
            <span className="barras" aria-hidden>
              <i />
              <i />
              <i />
            </span>
            Vitrine ligada ao estoque
          </p>
          <h2 id="titulo-vitrine" className="outdoor vitrine__titulo" data-revelar>
            Na loja <em>agora.</em>
          </h2>
        </div>
        {temMoto && temCarro && (
          <div className="vitrine__filtros" role="group" aria-label="Filtrar vitrine" data-revelar>
            {(
              [
                ["", `Tudo · ${veiculos.length}`],
                ["moto", "Motos"],
                ["carro", "Carros"],
              ] as const
            ).map(([valor, rotulo]) => (
              <button
                key={valor}
                type="button"
                className="filtro"
                aria-pressed={tipo === valor}
                onClick={() => setTipo(valor)}
              >
                {rotulo}
              </button>
            ))}
          </div>
        )}
      </div>

      {veiculos.length === 0 ? (
        <div className="vitrine__vazia" data-revelar>
          <p>
            A vitrine está sendo atualizada neste momento. Chame a loja e a gente diz o que tem no pátio hoje.
          </p>
          <a className="acao acao--tinta" href={linkLoja} target="_blank" rel="noopener" style={{ marginTop: "1.5rem" }}>
            Perguntar no WhatsApp
          </a>
        </div>
      ) : (
        <div>
          {lista.map((v, i) => (
            <article key={v.id} className="anuncio" data-revelar>
              <p className="dado anuncio__num" aria-hidden>
                {String(i + 1).padStart(2, "0")}
              </p>

              {v.fotos.length > 0 ? (
                <button
                  type="button"
                  className="anuncio__midia"
                  onClick={() => setFotos(v)}
                  aria-label={`Ver ${v.fotos.length} ${v.fotos.length === 1 ? "foto" : "fotos"} de ${v.marca} ${v.modelo}`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element -- miniatura já otimizada pela API */}
                  <img src={v.fotos[0].url} alt="" loading="lazy" />
                  {v.fotos.length > 1 && <span className="dado anuncio__conta">{v.fotos.length} fotos</span>}
                </button>
              ) : (
                <div className="anuncio__midia" style={{ cursor: "default" }} aria-hidden>
                  <span className="anuncio__poster">
                    <b>{v.marca}</b>
                    <small className="dado">Fotos em breve</small>
                  </span>
                </div>
              )}

              <div>
                <h3 className="outdoor anuncio__nome">
                  {v.marca} {v.modelo}
                </h3>
                <p className="dado anuncio__ficha">
                  {v.ano_modelo && (
                    <span>
                      {v.ano_fabricacao && v.ano_fabricacao !== v.ano_modelo ? `${v.ano_fabricacao}/` : ""}
                      {v.ano_modelo}
                    </span>
                  )}
                  {v.km !== null && <span>{numero(v.km)} km</span>}
                  {v.cor && <span>{v.cor}</span>}
                  {v.placa_mascarada && <span>Placa {v.placa_mascarada}</span>}
                </p>
                <div className="anuncio__selos">
                  {v.semaforo && (
                    <button type="button" className="selo" onClick={() => aoVerLaudo(v)}>
                      <Semaforo cor={v.semaforo} deitado tamanho="0.72rem" />
                      {LAUDO[v.semaforo]}
                    </button>
                  )}
                  {v.dias_na_loja <= 7 && <span className="selo selo--novo">Chegou esta semana</span>}
                </div>
              </div>

              <div className="anuncio__fecho">
                <Preco valor={v.preco} />
                <div className="anuncio__acoes">
                  <a className="acao acao--tinta" href={linkVeiculo(v)} target="_blank" rel="noopener">
                    Quero essa
                  </a>
                  <button type="button" className="acao acao--linha acao--sem-seta" onClick={() => aoVerLaudo(v)}>
                    Ver procedência
                  </button>
                </div>
              </div>
            </article>
          ))}
          {ilustrativo && (
            <p className="dado vitrine__nota">Ambiente de demonstração: veículos, preços e laudos ilustrativos.</p>
          )}
        </div>
      )}

      {fotos && <Galeria veiculo={fotos} aoFechar={() => setFotos(null)} />}
    </section>
  );
}
