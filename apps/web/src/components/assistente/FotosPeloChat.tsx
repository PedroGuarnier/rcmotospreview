"use client";

import { useRef, useState } from "react";
import { api, mensagemDe } from "@/lib/api";
import type { Foto, VeiculoDetalhe } from "@/lib/tipos";

// Os mesmos limites da API (app/fotos.py e FOTO_TAMANHO_MAX_MB): conferir antes poupa o envio
// de um arquivo que seria recusado. A API confere de novo.
const FORMATOS = ["image/jpeg", "image/png", "image/webp"];
const TAMANHO_MAX_MB = 15;

interface ErroDeArquivo {
  nome: string;
  motivo: string;
}

function motivoLocal(arquivo: File): string | null {
  if (arquivo.type && !FORMATOS.includes(arquivo.type)) {
    const formato = arquivo.type.split("/")[1]?.toUpperCase() || "desconhecido";
    return `formato ${formato} não aceito. Envie JPG, PNG ou WebP.`;
  }
  if (arquivo.size > TAMANHO_MAX_MB * 1024 * 1024) {
    return `foto muito grande (máx. ${TAMANHO_MAX_MB} MB).`;
  }
  return null;
}

/**
 * Fotos pelo chat: depois de cadastrar ou alterar um veículo, as fotos vão dali mesmo, uma
 * por requisição, pelo endpoint da página do veículo (POST /veiculos/{id}/fotos). As enviadas
 * ficam guardadas na conversa (`aoEnviar`), então recarregar a página não as perde.
 */
export function FotosPeloChat({
  veiculoId,
  fotos,
  aoEnviar,
}: {
  veiculoId: number;
  fotos: Foto[];
  aoEnviar: (foto: Foto) => void;
}) {
  const entrada = useRef<HTMLInputElement>(null);
  const raiz = useRef<HTMLDivElement>(null);
  const [progresso, setProgresso] = useState<{ atual: number; total: number } | null>(null);
  const [erros, setErros] = useState<ErroDeArquivo[]>([]);

  async function enviar(lista: FileList | null) {
    const arquivos = Array.from(lista ?? []);
    if (entrada.current) entrada.current.value = ""; // deixa escolher os mesmos de novo
    if (!arquivos.length || progresso) return;
    setErros([]);
    const falhas: ErroDeArquivo[] = [];
    for (const [indice, arquivo] of arquivos.entries()) {
      setProgresso({ atual: indice + 1, total: arquivos.length });
      const motivo = motivoLocal(arquivo);
      if (motivo) {
        falhas.push({ nome: arquivo.name, motivo });
        continue;
      }
      try {
        const detalhe = await api<VeiculoDetalhe>(`/veiculos/${veiculoId}/fotos`, { arquivo });
        const nova = detalhe.fotos.reduce((maior, f) => (f.id > maior.id ? f : maior), detalhe.fotos[0]);
        if (nova) aoEnviar(nova);
      } catch (erro) {
        falhas.push({ nome: arquivo.name, motivo: mensagemDe(erro) });
      }
    }
    setErros(falhas);
    setProgresso(null);
    // miniaturas e erros aparecem embaixo do botão: rola até eles (o campo de texto fica por cima)
    requestAnimationFrame(() => raiz.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
  }

  const enviando = progresso !== null;
  return (
    <div ref={raiz} className="mt-3 scroll-mb-40 border-t border-borda pt-3">
      <input
        ref={entrada}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => enviar(e.target.files)}
        aria-label="Escolher fotos do veículo"
      />
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={enviando}
          onClick={() => entrada.current?.click()}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-borda bg-white px-4 text-sm font-semibold transition-colors hover:border-azul disabled:cursor-not-allowed disabled:opacity-60"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.6l1.4-2h5l1.4 2h1.6A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5Z" />
            <circle cx="12" cy="12.5" r="3.2" />
          </svg>
          {enviando ? "Enviando…" : fotos.length ? "Adicionar mais fotos" : "Adicionar fotos"}
        </button>
        {fotos.length > 0 && !enviando && (
          <span className="text-xs text-suave">
            {fotos.length === 1 ? "1 foto enviada" : `${fotos.length} fotos enviadas`}
          </span>
        )}
      </div>

      {progresso && (
        <div className="mt-2.5" role="status" aria-live="polite">
          <p className="text-xs font-semibold text-suave">
            Enviando foto {progresso.atual} de {progresso.total}…
          </p>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gelo">
            <div
              className="h-full rounded-full bg-azul transition-[width] duration-300"
              style={{ width: `${((progresso.atual - 1) / progresso.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {fotos.length > 0 && (
        <ul className="mt-2.5 grid grid-cols-4 gap-1.5 sm:grid-cols-6" aria-label="Fotos enviadas">
          {fotos.map((foto) => (
            <li key={foto.id} className="aspect-square overflow-hidden rounded-lg bg-gelo">
              {/* eslint-disable-next-line @next/next/no-img-element -- miniatura já otimizada pela API */}
              <img src={foto.miniatura_url} alt="" loading="lazy" className="size-full object-cover" />
            </li>
          ))}
        </ul>
      )}

      {erros.length > 0 && (
        <ul role="alert" className="mt-2.5 space-y-1 rounded-xl bg-vermelho/10 px-3 py-2 text-xs text-vermelho">
          {erros.map((erro, i) => (
            <li key={`${erro.nome}-${i}`} className="break-words">
              <b>{erro.nome}</b>: {erro.motivo}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
