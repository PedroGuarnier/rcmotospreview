import { type RefObject, useEffect } from "react";

const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Para o que abre por cima da página (galeria de fotos, menu do celular): o foco entra na caixa,
 * o Tab dá a volta sem sair dela e, ao fechar, o foco volta para quem abriu.
 */
export function useFocoPreso(caixa: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = caixa.current;
    if (!el) return;
    const quemAbriu = document.activeElement as HTMLElement | null;
    const focaveis = () => [...el.querySelectorAll<HTMLElement>(FOCAVEIS)];
    focaveis()[0]?.focus({ preventScroll: true });

    const tecla = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const lista = focaveis();
      if (lista.length === 0) return;
      const primeiro = lista[0];
      const ultimo = lista[lista.length - 1];
      const atual = document.activeElement;
      if (!el.contains(atual)) {
        e.preventDefault();
        primeiro.focus();
      } else if (e.shiftKey && atual === primeiro) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && atual === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    };
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("keydown", tecla);
      // se o foco já seguiu para outro lugar (um link do menu levou a uma seção), fica lá
      const atual = document.activeElement;
      if (!atual || atual === document.body || el.contains(atual)) quemAbriu?.focus({ preventScroll: true });
    };
  }, [caixa]);
}
