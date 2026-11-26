"use client";

import { useLinkStatus } from "next/link";

/**
 * Indicador discreto de "abrindo o veículo": uma barra amarela que corre no alto do cartão
 * enquanto a página do veículo carrega. Precisa estar dentro do <Link> (useLinkStatus).
 * Não é `loading.tsx` de propósito: ele faria a resposta do veículo fora da vitrine sair 200,
 * e não 404.
 */
export function Abrindo() {
  const { pending } = useLinkStatus();
  return <span className="abrindo" data-pendente={pending || undefined} aria-hidden />;
}
