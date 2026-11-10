"use client";

import { useEffect, useId, useRef, useState } from "react";
import { valorParaCampo } from "@/lib/formato";

type Tom = "primario" | "amarelo" | "neutro" | "perigo" | "fantasma";

const TONS: Record<Tom, string> = {
  primario: "bg-azul text-white hover:bg-azul-escuro",
  amarelo: "bg-amarelo text-tinta hover:bg-amarelo-escuro",
  neutro: "bg-white text-tinta border border-borda hover:border-azul",
  perigo: "bg-white text-vermelho border border-vermelho/40 hover:bg-vermelho hover:text-white",
  fantasma: "text-azul hover:bg-azul/10",
};

export function Botao({
  tom = "primario",
  pequeno,
  ocupado,
  className = "",
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tom?: Tom; pequeno?: boolean; ocupado?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || ocupado}
      className={`inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        pequeno ? "min-h-9 px-3.5 text-sm" : "min-h-11 px-5 text-[15px]"
      } ${TONS[tom]} ${className}`}
    >
      {ocupado ? "Aguarde…" : children}
    </button>
  );
}

/** Motivo da logo: as três barras de velocidade do "R". */
export function Barras({ className = "bg-amarelo" }: { className?: string }) {
  return (
    <span aria-hidden className="inline-flex flex-col gap-[3px]">
      <i className={`block h-[3px] w-6 rounded ${className}`} />
      <i className={`ml-2 block h-[3px] w-4 rounded ${className}`} />
      <i className={`ml-4 block h-[3px] w-2 rounded ${className}`} />
    </span>
  );
}

export function Titulo({
  sobre,
  children,
  acoes,
}: {
  sobre?: string;
  children: React.ReactNode;
  acoes?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        {sobre && (
          <p className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-azul">
            <Barras className="bg-azul" /> {sobre}
          </p>
        )}
        <h1 className="display text-3xl leading-tight sm:text-4xl">{children}</h1>
      </div>
      {acoes && <div className="flex flex-wrap gap-2">{acoes}</div>}
    </div>
  );
}

export function Cartao({
  className = "",
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={`rounded-2xl border border-borda bg-white ${className}`}>{children}</div>;
}

const ETIQUETAS = {
  azul: "bg-azul/10 text-azul",
  verde: "bg-verde/10 text-verde",
  amarelo: "bg-amarelo/30 text-tinta",
  cinza: "bg-gelo text-suave",
  vermelho: "bg-vermelho/10 text-vermelho",
  laranja: "bg-laranja/10 text-laranja",
};

export function Etiqueta({
  cor = "cinza",
  sobreFoto,
  children,
}: {
  cor?: keyof typeof ETIQUETAS;
  /** fundo branco por baixo, para ficar legível em cima de foto */
  sobreFoto?: boolean;
  children: React.ReactNode;
}) {
  const etiqueta = (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${ETIQUETAS[cor]}`}
    >
      {children}
    </span>
  );
  return sobreFoto ? <span className="inline-flex rounded-full bg-white shadow-sm">{etiqueta}</span> : etiqueta;
}

export function Aviso({ children, tom = "erro" }: { children: React.ReactNode; tom?: "erro" | "info" }) {
  if (!children) return null;
  return (
    <p
      role={tom === "erro" ? "alert" : "status"}
      className={`rounded-xl px-4 py-3 text-sm font-medium ${
        tom === "erro" ? "bg-vermelho/10 text-vermelho" : "bg-azul/10 text-azul"
      }`}
    >
      {children}
    </p>
  );
}

export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return <p className="py-10 text-center text-sm text-suave">{texto}</p>;
}

export function Vazio({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-borda bg-white/60 px-6 py-12 text-center text-sm text-suave">
      {children}
    </div>
  );
}

const CAMPO =
  "w-full min-h-11 rounded-xl border border-borda bg-white px-3.5 text-[15px] text-tinta placeholder:text-suave/60 focus:border-azul focus:outline-none focus:ring-2 focus:ring-azul/20 disabled:bg-gelo";

export function Rotulo({
  rotulo,
  dica,
  children,
  className = "",
}: {
  rotulo: string;
  dica?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1.5 block text-sm font-semibold">{rotulo}</span>
      {children}
      {dica && <span className="mt-1 block text-xs text-suave">{dica}</span>}
    </label>
  );
}

export function Campo({
  rotulo,
  dica,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { rotulo: string; dica?: string }) {
  return (
    <Rotulo rotulo={rotulo} dica={dica} className={className}>
      <input {...props} className={CAMPO} />
    </Rotulo>
  );
}

export function AreaTexto({
  rotulo,
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { rotulo: string }) {
  return (
    <Rotulo rotulo={rotulo} className={className}>
      <textarea rows={3} {...props} className={`${CAMPO} py-2.5`} />
    </Rotulo>
  );
}

export function Selecao<T extends string>({
  rotulo,
  valor,
  aoMudar,
  opcoes,
  className,
  disabled,
}: {
  rotulo: string;
  valor: T;
  aoMudar: (valor: T) => void;
  opcoes: { valor: T; rotulo: string }[];
  className?: string;
  disabled?: boolean;
}) {
  return (
    <Rotulo rotulo={rotulo} className={className}>
      <select
        value={valor}
        disabled={disabled}
        onChange={(e) => aoMudar(e.target.value as T)}
        className={CAMPO}
      >
        {opcoes.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.rotulo}
          </option>
        ))}
      </select>
    </Rotulo>
  );
}

/** Campo de dinheiro: aceita "14900", "14.900,00"… e formata ao sair. */
export function CampoValor({
  rotulo,
  valor,
  aoMudar,
  dica,
  className,
  required,
  autoFocus,
}: {
  rotulo: string;
  valor: string;
  aoMudar: (valor: string) => void;
  dica?: string;
  className?: string;
  required?: boolean;
  autoFocus?: boolean;
}) {
  return (
    <Rotulo rotulo={rotulo} dica={dica} className={className}>
      <div className="relative">
        <span aria-hidden className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-suave">
          R$
        </span>
        <input
          inputMode="decimal"
          autoComplete="off"
          required={required}
          autoFocus={autoFocus}
          value={valor}
          placeholder="0,00"
          onChange={(e) => aoMudar(e.target.value.replace(/[^\d.,]/g, ""))}
          onBlur={() => {
            const limpo = valor.includes(",") ? valor.replace(/\./g, "").replace(",", ".") : valor;
            if (limpo && Number.isFinite(Number(limpo))) aoMudar(valorParaCampo(limpo));
          }}
          className={`${CAMPO} num pl-10`}
        />
      </div>
    </Rotulo>
  );
}

/** Janela modal: folha que sobe no celular, caixa centralizada no computador. */
export function Modal({
  titulo,
  aoFechar,
  children,
  largo,
}: {
  titulo: string;
  aoFechar: () => void;
  children: React.ReactNode;
  largo?: boolean;
}) {
  const id = useId();
  const caixa = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    document.addEventListener("keydown", tecla);
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    caixa.current?.focus();
    return () => {
      document.removeEventListener("keydown", tecla);
      document.body.style.overflow = anterior;
    };
  }, [aoFechar]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-tinta/60 sm:items-center sm:p-4"
      onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}
    >
      <div
        ref={caixa}
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        tabIndex={-1}
        className={`entrar max-h-[92dvh] w-full overflow-y-auto rounded-t-3xl bg-white p-5 outline-none sm:rounded-3xl sm:p-7 ${
          largo ? "sm:max-w-2xl" : "sm:max-w-lg"
        }`}
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <h2 id={id} className="display text-2xl">
            {titulo}
          </h2>
          <button
            type="button"
            onClick={aoFechar}
            aria-label="Fechar"
            className="-mr-1 -mt-1 grid size-9 shrink-0 place-items-center rounded-full text-xl text-suave hover:bg-gelo"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** Seletor de mês com setas (‹ novembro de 2026 ›). */
export function SeletorMes({
  rotulo,
  aoAnterior,
  aoProximo,
  podeAvancar,
}: {
  rotulo: string;
  aoAnterior: () => void;
  aoProximo: () => void;
  podeAvancar: boolean;
}) {
  const seta = "grid size-10 place-items-center rounded-full border border-borda bg-white text-lg hover:border-azul disabled:opacity-40";
  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={aoAnterior} aria-label="Mês anterior" className={seta}>
        ‹
      </button>
      <span className="inline-block min-w-40 text-center text-sm font-semibold first-letter:uppercase">{rotulo}</span>
      <button
        type="button"
        onClick={aoProximo}
        disabled={!podeAvancar}
        aria-label="Próximo mês"
        className={seta}
      >
        ›
      </button>
    </div>
  );
}

/** Estado de uma ação assíncrona (salvar, pagar…): controla "ocupado" e a mensagem de erro. */
export function useAcao() {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");

  async function executar(acao: () => Promise<unknown>): Promise<boolean> {
    setOcupado(true);
    setErro("");
    try {
      await acao();
      return true;
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Algo deu errado. Tente de novo.");
      return false;
    } finally {
      setOcupado(false);
    }
  }

  return { ocupado, erro, executar, limparErro: () => setErro("") };
}
