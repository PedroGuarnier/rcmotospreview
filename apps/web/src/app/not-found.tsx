import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = {
  title: { absolute: "Página não encontrada — RC Motos" },
  description: "Este endereço não existe no site da RC Motos. Veja as motos e os carros que estão à venda agora.",
};

/**
 * Endereço que não existe, em qualquer parte do site. Fica de propósito sem os estilos e os
 * componentes do site público: o Next carrega este arquivo junto com todas as páginas.
 */
export default function NaoEncontrada() {
  return (
    <main className="grid min-h-dvh place-items-center bg-tinta px-5 py-12 text-white">
      <div className="w-full max-w-xl">
        <Link href="/" className="inline-flex items-center gap-3" aria-label="RC Motos — início">
          <Image src="/logo.png" alt="" width={48} height={48} />
          <span className="display text-2xl">
            RC <span className="text-amarelo">Motos</span>
          </span>
        </Link>
        <h1 className="display mt-10 text-5xl leading-[1.1] sm:text-7xl">
          Essa página <span className="text-amarelo">não existe.</span>
        </h1>
        <p className="mt-5 max-w-md text-lg leading-relaxed text-nevoa">
          O endereço pode ter mudado ou sido digitado errado. A vitrine continua no mesmo lugar.
        </p>
        <Link
          href="/#vitrine"
          className="display mt-8 inline-flex min-h-13 items-center rounded-md bg-amarelo px-6 text-lg tracking-wide text-tinta transition-colors hover:bg-white"
        >
          Ver a vitrine
        </Link>
      </div>
    </main>
  );
}
