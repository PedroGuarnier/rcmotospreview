import Link from "next/link";
import type { RespostaAssistente } from "@/lib/tipos";
import { Etiqueta } from "../ui";

type Modo = "cadastro" | "venda" | "edicao";

const TITULO: Record<Modo, string> = {
  cadastro: "Ficha do veículo",
  venda: "Ficha da venda",
  edicao: "Alteração do veículo",
};
const PRONTA: Record<Modo, string> = {
  cadastro: "Pronta para cadastrar",
  venda: "Pronta para registrar",
  edicao: "Pronta para salvar",
};

function Situacao({ resposta, modo }: { resposta: RespostaAssistente; modo: Modo }) {
  if (resposta.duplicado) {
    return <Etiqueta cor="vermelho">{resposta.duplicado.campo === "placa" ? "Placa repetida" : "Chassi repetido"}</Etiqueta>;
  }
  if (resposta.pronto) return <Etiqueta cor="verde">{PRONTA[modo]}</Etiqueta>;
  const faltam = resposta.faltando.length;
  if (faltam === 0) return <Etiqueta cor="laranja">Em andamento</Etiqueta>;
  return <Etiqueta cor="laranja">{faltam === 1 ? "Falta 1 campo" : `Faltam ${faltam} campos`}</Etiqueta>;
}

function Vazia({ cadastra }: { cadastra: boolean }) {
  const itens = cadastra ? ["Marca e modelo", "Tipo (moto ou carro)", "Valor de compra"] : ["Veículo (placa ou modelo)", "Comprador", "Valor e forma de pagamento"];
  return (
    <div className="text-sm text-suave">
      <p>O que eu entender das suas mensagens aparece aqui, campo por campo.</p>
      <p className="mt-3 font-semibold text-tinta">
        {cadastra ? "Para cadastrar eu preciso de:" : "Para registrar a venda eu preciso de:"}
      </p>
      <ul className="mt-1.5 space-y-1">
        {itens.map((nome) => (
          <li key={nome} className="flex items-center gap-2">
            <span aria-hidden className="size-1.5 rounded-full bg-azul" />
            {nome}
          </li>
        ))}
      </ul>
      <p className="mt-3">
        {cadastra
          ? "Ano, cor, km, placa, data da compra e preço de venda são opcionais. Também dá para alterar um veículo do estoque ou registrar uma venda."
          : "O vendedor é você. A data da venda, se você não disser, é hoje."}
      </p>
    </div>
  );
}

/**
 * Ficha do que está em andamento: cadastro, venda ou alteração. Os valores chegam prontos do
 * servidor (R$ 11.500,00, 18.500 km, ABC-1D23): aqui é só desenhar. Na alteração, cada campo
 * mostra o antes → depois.
 */
export function Ficha({
  resposta,
  cadastra = true,
  compacta,
}: {
  /** última resposta do assistente; null antes da primeira mensagem */
  resposta: RespostaAssistente | null;
  /** quem pode cadastrar veículo (a ficha vazia explica o cadastro; senão, a venda) */
  cadastra?: boolean;
  /** versão de dentro da conversa, no celular */
  compacta?: boolean;
}) {
  const itens = resposta?.ficha ?? [];
  const dados = itens.filter((i) => !i.calculado);
  const calculados = itens.filter((i) => i.calculado);
  const vazia = !resposta || dados.length === 0;
  const modo: Modo = resposta?.estado.modo ?? "cadastro";

  return (
    <section aria-label={TITULO[modo]} className={`rounded-2xl border border-borda bg-white ${compacta ? "p-4" : "p-5"}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className={`display leading-none ${compacta ? "text-lg" : "text-xl"}`}>{TITULO[modo]}</h2>
        {!vazia && <Situacao resposta={resposta} modo={modo} />}
      </div>

      {vazia ? (
        <Vazia cadastra={cadastra} />
      ) : (
        <>
          <dl className={compacta ? "grid grid-cols-2 gap-x-4 gap-y-2.5" : "divide-y divide-borda"}>
            {dados.map((item) => {
              const larga = item.campo === "observacoes" || item.campo === "veiculo" || Boolean(item.antes);
              return (
                <div
                  key={item.campo}
                  className={
                    compacta
                      ? larga
                        ? "col-span-2"
                        : ""
                      : "flex items-baseline justify-between gap-4 py-2 first:pt-0"
                  }
                >
                  <dt className={`shrink-0 text-suave ${compacta ? "text-xs" : "text-sm"}`}>{item.rotulo}</dt>
                  <dd className={`num min-w-0 break-words font-semibold ${compacta ? "text-sm" : "text-right text-[15px]"}`}>
                    {item.antes ? (
                      <>
                        <span className="font-normal text-suave line-through decoration-suave/60">{item.antes}</span>
                        <span aria-hidden className="mx-1.5 text-suave">
                          →
                        </span>
                        <span className="sr-only"> passa a ser </span>
                        <span className="text-azul">{item.valor}</span>
                      </>
                    ) : (
                      item.valor
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>

          {calculados.length > 0 && (
            <dl className="mt-3 space-y-1 rounded-xl bg-gelo px-3 py-2.5 text-sm">
              {calculados.map((item) => (
                <div key={item.campo} className="flex items-baseline justify-between gap-4">
                  <dt className="text-suave">{item.rotulo}</dt>
                  <dd
                    className={`num font-bold ${
                      item.campo !== "lucro_previsto"
                        ? ""
                        : item.valor.includes("-")
                          ? "text-vermelho"
                          : "text-verde"
                    }`}
                  >
                    {item.antes && item.antes !== item.valor && (
                      <span className="mr-1.5 font-normal text-suave line-through">{item.antes}</span>
                    )}
                    {item.valor}
                  </dd>
                </div>
              ))}
            </dl>
          )}

          {resposta.faltando.length > 0 && (
            <div className="mt-3">
              <p className="mb-1.5 text-xs font-bold uppercase tracking-wider text-laranja">
                {modo === "venda" ? "Falta para registrar" : "Falta para cadastrar"}
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {resposta.faltando.map((campo) => (
                  <li
                    key={campo.campo}
                    className="rounded-full border border-dashed border-laranja/60 bg-laranja/5 px-2.5 py-0.5 text-xs font-semibold text-laranja"
                  >
                    {campo.rotulo}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {resposta.duplicado && (
            <p className="mt-3 rounded-xl bg-vermelho/10 px-3 py-2 text-sm text-vermelho">
              {resposta.duplicado.campo === "placa" ? "Esta placa" : "Este chassi"} já está em{" "}
              <Link href={`/estoque/${resposta.duplicado.id}`} className="font-semibold underline underline-offset-2">
                {resposta.duplicado.descricao}
              </Link>
              .
            </p>
          )}

          {resposta.sugeridos.length > 0 && resposta.faltando.length === 0 && (
            <p className="mt-3 text-xs text-suave">
              Opcional, se quiser acrescentar: {resposta.sugeridos.map((c) => c.rotulo).join(" · ")}
            </p>
          )}

          {resposta.avisos.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {resposta.avisos.map((aviso) => (
                <li key={aviso} className="flex gap-2 rounded-xl bg-amarelo/25 px-3 py-2 text-xs leading-snug">
                  <span aria-hidden className="font-bold">
                    !
                  </span>
                  <span>{aviso}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
