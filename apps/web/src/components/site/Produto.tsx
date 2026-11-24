"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { LaudoVisual } from "@/components/placa/Laudo";
import { numero } from "@/lib/formato";
import type { Loja } from "@/lib/loja";
import type { ProcedenciaPublica, VeiculoPublico } from "@/lib/tipos";
import {
  ROTULO_TIPO,
  anoVeiculo,
  caminhoVitrine,
  chegouEstaSemana,
  linkVeiculo,
  nomeVeiculo,
  queroEsse,
} from "./anuncio";
import { Cartao } from "./Cartao";
import { Galeria } from "./Galeria";
import { Moldura } from "./Moldura";
import { Barras, Capa, Preco, SeloLaudo } from "./pecas";

const MINIATURAS = 6;

/** Página de um veículo da vitrine: fotos, preço, ficha, WhatsApp, laudo e outros anúncios. */
export function Produto({
  veiculo,
  laudo,
  outros,
  ilustrativo,
  loja,
  pagina,
}: {
  veiculo: VeiculoPublico;
  /** null quando não deu para carregar o laudo: o bloco simplesmente não aparece */
  laudo: ProcedenciaPublica | null;
  outros: VeiculoPublico[];
  ilustrativo: boolean;
  loja: Loja;
  /** endereço completo desta página (só com SITE_URL), para ir junto na mensagem */
  pagina?: string;
}) {
  const [atual, setAtual] = useState(0);
  const [aberta, setAberta] = useState<number | null>(null);
  const fechar = useCallback(() => setAberta(null), []);

  const nome = nomeVeiculo(veiculo);
  const fotos = veiculo.fotos;
  const linkQuero = linkVeiculo(loja.whatsapp, veiculo, pagina);
  const ano = anoVeiculo(veiculo);
  const sobram = fotos.length - MINIATURAS;

  const ficha: [string, React.ReactNode][] = [["Tipo", ROTULO_TIPO[veiculo.tipo]]];
  if (ano) ficha.push(["Ano", ano]); // "2021/2022" = fabricação/modelo
  if (veiculo.km !== null) ficha.push(["Quilometragem", `${numero(veiculo.km)} km`]);
  if (veiculo.cor) ficha.push(["Cor", veiculo.cor]);
  if (veiculo.placa_mascarada) {
    ficha.push([
      "Placa",
      <span key="placa" className="produto__placa" aria-label="Placa parcialmente oculta">
        {veiculo.placa_mascarada}
      </span>,
    ]);
  }

  return (
    <Moldura loja={loja} linkZap={linkQuero}>
      <article className="claro produto" aria-labelledby="titulo-veiculo">
        <nav className="trilha" aria-label="Você está em">
          <Link href={caminhoVitrine()}>Vitrine</Link>
          <span aria-hidden>/</span>
          <Link href={caminhoVitrine(veiculo.tipo)}>{veiculo.tipo === "moto" ? "Motos" : "Carros"}</Link>
          <span aria-hidden>/</span>
          <span aria-current="page">{nome}</span>
        </nav>

        <div className="produto__grade">
          <div className="produto__fotos">
            {fotos.length > 0 ? (
              <button
                type="button"
                className="produto__principal"
                onClick={() => setAberta(atual)}
                aria-label={`Ampliar a foto ${atual + 1} de ${fotos.length}`}
              >
                {/* eslint-disable @next/next/no-img-element -- fotos já redimensionadas pela API */}
                <img className="produto__fundo" src={fotos[atual].miniatura_url} alt="" aria-hidden />
                <img
                  key={fotos[atual].id}
                  className="produto__foto"
                  src={fotos[atual].url}
                  alt={`${nome}, foto ${atual + 1} de ${fotos.length}`}
                />
                {/* eslint-enable @next/next/no-img-element */}
                <span className="dado produto__ampliar" aria-hidden>
                  Ampliar · {atual + 1}/{fotos.length}
                </span>
              </button>
            ) : (
              <div className="produto__principal">
                <Capa veiculo={veiculo} />
              </div>
            )}

            {fotos.length > 1 && (
              <ul className="produto__miniaturas" aria-label="Fotos do veículo">
                {fotos.slice(0, sobram > 0 ? MINIATURAS - 1 : MINIATURAS).map((foto, i) => (
                  <li key={foto.id}>
                    <button
                      type="button"
                      aria-pressed={i === atual}
                      aria-label={`Mostrar a foto ${i + 1}`}
                      onClick={() => setAtual(i)}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element -- miniatura da API */}
                      <img src={foto.miniatura_url} alt="" loading="lazy" />
                    </button>
                  </li>
                ))}
                {sobram > 0 && (
                  <li>
                    <button
                      type="button"
                      className="dado produto__mais"
                      aria-label={`Ver as outras ${sobram + 1} fotos`}
                      onClick={() => setAberta(MINIATURAS - 1)}
                    >
                      +{sobram + 1}
                    </button>
                  </li>
                )}
              </ul>
            )}
          </div>

          <div className="produto__painel">
            <p className="produto__selos">
              <span className="etiqueta etiqueta--linha">{ROTULO_TIPO[veiculo.tipo]}</span>
              {chegouEstaSemana(veiculo) && <span className="etiqueta">Chegou esta semana</span>}
            </p>
            <h1 id="titulo-veiculo" className="outdoor produto__nome">
              {nome}
            </h1>
            <Preco valor={veiculo.preco} className="produto__preco" />

            <dl className="produto__ficha">
              {ficha.map(([rotulo, valor]) => (
                <div key={rotulo}>
                  <dt>{rotulo}</dt>
                  <dd>{valor}</dd>
                </div>
              ))}
            </dl>

            <div className="produto__acoes" data-sem-zap>
              <a className="acao acao--tinta" href={linkQuero} target="_blank" rel="noopener">
                {queroEsse(veiculo.tipo)}
              </a>
              <Link className="acao acao--linha acao--sem-seta" href={`/?veiculo=${veiculo.id}#pagamento`}>
                Montar proposta
              </Link>
            </div>

            {laudo?.semaforo && (
              <a className="produto__laudo" href="#laudo">
                <SeloLaudo cor={laudo.semaforo} />
                <span>
                  Ver o laudo <span aria-hidden>↓</span>
                </span>
              </a>
            )}
            {ilustrativo && (
              <p className="dado vitrine__nota">Ambiente de demonstração: veículo, preço e laudo ilustrativos.</p>
            )}
          </div>
        </div>
      </article>

      {laudo && (
        <section id="laudo" className="laudo-anuncio" aria-labelledby="titulo-laudo">
          <div className="laudo-anuncio__grade">
            <div>
              <p className="sobretitulo">
                <Barras /> Consulta pela placa
              </p>
              <h2 id="titulo-laudo" className="outdoor laudo-anuncio__titulo">
                Laudo de <em>procedência.</em>
              </h2>
              <p className="laudo-anuncio__texto">
                A consulta pela placa confere roubo e furto, leilão, restrição judicial e dados cadastrais.
                {veiculo.placa_mascarada && " No site a placa aparece pela metade, para ninguém clonar."}
              </p>
            </div>
            <LaudoVisual
              semaforo={laudo.semaforo}
              itens={laudo.itens}
              // sem laudo anexado, a linha do tempo ficaria com um marco só: fica só o aviso
              historico={laudo.semaforo ? laudo.historico : []}
              consultadoEm={laudo.consultado_em}
              ilustrativo={laudo.ilustrativo}
              semLaudo="A consulta deste veículo ainda não foi anexada. Peça o laudo para a loja."
            />
          </div>
        </section>
      )}

      {outros.length > 0 && (
        <section className="claro outros" aria-labelledby="titulo-outros">
          <div className="outros__cabeca">
            <h2 id="titulo-outros" className="outdoor outros__titulo">
              Outros na <em>vitrine.</em>
            </h2>
            <Link className="acao acao--linha" href={caminhoVitrine()}>
              Ver a vitrine toda
            </Link>
          </div>
          <div className="grade">
            {outros.map((v) => (
              <Cartao key={v.id} veiculo={v} whatsapp={loja.whatsapp} />
            ))}
          </div>
        </section>
      )}

      {aberta !== null && <Galeria veiculo={veiculo} inicial={aberta} aoFechar={fechar} />}
    </Moldura>
  );
}
