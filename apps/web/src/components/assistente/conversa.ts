import { useSyncExternalStore } from "react";
import type {
  DuplicadoAssistente,
  EstadoAssistente,
  RespostaAssistente,
  VeiculoCriadoAssistente,
} from "@/lib/tipos";

export interface Mensagem {
  id: number;
  de: "voce" | "assistente" | "sistema";
  texto: string;
  /** resposta em que o veículo foi criado: vira o cartão de sucesso */
  veiculo?: VeiculoCriadoAssistente | null;
  /** resposta que encontrou a placa ou o chassi em outro veículo */
  duplicado?: DuplicadoAssistente | null;
}

export interface Conversa {
  mensagens: Mensagem[];
  /** devolvido ao servidor na mensagem seguinte */
  estado: EstadoAssistente | null;
  /** última resposta: ficha, o que falta, avisos e ação pendente */
  ultima: RespostaAssistente | null;
}

const VAZIA: Conversa = { mensagens: [], estado: null, ultima: null };
const PREFIXO = "rc.assistente.v1.";
const MAXIMO_GUARDADO = 80;

// A conversa fica no sessionStorage (sobrevive a recarregar a página, some ao fechar a aba),
// uma por usuário. Se o navegador não deixar gravar, ela segue só na memória.
const memoria = new Map<string, Conversa>();
const ouvintes = new Set<() => void>();

function valida(valor: unknown): valor is Conversa {
  if (typeof valor !== "object" || valor === null) return false;
  const c = valor as Partial<Conversa>;
  return (
    Array.isArray(c.mensagens) &&
    c.mensagens.every((m) => typeof m?.id === "number" && typeof m?.texto === "string") &&
    (c.estado === null || typeof c.estado === "object") &&
    (c.ultima === null || (typeof c.ultima === "object" && Array.isArray(c.ultima.ficha)))
  );
}

function ler(chave: string): Conversa {
  const guardada = memoria.get(chave);
  if (guardada) return guardada;
  let conversa = VAZIA;
  try {
    const bruto = window.sessionStorage.getItem(chave);
    const lida: unknown = bruto ? JSON.parse(bruto) : null;
    if (valida(lida)) conversa = semResposta(lida);
  } catch {
    // sem sessionStorage (bloqueado, modo privado) ou conteúdo estragado: começa vazia
  }
  memoria.set(chave, conversa);
  return conversa;
}

/**
 * A página foi recarregada com uma mensagem a caminho: a resposta se perdeu, mas o servidor
 * pode ter atendido (e gravado o veículo, se era a confirmação).
 */
function semResposta(conversa: Conversa): Conversa {
  const ultima = conversa.mensagens.at(-1);
  if (ultima?.de !== "voce") return conversa;
  const aviso: Mensagem = {
    id: ultima.id + 1,
    de: "sistema",
    texto:
      "A página foi recarregada antes de a resposta chegar. Se você estava confirmando o cadastro, " +
      "veja no Estoque se o veículo entrou; se não, mande a mensagem de novo.",
  };
  return { ...conversa, mensagens: [...conversa.mensagens, aviso] };
}

function gravar(chave: string, conversa: Conversa) {
  const enxuta = { ...conversa, mensagens: conversa.mensagens.slice(-MAXIMO_GUARDADO) };
  memoria.set(chave, enxuta);
  try {
    window.sessionStorage.setItem(chave, JSON.stringify(enxuta));
  } catch {
    // fica só na memória
  }
  ouvintes.forEach((avisar) => avisar());
}

function assinar(avisar: () => void) {
  ouvintes.add(avisar);
  return () => {
    ouvintes.delete(avisar);
  };
}

/** Conversa do usuário logado, guardada entre recarregamentos da página. */
export function useConversa(usuarioId: number) {
  const chave = `${PREFIXO}${usuarioId}`;
  const conversa = useSyncExternalStore(
    assinar,
    () => ler(chave),
    () => VAZIA, // no servidor e na hidratação; o que estava guardado entra logo depois
  );
  return {
    conversa,
    /** estado mais recente, para usar dentro de funções assíncronas */
    atual: () => ler(chave),
    gravar: (nova: Conversa) => gravar(chave, nova),
    limpar: () => gravar(chave, VAZIA),
  };
}

/** Ao sair do sistema: o rascunho (que tem valor de compra) não fica para o próximo login. */
export function esquecerConversas() {
  memoria.clear();
  try {
    const chaves = Object.keys(window.sessionStorage).filter((c) => c.startsWith(PREFIXO));
    chaves.forEach((c) => window.sessionStorage.removeItem(c));
  } catch {
    // nada guardado
  }
  ouvintes.forEach((avisar) => avisar());
}
