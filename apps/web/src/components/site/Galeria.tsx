"use client";

import { useEffect, useState } from "react";
import type { VeiculoPublico } from "@/lib/tipos";
import { nomeVeiculo } from "./anuncio";

/** Fotos em tela cheia: setas do teclado passam, Esc fecha e o foco volta para onde estava. */
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

  // quem abriu a galeria (lido antes de o botão de fechar puxar o foco)
  const [abriu] = useState(() =>
    typeof document === "undefined" ? null : (document.activeElement as HTMLElement | null),
  );

  // enquanto está aberta a página não rola por baixo; ao fechar, o foco volta para quem abriu
  useEffect(() => {
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = anterior;
      abriu?.focus({ preventScroll: true });
    };
  }, [abriu]);

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
    <div className="galeria" role="dialog" aria-modal="true" aria-label={`Fotos: ${nomeVeiculo(veiculo)}`}>
      <div className="galeria__barra">
        <p className="outdoor galeria__nome">{nomeVeiculo(veiculo)}</p>
        <button type="button" className="botao-redondo" onClick={aoFechar} aria-label="Fechar fotos" autoFocus>
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
        <span className="dado galeria__conta">
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
