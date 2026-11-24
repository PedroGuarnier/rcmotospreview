import Link from "next/link";
import { moeda } from "@/lib/formato";
import type { TipoVeiculo, VeiculoPublico } from "@/lib/tipos";
import { caminhoVeiculo, caminhoVitrine, chegouEstaSemana, fichaVeiculo, nomeVeiculo } from "./anuncio";
import { Barras, Capa, Preco } from "./pecas";

/** Cartão de destaque da primeira dobra: o cartão inteiro é o link para a página do veículo. */
function Destaque({ veiculo }: { veiculo: VeiculoPublico }) {
  const ficha = fichaVeiculo(veiculo);
  const chegou = chegouEstaSemana(veiculo);
  // o cartão inteiro é um link: o nome acessível diz o essencial, em ordem
  const rotulo = [nomeVeiculo(veiculo), ...ficha, moeda(veiculo.preco), chegou ? "chegou esta semana" : null]
    .filter(Boolean)
    .join(", ");
  return (
    <Link href={caminhoVeiculo(veiculo)} prefetch={false} className="destaque" aria-label={rotulo}>
      <span className="destaque__midia">
        <Capa veiculo={veiculo} urgente />
        {chegou && <span className="etiqueta">Chegou esta semana</span>}
      </span>
      <span className="destaque__corpo">
        <span className="destaque__texto">
          <span className="outdoor destaque__nome">{nomeVeiculo(veiculo)}</span>
          {ficha.length > 0 && (
            <span className="dado ficha">
              {ficha.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </span>
          )}
        </span>
        <Preco valor={veiculo.preco} />
      </span>
    </Link>
  );
}

/**
 * Primeira dobra: quem abre o site já vê produto. Título curto, as ações e, ao lado, os
 * veículos que chegaram por último (o catálogo vem do mais novo para o mais antigo).
 */
export function Dobra({
  veiculos,
  local,
  linkLoja,
  aoFiltrar,
}: {
  veiculos: VeiculoPublico[];
  local: string;
  linkLoja: string;
  /** atalho "Motos (n)" / "Carros (n)": filtra a vitrine e desce até ela */
  aoFiltrar: (tipo: TipoVeiculo, evento: React.MouseEvent<HTMLAnchorElement>) => void;
}) {
  const destaques = veiculos.slice(0, 3);
  const motos = veiculos.filter((v) => v.tipo === "moto").length;
  const carros = veiculos.length - motos;
  const vazia = veiculos.length === 0;

  return (
    <section id="topo" className="dobra" aria-labelledby="titulo-site" data-sem-zap data-vazia={vazia}>
      <div className="dobra__grade">
        <div className="dobra__texto">
          <p className="sobretitulo">
            <Barras />
            <span className="dobra__onde">
              <span>Motos e carros seminovos</span> <i aria-hidden>·</i> <span>{local}</span>
            </span>
          </p>
          <h1 id="titulo-site" className="outdoor dobra__titulo">
            Escolha <em>a sua.</em>
          </h1>
          <p className="dobra__apoio">
            {vazia
              ? "Seminovos revisados. Chame a loja no WhatsApp e a gente diz o que tem no pátio hoje."
              : "Seminovos revisados, com preço no site. Escolheu, chama a loja no WhatsApp."}
          </p>
          <div className="dobra__acoes">
            {!vazia && (
              <a className="acao" href="#vitrine">
                Ver a vitrine
              </a>
            )}
            <a
              className={vazia ? "acao" : "acao acao--linha acao--sem-seta"}
              href={linkLoja}
              target="_blank"
              rel="noopener"
            >
              Falar no WhatsApp
            </a>
          </div>
          {!vazia && (
            <div className="dobra__fatos">
              <p className="dado dobra__conta">
                <i aria-hidden />
                <b>{veiculos.length}</b> na loja agora
              </p>
              {/* com um tipo só na loja não há o que filtrar */}
              {motos > 0 && carros > 0 && (
                <nav className="dobra__atalhos" aria-label="Atalhos da vitrine">
                  <a className="atalho" href={caminhoVitrine("moto")} onClick={(e) => aoFiltrar("moto", e)}>
                    Motos <span>({motos})</span>
                  </a>
                  <a className="atalho" href={caminhoVitrine("carro")} onClick={(e) => aoFiltrar("carro", e)}>
                    Carros <span>({carros})</span>
                  </a>
                </nav>
              )}
            </div>
          )}
        </div>

        {vazia ? (
          // sem destaques (vitrine vazia ou API fora do ar): as barras da marca ocupam o lugar
          <div className="dobra__marca" aria-hidden>
            <Barras />
          </div>
        ) : (
          <div className="dobra__vitrine">
            <p className="dado dobra__rotulo">
              <span>Chegaram por último</span>
              <a href="#vitrine">
                Ver {veiculos.length === 1 ? "o veículo" : `todos os ${veiculos.length}`}
                <span aria-hidden> →</span>
              </a>
            </p>
            <div className="destaques" data-total={destaques.length}>
              {destaques.map((v) => (
                <Destaque key={v.id} veiculo={v} />
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
