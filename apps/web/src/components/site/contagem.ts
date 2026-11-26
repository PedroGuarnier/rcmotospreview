/**
 * Contagem de visitas e cliques no WhatsApp por veículo (POST /publico/eventos).
 * Sem cookie e sem serviço externo: só o tipo e o número do veículo. `sendBeacon` entrega mesmo
 * com a página saindo e não segura a abertura do WhatsApp.
 */
import type { TipoEventoSite } from "@/lib/tipos";

export type OrigemClique = "cartao" | "pagina" | "proposta";

// Visitas já contadas nesta aba (some ao recarregar): voltar ao mesmo anúncio não conta de novo.
const vistos = new Set<number>();

function enviar(tipo: TipoEventoSite, veiculoId: number) {
  try {
    const corpo = new Blob([JSON.stringify({ tipo, veiculo_id: veiculoId })], { type: "application/json" });
    if (navigator.sendBeacon?.("/api/publico/eventos", corpo)) return;
    void fetch("/api/publico/eventos", { method: "POST", body: corpo, keepalive: true }).catch(() => {});
  } catch {
    // contagem nunca atrapalha a navegação
  }
}

/** Abriu a página do veículo. */
export function contarVisita(veiculoId: number) {
  if (vistos.has(veiculoId)) return;
  vistos.add(veiculoId);
  enviar("visualizacao", veiculoId);
}

/** Tocou num botão de WhatsApp sobre o veículo. */
export function contarClique(veiculoId: number, origem: OrigemClique) {
  enviar(`whatsapp_${origem}`, veiculoId);
}
