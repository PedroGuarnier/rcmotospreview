"use client";

import { useEffect, useRef, useState } from "react";
import "./placa.css";

export type FormatoPlaca = "carro" | "moto";
export type EstadoPlaca = "livre" | "consultando" | "pronta";

const LETRA = /[A-Z]/;
const NUMERO = /[0-9]/;
export const OCULTO = "•";

/** Padrão Mercosul (ABC1D23) e antigo (ABC1234): o que cada posição aceita. */
function aceita(posicao: number, c: string): boolean {
  if (posicao <= 2) return LETRA.test(c);
  if (posicao === 4) return LETRA.test(c) || NUMERO.test(c);
  return NUMERO.test(c);
}

const DICA = ["letra", "letra", "letra", "número", "letra ou número", "número", "número"];
const FANTASMA = ["A", "B", "C", "1", "D", "2", "3"];

/** Filtra o que foi digitado: devolve só o que cabe em cada posição e onde foi recusado. */
export function filtrarPlaca(texto: string): { valor: string; recusada: number | null } {
  let valor = "";
  let recusada: number | null = null;
  for (const bruto of texto.toUpperCase()) {
    if (valor.length >= 7) break;
    if (!/[A-Z0-9]/.test(bruto)) continue; // hífen, espaço…
    if (aceita(valor.length, bruto)) valor += bruto;
    else if (recusada === null) recusada = valor.length;
  }
  return { valor, recusada };
}

export const placaCompleta = (valor: string) => valor.length === 7;

function Emblema() {
  // Emblema do Mercosul, simplificado: quatro estrelas sobre o horizonte
  return (
    <svg className="placa__emblema" viewBox="0 0 30 20" aria-hidden>
      <rect width="30" height="20" rx="2" fill="#0b3a9e" />
      <path d="M4 15c6-4 16-4 22 0" fill="none" stroke="#3aa655" strokeWidth="2.2" strokeLinecap="round" />
      {[
        [8, 9],
        [13, 5.5],
        [18.5, 5.5],
        [23, 9],
      ].map(([x, y]) => (
        <circle key={x} cx={x} cy={y} r="1.35" fill="#fff" />
      ))}
    </svg>
  );
}

function Bandeira() {
  return (
    <svg className="placa__bandeira" viewBox="0 0 28 20" aria-hidden>
      <rect width="28" height="20" fill="#1f9b4d" />
      <path d="M14 2.6 25 10 14 17.4 3 10z" fill="#f6d21b" />
      <circle cx="14" cy="10" r="4.3" fill="#1b3f9c" />
      <path d="M9.9 9.2c3-.9 6-.2 8.3 1.7" fill="none" stroke="#fff" strokeWidth="0.9" />
    </svg>
  );
}

/**
 * A placa nacional (padrão Mercosul), em formato de carro ou de moto (duas linhas).
 *
 * Com `aoMudar`, é um campo de verdade: há um <input> por cima da chapa, então teclado do
 * celular, colar, leitor de tela e Enter funcionam como em qualquer campo. Sem `aoMudar`,
 * é só exibição (aceita "•" para caractere protegido).
 */
export function PlacaMercosul({
  valor,
  formato,
  aoMudar,
  aoConfirmar,
  estado = "livre",
  rotulo = "Placa do veículo",
  autoFoco,
  transicao,
  inclinar = true,
}: {
  valor: string;
  formato: FormatoPlaca;
  aoMudar?: (valor: string) => void;
  aoConfirmar?: () => void;
  estado?: EstadoPlaca;
  rotulo?: string;
  autoFoco?: boolean;
  /** dá nome a cada caractere para a troca carro ⇄ moto animar (use em uma placa por página) */
  transicao?: boolean;
  inclinar?: boolean;
}) {
  const placa = useRef<HTMLDivElement>(null);
  const entrada = useRef<HTMLInputElement>(null);
  const [erro, setErro] = useState<number | null>(null);
  const [focada, setFocada] = useState(false);
  const editavel = Boolean(aoMudar) && estado !== "consultando";

  useEffect(() => {
    if (erro === null) return;
    const t = setTimeout(() => setErro(null), 1400);
    return () => clearTimeout(t);
  }, [erro]);

  useEffect(() => {
    if (autoFoco) entrada.current?.focus({ preventScroll: true });
  }, [autoFoco]);

  function bater() {
    // pequena "pancada" da prensa a cada caractere
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    placa.current
      ?.querySelector(".placa__chapa")
      ?.animate([{ scale: "1" }, { scale: "0.985" }, { scale: "1" }], { duration: 140, easing: "ease-out" });
  }

  function digitar(texto: string) {
    const { valor: novo, recusada } = filtrarPlaca(texto);
    setErro(recusada);
    if (novo.length > valor.length) bater();
    aoMudar?.(novo);
  }

  function mover(e: React.PointerEvent) {
    if (!inclinar || e.pointerType !== "mouse" || !placa.current) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = placa.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    placa.current.style.setProperty("--inclina-y", `${(x * 9).toFixed(2)}deg`);
    placa.current.style.setProperty("--inclina-x", `${(-y * 7).toFixed(2)}deg`);
  }
  function soltar() {
    placa.current?.style.setProperty("--inclina-y", "0deg");
    placa.current?.style.setProperty("--inclina-x", "0deg");
  }

  const caracteres = Array.from({ length: 7 }, (_, i) => valor[i] ?? "");

  return (
    <div className="placa-palco" onPointerMove={mover} onPointerLeave={soltar}>
      <div ref={placa} className="placa" data-formato={formato} data-estado={estado}>
        <div className="placa__chapa">
          <div className="placa__faixa">
            <Emblema />
            <span className="placa__brasil">BRASIL</span>
            <Bandeira />
          </div>
          <div className="placa__corpo">
            <span className="placa__br" aria-hidden>
              <i className="placa__qr" />
              BR
            </span>
            <div className="placa__chars" aria-hidden>
              {caracteres.map((c, i) => {
                const estadoChar =
                  c === OCULTO ? "oculto" : c ? "cheio" : editavel && focada && i === valor.length ? "cursor" : "vazio";
                return (
                  <span
                    // a chave muda quando o caractere muda: a animação de estampar roda de novo
                    key={`${i}-${c}`}
                    className="placa__char"
                    data-estado={estadoChar}
                    data-erro={erro === i}
                    style={{
                      "--i": i,
                      ...(transicao ? { viewTransitionName: `placa-c${i}` } : null),
                    } as React.CSSProperties}
                  >
                    <b>{c === OCULTO ? "" : c || FANTASMA[i]}</b>
                  </span>
                );
              })}
            </div>
          </div>
          <span className="placa__feixe" aria-hidden />
        </div>

        {aoMudar ? (
          <input
            ref={entrada}
            className="placa__input"
            aria-label={rotulo}
            aria-describedby={erro !== null ? "placa-aviso" : undefined}
            value={valor}
            readOnly={!editavel}
            maxLength={12}
            inputMode="text"
            autoCapitalize="characters"
            autoCorrect="off"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="search"
            onChange={(e) => digitar(e.target.value)}
            onFocus={() => setFocada(true)}
            onBlur={() => setFocada(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && placaCompleta(valor)) aoConfirmar?.();
            }}
          />
        ) : (
          <span className="sr-only">
            {rotulo}: {valor.replaceAll(OCULTO, " oculto ")}
          </span>
        )}
      </div>
      <p id="placa-aviso" role="status" aria-live="polite" className="placa-aviso">
        {erro !== null ? `Na ${erro + 1}ª posição vai ${DICA[erro]}.` : " "}
      </p>
    </div>
  );
}
