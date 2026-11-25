"use client";

import { useEffect, useRef, useState } from "react";
import type { VeiculoPublico } from "@/lib/tipos";
import { nomeVeiculo } from "./anuncio";
import { useFocoPreso } from "./foco";

/** Fotos em tela cheia: setas do teclado passam, Esc fecha, o Tab não sai dela e o foco volta para onde estava. */
export function Galeria({
  veiculo,
  inicial = 0,
  aoFechar,
}: {
  veiculo: VeiculoPublico;
  /** foto em que a galeria abre */
  inicial?: number;
  aoFechar: () => void;
}) {
  const [i, setI] = useState(inicial);
  const total = veiculo.fotos.length;
  const caixa = useRef<HTMLDivElement>(null);
  useFocoPreso(caixa);

  // enquanto está aberta a página não rola por baixo
  useEffect(() => {
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = anterior;
    };
  }, []);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") aoFechar();
      if (e.key === "ArrowRight") setI((n) => (n + 1) % total);
      if (e.key === "ArrowLeft") setI((n) => (n - 1 + total) % total);
    };
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [aoFechar, total]);

  return (
    <div
      ref={caixa}
      className="galeria"
      role="dialog"
      aria-modal="true"
      aria-label={`Fotos: ${nomeVeiculo(veiculo)}`}
    >
      <div className="galeria__barra">
        <p className="outdoor galeria__nome">{nomeVeiculo(veiculo)}</p>
        <button type="button" className="botao-redondo" onClick={aoFechar} aria-label="Fechar fotos">
          ✕
        </button>
      </div>
      <div className="galeria__foto">
        {/* eslint-disable-next-line @next/next/no-img-element -- foto já redimensionada pela API */}
        <img src={veiculo.fotos[i].url} alt={`${nomeVeiculo(veiculo)}, foto ${i + 1} de ${total}`} />
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
        <span className="dado galeria__conta" aria-live="polite">
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
