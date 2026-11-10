import { data } from "@/lib/formato";
import type { ItemLaudo, MarcoHistorico, Semaforo as Cor } from "@/lib/tipos";
import "./placa.css";

const VEREDITO: Record<Cor, { titulo: string; frase: string }> = {
  verde: { titulo: "Nada consta", frase: "Sem roubo, furto, leilão ou restrição judicial." },
  amarelo: { titulo: "Ponto de atenção", frase: "Tem um item para olhar com calma antes de fechar." },
  vermelho: { titulo: "Restrição encontrada", frase: "Há restrição registrada para este veículo." },
};

export function Semaforo({
  cor,
  deitado,
  tamanho,
}: {
  cor: Cor | null;
  deitado?: boolean;
  tamanho?: string;
}) {
  const rotulo = cor ? `Semáforo ${cor}` : "Semáforo apagado";
  return (
    <span
      className="semaforo"
      role="img"
      aria-label={rotulo}
      data-deitado={deitado}
      style={tamanho ? ({ "--semaforo-tam": tamanho } as React.CSSProperties) : undefined}
    >
      {(["vermelho", "amarelo", "verde"] as const).map((lampada) => (
        <i key={lampada} data-acesa={cor === lampada ? lampada : undefined} />
      ))}
    </span>
  );
}

/** O resultado da consulta: semáforo, os quatro itens e a linha do tempo em forma de estrada. */
export function LaudoVisual({
  semaforo,
  itens,
  historico,
  consultadoEm,
  ilustrativo,
  semLaudo,
}: {
  semaforo: Cor | null;
  itens: ItemLaudo[];
  historico: MarcoHistorico[];
  consultadoEm: string | null;
  ilustrativo: boolean;
  /** texto para quando o veículo ainda não tem laudo */
  semLaudo?: string;
}) {
  const veredito = semaforo ? VEREDITO[semaforo] : null;
  return (
    <div className="laudo">
      <div className="laudo__veredito">
        <Semaforo cor={semaforo} tamanho="clamp(1.5rem, 4vw, 2.1rem)" />
        <div>
          <p className="laudo__titulo">{veredito ? veredito.titulo : "Laudo em preparação"}</p>
          <p className="laudo__sub">
            {veredito ? veredito.frase : (semLaudo ?? "A consulta deste veículo ainda não foi anexada.")}
            {consultadoEm && <> Consulta de {data(consultadoEm)}.</>}
            {ilustrativo && <span className="laudo__selo">Ilustrativo</span>}
          </p>
        </div>
      </div>

      {itens.length > 0 && (
        <ul className="laudo__itens">
          {itens.map((item, i) => (
            <li
              key={item.chave}
              className="laudo__item"
              data-situacao={item.situacao}
              style={{ "--i": i } as React.CSSProperties}
            >
              <i className="laudo__lampada" aria-hidden />
              <strong>{item.titulo}</strong>
              <span>{item.detalhe}</span>
            </li>
          ))}
        </ul>
      )}

      {historico.length > 0 && (
        <ol className="estrada" aria-label="Linha do tempo do veículo">
          {historico.map((marco, i) => (
            <li key={i} className="estrada__marco" style={{ "--i": i } as React.CSSProperties}>
              <p className="estrada__quando">{marco.quando}</p>
              <p className="estrada__titulo">{marco.titulo}</p>
              {marco.detalhe && <p className="estrada__detalhe">{marco.detalhe}</p>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
