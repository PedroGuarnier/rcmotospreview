import type { Metadata } from "next";

// Metadata de reserva da seção: vale para o aviso de "fora da vitrine" (resposta 404).
// A página de cada veículo que está à venda define a sua, com nome, preço e foto.
export const metadata: Metadata = {
  title: { absolute: "Veículo fora da vitrine — RC Motos" },
  description: "Este veículo não está mais na vitrine da RC Motos. Veja as motos e os carros que estão à venda agora.",
};

export default function Secao({ children }: { children: React.ReactNode }) {
  return children;
}
