"use client";

import { type Ref, useImperativeHandle, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { LaudoVisual, Semaforo } from "@/components/placa/Laudo";
import { type FormatoPlaca, PlacaMercosul, placaCompleta } from "@/components/placa/PlacaMercosul";
import { moeda, numero } from "@/lib/formato";
import type { ProcedenciaPublica, VeiculoPublico } from "@/lib/tipos";

type Estado =
  | { fase: "espera" }
  | { fase: "consultando" }
  | { fase: "laudo"; laudo: ProcedenciaPublica }
  | { fase: "fora"; placa: string }
  | { fase: "erro"; mensagem: string };

const CONFERIDOS = ["Roubo e furto", "Leilão", "Restrição judicial (Renajud)", "Dados cadastrais"];
const pausa = (ms: number) => new Promise((ok) => setTimeout(ok, ms));
const semMovimento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export interface ControleProcedencia {
  /** preenche a placa (protegida) do anúncio e abre o laudo dele */
  abrirDoAnuncio: (veiculo: VeiculoPublico) => void;
}

export function Procedencia({
  veiculos,
  controle,
  linkVeiculo,
  linkLoja,
}: {
  veiculos: VeiculoPublico[];
  controle: Ref<ControleProcedencia>;
  linkVeiculo: (v: VeiculoPublico) => string;
  linkLoja: string;
}) {
  const [placa, setPlaca] = useState("");
  const [formato, setFormato] = useState<FormatoPlaca>("moto");
  const [estado, setEstado] = useState<Estado>({ fase: "espera" });
  const [escolhido, setEscolhido] = useState<number | null>(null);
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

  async function buscar(caminho: string, placaDigitada: string) {
    const vez = ++corrida.current;
    setEstado({ fase: "consultando" });
    try {
      // a leitura dura pelo menos o tempo do feixe passar uma vez pela chapa
      const [resposta] = await Promise.all([fetch(caminho), pausa(semMovimento() ? 0 : 1150)]);
      if (vez !== corrida.current) return;
      if (resposta.status === 404) setEstado({ fase: "fora", placa: placaDigitada });
      else if (!resposta.ok) {
        const corpo = await resposta.json().catch(() => null);
        setEstado({ fase: "erro", mensagem: corpo?.detail ?? "Não deu para consultar agora. Tente de novo." });
      } else setEstado({ fase: "laudo", laudo: await resposta.json() });
    } catch {
      if (vez === corrida.current) setEstado({ fase: "erro", mensagem: "Sem conexão. Tente de novo." });
    }
    if (window.matchMedia("(max-width: 999px)").matches) {
      resultado.current?.scrollIntoView({ block: "start", behavior: semMovimento() ? "auto" : "smooth" });
    }
  }

  const puxar = () => {
    setEscolhido(null);
    buscar(`/api/publico/procedencia/${placa}`, placa);
  };

  /** Veio de um anúncio: a placa se preenche sozinha (protegida) e o laudo abre. */
  async function abrirDoAnuncio(v: VeiculoPublico) {
    const vez = ++corrida.current;
    setEscolhido(v.id);
    setEstado({ fase: "espera" });
    setFormato(v.tipo);
    const alvo = v.placa_mascarada ?? "";
    if (semMovimento()) setPlaca(alvo);
    else {
      setPlaca("");
      await pausa(350);
      for (let i = 1; i <= alvo.length; i++) {
        if (vez !== corrida.current) return;
        setPlaca(alvo.slice(0, i));
        await pausa(95);
      }
    }
    if (vez === corrida.current) buscar(`/api/publico/veiculos/${v.id}/procedencia`, alvo);
  }

  useImperativeHandle(controle, () => ({ abrirDoAnuncio }));

  function digitar(valor: string) {
    corrida.current++;
    setEscolhido(null);
    setPlaca(valor);
    if (estado.fase !== "espera") setEstado({ fase: "espera" });
  }

  const consultando = estado.fase === "consultando";
  const pronta = placaCompleta(placa) && !placa.includes("•");

  return (
    <section id="procedencia" className="pista" aria-labelledby="titulo-procedencia">
      <div className="pista__cabeca">
          <p className="sobretitulo" data-revelar>
            <span className="barras" aria-hidden>
              <i />
              <i />
              <i />
            </span>
            Procedência pela placa
          </p>
          <h2 id="titulo-procedencia" className="outdoor pista__titulo" data-revelar>
            Puxe a <em>placa.</em>
          </h2>
          <p className="pista__texto" data-revelar>
            Todo veículo da vitrine passa por consulta de roubo e furto, leilão, restrição judicial e dados
            cadastrais antes de ir à venda. Digite a placa de um veículo da loja e veja o resultado.
          </p>
      </div>

      <div className="pista__grade">
        <div className="pista__mesa" data-revelar>
          <div className="pista__bancada">
            <div className="formato" role="group" aria-label="Formato da placa">
              <button type="button" aria-pressed={formato === "moto"} onClick={() => trocarFormato("moto")}>
                Moto
              </button>
              <button type="button" aria-pressed={formato === "carro"} onClick={() => trocarFormato("carro")}>
                Carro
              </button>
            </div>

            <PlacaMercosul
              valor={placa}
              formato={formato}
              aoMudar={digitar}
              aoConfirmar={puxar}
              estado={consultando ? "consultando" : "livre"}
              rotulo="Placa do veículo (7 caracteres)"
              transicao
            />

            <button type="button" className="acao" disabled={!pronta || consultando} onClick={puxar}>
              {consultando ? "Lendo a placa" : "Puxar a placa"}
            </button>

            {veiculos.length > 0 && (
              <div className="pista__atalhos">
                <p className="dado">Não tem a placa? Escolha um da vitrine</p>
                <div>
                  {veiculos.slice(0, 6).map((v) => (
                    <button
                      key={v.id}
                      type="button"
                      className="atalho"
                      aria-pressed={escolhido === v.id}
                      onClick={() => abrirDoAnuncio(v)}
                    >
                      {v.modelo}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div ref={resultado} className="pista__resultado" aria-live="polite">
          {(estado.fase === "espera" || consultando) && (
            <div className="espera" data-consultando={consultando}>
              <div className="espera__topo">
                <Semaforo cor={null} tamanho="clamp(1.5rem, 4vw, 2.1rem)" />
                <p>{consultando ? "Conferindo…" : "O laudo aparece aqui"}</p>
              </div>
              <ul>
                {CONFERIDOS.map((item, i) => (
                  <li key={item} style={{ "--i": i } as React.CSSProperties}>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {estado.fase === "laudo" && (
            // a chave refaz a coreografia a cada novo laudo
            <div key={`${estado.laudo.veiculo.id}-${estado.laudo.placa}`}>
              <div className="achado">
                <p className="dado" style={{ fontSize: "0.72rem", color: "var(--amarelo)" }}>
                  Na vitrine da RC
                </p>
                <p className="outdoor achado__nome">
                  {estado.laudo.veiculo.marca} {estado.laudo.veiculo.modelo}
                </p>
                <p className="dado achado__ficha">
                  {estado.laudo.veiculo.ano_modelo && <span>{estado.laudo.veiculo.ano_modelo}</span>}
                  {estado.laudo.veiculo.km !== null && <span>{numero(estado.laudo.veiculo.km)} km</span>}
                  {estado.laudo.veiculo.cor && <span>{estado.laudo.veiculo.cor}</span>}
                  <span>{moeda(estado.laudo.veiculo.preco)}</span>
                </p>
              </div>
              <LaudoVisual
                semaforo={estado.laudo.semaforo}
                itens={estado.laudo.itens}
                historico={estado.laudo.historico}
                consultadoEm={estado.laudo.consultado_em}
                ilustrativo={estado.laudo.ilustrativo}
                semLaudo="A consulta deste veículo ainda não foi anexada. Peça o laudo para a loja."
              />
              <div className="pista__fecho">
                <a className="acao" href={linkVeiculo(estado.laudo.veiculo)} target="_blank" rel="noopener">
                  Quero essa
                </a>
                <a className="acao acao--linha acao--sem-seta" href="#vitrine">
                  Voltar à vitrine
                </a>
              </div>
            </div>
          )}

          {estado.fase === "fora" && (
            <div className="fora">
              <p>Essa não é da nossa vitrine.</p>
              <p>
                A placa {estado.placa} não está entre os veículos à venda na RC Motos. O laudo daqui vale para o
                que está na loja — confira a placa ou escolha um veículo da vitrine.
              </p>
              <div className="pista__fecho" style={{ marginTop: 0 }}>
                <a className="acao" href="#vitrine">
                  Ver a vitrine
                </a>
                <a className="acao acao--linha" href={linkLoja} target="_blank" rel="noopener">
                  Falar com a loja
                </a>
              </div>
            </div>
          )}

          {estado.fase === "erro" && (
            <div className="fora" role="alert">
              <p>Não deu para ler.</p>
              <p>{estado.mensagem}</p>
              <div className="pista__fecho" style={{ marginTop: 0 }}>
                <button type="button" className="acao" onClick={puxar} disabled={!pronta}>
                  Tentar de novo
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
