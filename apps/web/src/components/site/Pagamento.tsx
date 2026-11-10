"use client";

import { useState } from "react";
import { moeda, valorParaApi, valorParaCampo } from "@/lib/formato";
import { linkWhats } from "@/lib/loja";
import type { VeiculoPublico } from "@/lib/tipos";

const FORMAS = [
  { valor: "avista", rotulo: "À vista", parcela: false },
  { valor: "banco", rotulo: "Financiado", parcela: true },
  { valor: "loja", rotulo: "Parcelado na loja", parcela: true },
] as const;
type Forma = (typeof FORMAS)[number]["valor"];
const PRAZOS = [6, 10, 12, 18, 24, 36, 48];

export function Pagamento({ veiculos, whatsapp }: { veiculos: VeiculoPublico[]; whatsapp: string | null }) {
  const [veiculoId, setVeiculoId] = useState("");
  const [forma, setForma] = useState<Forma>("loja");
  const [entrada, setEntrada] = useState("");
  const [prazo, setPrazo] = useState(2); // índice em PRAZOS
  const [troca, setTroca] = useState(false);
  const [usada, setUsada] = useState("");

  const veiculo = veiculos.find((v) => String(v.id) === veiculoId);
  const parcelado = FORMAS.find((f) => f.valor === forma)!.parcela;
  const entradaApi = valorParaApi(entrada);

  const linhas = [
    "Olá! Quero montar uma proposta pelo site.",
    veiculo
      ? `• Veículo: ${veiculo.marca} ${veiculo.modelo}${veiculo.ano_modelo ? ` ${veiculo.ano_modelo}` : ""} (${moeda(veiculo.preco)})`
      : "• Veículo: ainda estou escolhendo",
    `• Pagamento: ${FORMAS.find((f) => f.valor === forma)!.rotulo.toLowerCase()}`,
  ];
  if (parcelado) {
    if (entradaApi && Number(entradaApi) > 0) linhas.push(`• Entrada: ${moeda(entradaApi)}`);
    linhas.push(`• Parcelas: em ${PRAZOS[prazo]} vezes`);
  }
  if (troca) linhas.push(`• Tenho uma usada para a troca${usada.trim() ? `: ${usada.trim()}` : ""}`);
  const mensagem = linhas.join("\n");

  return (
    <section id="pagamento" className="solar" aria-labelledby="titulo-pagamento">
      <div className="solar__grade">
        <div>
          <p className="sobretitulo" data-revelar>
            <span className="barras" aria-hidden>
              <i />
              <i />
              <i />
            </span>
            Como pagar
          </p>
          <h2 id="titulo-pagamento" className="outdoor solar__titulo" data-revelar>
            Do jeito que cabe.
          </h2>
          <ol className="jeitos">
            <li data-revelar>
              <strong>À vista</strong>
              <span>Fechou o valor, a moto é sua.</span>
            </li>
            <li data-revelar>
              <strong>Financiado pelo banco</strong>
              <span>A loja monta a proposta com o banco e avisa você da resposta.</span>
            </li>
            <li data-revelar>
              <strong>Parcelado na loja</strong>
              <span>Entrada e parcelas combinadas direto com a RC.</span>
            </li>
            <li data-revelar>
              <strong>Sua usada na troca</strong>
              <span>A gente avalia sua moto ou carro como parte do pagamento.</span>
            </li>
          </ol>
        </div>

        <form
          className="proposta"
          data-revelar
          data-sem-zap
          onSubmit={(e) => {
            e.preventDefault();
            window.open(linkWhats(whatsapp, mensagem), "_blank", "noopener");
          }}
        >
          <div>
            <p className="outdoor proposta__titulo">Monte sua proposta</p>
            <p style={{ color: "var(--nevoa)", marginTop: "0.5rem", lineHeight: 1.5 }}>
              Você diz como quer pagar; a loja responde com os valores no WhatsApp.
            </p>
          </div>

          <div>
            <label htmlFor="proposta-veiculo">Veículo</label>
            <select id="proposta-veiculo" value={veiculoId} onChange={(e) => setVeiculoId(e.target.value)}>
              <option value="">Ainda estou escolhendo</option>
              {veiculos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.marca} {v.modelo} {v.ano_modelo ?? ""} — {moeda(v.preco)}
                </option>
              ))}
            </select>
          </div>

          <fieldset>
            <legend>Pagamento</legend>
            <div className="proposta__opcoes">
              {FORMAS.map((f) => (
                <button key={f.valor} type="button" aria-pressed={forma === f.valor} onClick={() => setForma(f.valor)}>
                  {f.rotulo}
                </button>
              ))}
            </div>
          </fieldset>

          {parcelado && (
            <div className="proposta__dupla">
              <div>
                <label htmlFor="proposta-entrada">Entrada (R$)</label>
                <input
                  id="proposta-entrada"
                  type="text"
                  inputMode="decimal"
                  placeholder="Sem entrada"
                  autoComplete="off"
                  value={entrada}
                  onChange={(e) => setEntrada(e.target.value.replace(/[^\d.,]/g, ""))}
                  onBlur={() => entradaApi && setEntrada(valorParaCampo(entradaApi))}
                />
              </div>
              <div>
                <label id="rotulo-prazo">Parcelas</label>
                <div className="passo" role="group" aria-labelledby="rotulo-prazo">
                  <button type="button" aria-label="Menos parcelas" disabled={prazo === 0} onClick={() => setPrazo(prazo - 1)}>
                    −
                  </button>
                  <output aria-live="polite">{PRAZOS[prazo]}×</output>
                  <button
                    type="button"
                    aria-label="Mais parcelas"
                    disabled={prazo === PRAZOS.length - 1}
                    onClick={() => setPrazo(prazo + 1)}
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
          )}

          <div>
            <label className="troca" style={{ fontFamily: "inherit", letterSpacing: 0, textTransform: "none", fontSize: "1rem", color: "#fff", marginBottom: 0 }}>
              <input type="checkbox" checked={troca} onChange={(e) => setTroca(e.target.checked)} />
              Tenho uma usada para dar na troca
            </label>
            {troca && (
              <input
                type="text"
                aria-label="Qual é a sua usada? (modelo e ano)"
                placeholder="Qual? Ex.: CG 150, 2015"
                value={usada}
                onChange={(e) => setUsada(e.target.value)}
                style={{ marginTop: "0.7rem" }}
                maxLength={80}
              />
            )}
          </div>

          <div>
            <p className="dado" style={{ fontSize: "0.7rem", color: "var(--nevoa)", marginBottom: "0.5rem" }}>
              A mensagem que vai para a loja
            </p>
            <p className="balao" aria-live="polite">
              {mensagem}
            </p>
          </div>

          <button type="submit" className="acao">
            Enviar no WhatsApp
          </button>
        </form>
      </div>
    </section>
  );
}
