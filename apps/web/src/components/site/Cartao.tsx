"use client";

import Link from "next/link";
import type { VeiculoPublico } from "@/lib/tipos";
import { Abrindo } from "./Abrindo";
import { caminhoVeiculo, chegouEstaSemana, fichaVeiculo, linkVeiculo, nomeVeiculo, queroEsse } from "./anuncio";
import { contarClique } from "./contagem";
import { Capa, Preco, SeloLaudo } from "./pecas";

/**
 * Cartão de produto da vitrine. O cartão inteiro leva à página do veículo (o link do nome se
 * estende por cima de tudo); só o botão do WhatsApp fica por cima dele.
 */
export function Cartao({
  veiculo,
  whatsapp,
  ordem = 0,
}: {
  veiculo: VeiculoPublico;
  whatsapp: string | null;
  /** posição na grade, para a entrada escalonada */
  ordem?: number;
}) {
  const ficha = fichaVeiculo(veiculo);
  return (
    <article className="cartao" style={{ "--i": Math.min(ordem, 8) } as React.CSSProperties}>
      <div className="cartao__midia">
        <Capa veiculo={veiculo} />
        {chegouEstaSemana(veiculo) && <span className="etiqueta">Chegou esta semana</span>}
        {veiculo.fotos.length > 1 && <span className="cartao__conta">{veiculo.fotos.length} fotos</span>}
      </div>
      <div className="cartao__corpo">
        <h3 className="outdoor cartao__nome">
          <Link href={caminhoVeiculo(veiculo)} prefetch={false}>
            {nomeVeiculo(veiculo)}
            <Abrindo />
          </Link>
        </h3>
        {ficha.length > 0 && (
          <p className="dado ficha">
            {ficha.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </p>
        )}
        {veiculo.semaforo && <SeloLaudo cor={veiculo.semaforo} />}
        <div className="cartao__fecho">
          <Preco valor={veiculo.preco} />
          <div className="cartao__acoes">
            <a
              className="acao acao--tinta"
              href={linkVeiculo(whatsapp, veiculo)}
              target="_blank"
              rel="noopener"
              onClick={() => contarClique(veiculo.id, "cartao")}
              aria-label={`${queroEsse(veiculo.tipo)}: ${nomeVeiculo(veiculo)} (abre o WhatsApp)`}
            >
              {queroEsse(veiculo.tipo)}
            </a>
            {/* fica por baixo do link do cartão: é ele quem recebe o clique e o foco */}
            <span className="acao acao--linha acao--sem-seta" aria-hidden>
              Ver detalhes
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
