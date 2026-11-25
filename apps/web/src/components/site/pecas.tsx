/** Peças pequenas que se repetem pelo site: barras da marca, preço, selo do laudo, foto ou pôster. */
import { Semaforo } from "@/components/placa/Laudo";
import type { Semaforo as Cor, VeiculoPublico } from "@/lib/tipos";
import { ROTULO_LAUDO, nomeVeiculo, precoVeiculo } from "./anuncio";

/** As três barras de velocidade do "R" da logo. */
export function Barras() {
  return (
    <span className="barras" aria-hidden>
      <i />
      <i />
      <i />
    </span>
  );
}

export function IconeZap() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5.1-1.3A10 10 0 1 0 12 2Zm0 1.8a8.2 8.2 0 1 1-4.2 15.25l-.3-.18-3 .77.8-2.9-.2-.3A8.2 8.2 0 0 1 12 3.8Zm-3.1 3.9c-.2 0-.5.07-.75.35-.26.28-1 .97-1 2.37 0 1.4 1 2.75 1.16 2.94.14.19 2 3.05 4.84 4.27 2.36 1.01 2.84.81 3.35.76.51-.05 1.65-.67 1.88-1.32.23-.65.23-1.2.16-1.32-.07-.12-.26-.19-.54-.33-.28-.14-1.65-.81-1.9-.9-.26-.1-.44-.14-.63.14-.19.28-.72.9-.89 1.09-.16.19-.33.21-.6.07-.28-.14-1.19-.44-2.26-1.4-.84-.74-1.4-1.66-1.56-1.94-.16-.28-.02-.43.12-.57.13-.13.28-.33.42-.49.14-.16.19-.28.28-.47.09-.19.05-.35-.02-.49-.07-.14-.63-1.51-.86-2.07-.23-.54-.46-.47-.63-.48l-.54-.01Z" />
    </svg>
  );
}

export function Preco({ valor, className = "" }: { valor: string; className?: string }) {
  return (
    <p className={`preco ${className}`}>
      <small>R$</small>
      {precoVeiculo(valor)}
    </p>
  );
}

/** Selo discreto do laudo: o semáforo deitado e o veredito em três palavras. */
export function SeloLaudo({ cor }: { cor: Cor }) {
  return (
    <span className="selo-laudo">
      <Semaforo cor={cor} deitado tamanho="0.6rem" />
      {ROTULO_LAUDO[cor]}
    </span>
  );
}

/**
 * A imagem do anúncio: a primeira foto ou, enquanto não há foto, um pôster tipográfico
 * (as barras da logo no alto, marca pequena e modelo grande embaixo). O elemento pai define o tamanho.
 */
export function Capa({ veiculo, urgente = false }: { veiculo: VeiculoPublico; urgente?: boolean }) {
  const foto = veiculo.fotos[0];
  if (foto) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- foto já redimensionada pela API
      <img
        className="capa"
        src={foto.url}
        srcSet={`${foto.miniatura_url} 480w, ${foto.url} 1920w`}
        sizes="(min-width: 1100px) 34vw, (min-width: 640px) 48vw, 94vw"
        alt={`Foto: ${nomeVeiculo(veiculo)}`}
        loading={urgente ? "eager" : "lazy"}
        decoding="async"
      />
    );
  }
  // o tamanho da letra acompanha o comprimento do modelo: nome curto enche o pôster numa linha,
  // nome longo vai para duas — e o teto de altura (em % da caixa) é menor quando são duas
  const letras = Math.max(veiculo.modelo.length, 6);
  const teto = letras <= 19 ? 34 : 18;
  return (
    <span className="poster" style={{ "--letras": letras, "--teto": teto } as React.CSSProperties} aria-hidden>
      <Barras />
      <span className="poster__base">
        <span className="poster__marca">{veiculo.marca}</span>
        <span className="poster__modelo">{veiculo.modelo}</span>
        <span className="poster__aviso">Fotos em breve</span>
      </span>
    </span>
  );
}
