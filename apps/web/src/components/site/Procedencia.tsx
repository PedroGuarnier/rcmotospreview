"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { flushSync } from "react-dom";
import { LaudoVisual } from "@/components/placa/Laudo";
import { type FormatoPlaca, PlacaMercosul, placaCompleta } from "@/components/placa/PlacaMercosul";
import type { ProcedenciaPublica } from "@/lib/tipos";
import { caminhoVeiculo, fichaVeiculo, linkVeiculo, nomeVeiculo, queroEsse } from "./anuncio";
import { Barras, Preco } from "./pecas";

type Estado =
  | { fase: "espera" }
  | { fase: "consultando" }
  | { fase: "laudo"; laudo: ProcedenciaPublica }
  | { fase: "fora"; placa: string }
  | { fase: "erro"; mensagem: string };

const CONFERIDOS = ["Roubo e furto", "Leilão", "Restrição judicial (Renajud)", "Dados cadastrais"];
const pausa = (ms: number) => new Promise((ok) => setTimeout(ok, ms));
const semMovimento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * A procedência como garantia da loja: o que é conferido em cada veículo e a consulta pela placa.
 * O laudo de cada anúncio aparece na página dele; aqui é para quem tem a placa em mãos.
 */
export function Procedencia({ whatsapp, linkLoja }: { whatsapp: string | null; linkLoja: string }) {
  const [placa, setPlaca] = useState("");
  const [formato, setFormato] = useState<FormatoPlaca>("moto");
  const [estado, setEstado] = useState<Estado>({ fase: "espera" });
  const resultado = useRef<HTMLDivElement>(null);
  const corrida = useRef(0); // descarta respostas de consultas antigas

  function trocarFormato(novo: FormatoPlaca) {
    if (novo === formato) return;
    // os caracteres viajam até o novo lugar (onde o navegador suporta)
    if (document.startViewTransition && !semMovimento()) {
      document.startViewTransition(() => flushSync(() => setFormato(novo)));
    } else {
      setFormato(novo);
    }
  }

  async function conferir() {
    const vez = ++corrida.current;
    setEstado({ fase: "consultando" });
    try {
      // a leitura dura pelo menos o tempo do feixe passar uma vez pela chapa
      const [resposta] = await Promise.all([
        fetch(`/api/publico/procedencia/${placa}`),
        pausa(semMovimento() ? 0 : 1150),
      ]);
      if (vez !== corrida.current) return;
      if (resposta.status === 404) setEstado({ fase: "fora", placa });
      else if (!resposta.ok) {
        const corpo = await resposta.json().catch(() => null);
        setEstado({ fase: "erro", mensagem: corpo?.detail ?? "Não deu para consultar agora. Tente de novo." });
      } else setEstado({ fase: "laudo", laudo: await resposta.json() });
    } catch {
      if (vez !== corrida.current) return;
      setEstado({ fase: "erro", mensagem: "Sem conexão. Tente de novo." });
    }
    // o resultado abre logo abaixo: traz para a tela quem estava olhando para a placa
    requestAnimationFrame(() =>
      resultado.current?.scrollIntoView({ block: "nearest", behavior: semMovimento() ? "auto" : "smooth" }),
    );
  }

  function digitar(valor: string) {
    corrida.current++;
    setPlaca(valor);
    if (estado.fase !== "espera") setEstado({ fase: "espera" });
  }

  const consultando = estado.fase === "consultando";
  const pronta = placaCompleta(placa);

  return (
    <section id="procedencia" className="garantia" aria-labelledby="titulo-procedencia">
      <div className="garantia__grade">
        <div>
          <p className="sobretitulo" data-revelar>
            <Barras /> Procedência
          </p>
          <h2 id="titulo-procedencia" className="outdoor garantia__titulo" data-revelar>
            Veículo da vitrine <em>tem laudo.</em>
          </h2>
          <p className="garantia__texto" data-revelar>
            Todo veículo passa por consulta pela placa antes de ir à venda. O resultado fica na página de cada
            anúncio, para você ver antes de sair de casa.
          </p>
          <ul className="garantia__itens" data-revelar>
            {CONFERIDOS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="garantia__consulta" data-revelar>
          <p className="dado garantia__rotulo">Confira o laudo pela placa</p>
          <div className="formato" role="group" aria-label="Formato da placa">
            <button type="button" aria-pressed={formato === "moto"} onClick={() => trocarFormato("moto")}>
              Moto
            </button>
            <button type="button" aria-pressed={formato === "carro"} onClick={() => trocarFormato("carro")}>
              Carro
            </button>
          </div>
          <div className="garantia__placa" data-formato={formato}>
            <PlacaMercosul
              valor={placa}
              formato={formato}
              aoMudar={digitar}
              aoConfirmar={conferir}
              estado={consultando ? "consultando" : "livre"}
              rotulo="Placa de um veículo da loja (7 caracteres)"
              transicao
            />
          </div>
          <button type="button" className="acao" disabled={!pronta || consultando} onClick={conferir}>
            {consultando ? "Lendo a placa" : "Conferir o laudo"}
          </button>
        </div>
      </div>

      <div ref={resultado} className="garantia__resultado" aria-live="polite">
        {estado.fase === "laudo" && (
          // a chave refaz a coreografia a cada novo laudo
          <div key={`${estado.laudo.veiculo.id}-${estado.laudo.placa}`} className="garantia__laudo">
            <div className="achado">
              <div>
                <p className="dado achado__rotulo">Na vitrine da RC</p>
                <p className="outdoor achado__nome">{nomeVeiculo(estado.laudo.veiculo)}</p>
                {fichaVeiculo(estado.laudo.veiculo).length > 0 && (
                  <p className="dado ficha">
                    {fichaVeiculo(estado.laudo.veiculo).map((item) => (
                      <span key={item}>{item}</span>
                    ))}
                  </p>
                )}
              </div>
              <Preco valor={estado.laudo.veiculo.preco} />
            </div>
            <LaudoVisual
              semaforo={estado.laudo.semaforo}
              itens={estado.laudo.itens}
              historico={estado.laudo.historico}
              consultadoEm={estado.laudo.consultado_em}
              ilustrativo={estado.laudo.ilustrativo}
              semLaudo="A consulta deste veículo ainda não foi anexada. Peça o laudo para a loja."
            />
            <div className="garantia__fecho">
              <Link className="acao" href={caminhoVeiculo(estado.laudo.veiculo)} prefetch={false}>
                Ver o veículo
              </Link>
              <a
                className="acao acao--linha acao--sem-seta"
                href={linkVeiculo(whatsapp, estado.laudo.veiculo)}
                target="_blank"
                rel="noopener"
              >
                {queroEsse(estado.laudo.veiculo.tipo)}
              </a>
            </div>
          </div>
        )}

        {estado.fase === "fora" && (
          <div className="fora">
            <p>Essa não é da nossa vitrine.</p>
            <p>
              A placa {estado.placa} não está entre os veículos à venda na RC Motos. O laudo daqui vale para o que
              está na loja — confira a placa ou escolha um veículo da vitrine.
            </p>
            <div className="garantia__fecho">
              <a className="acao" href="#vitrine">
                Ver a vitrine
              </a>
              <a className="acao acao--linha acao--sem-seta" href={linkLoja} target="_blank" rel="noopener">
                Falar com a loja
              </a>
            </div>
          </div>
        )}

        {estado.fase === "erro" && (
          <div className="fora" role="alert">
            <p>Não deu para ler.</p>
            <p>{estado.mensagem}</p>
            <div className="garantia__fecho">
              <button type="button" className="acao" onClick={conferir} disabled={!pronta}>
                Tentar de novo
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
