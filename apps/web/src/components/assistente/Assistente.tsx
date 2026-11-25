"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ErroApi, api, mensagemDe } from "@/lib/api";
import type { EstadoAssistente, RespostaAssistente } from "@/lib/tipos";
import { useEu, usePode } from "../Sessao";
import { Barras, Botao, Titulo } from "../ui";
import { Ficha } from "./Ficha";
import { type Mensagem, useConversa } from "./conversa";
import "./assistente.css";

// Frases de exemplo: mostram o jeito de escrever. Os dados são ilustrativos.
const EXEMPLOS = [
  "Honda CG 160 Fan 2022 vermelha, placa ABC1D23, 18.500 km, comprei por 11.500 e vou vender por 14.900",
  "chegou uma biz 125 2021 branca, 22 mil km, comprei por 9 mil",
  "fiat uno way 1.0 2015 prata, 98.000 km, compra R$ 24.000, venda R$ 31.900",
];

const BOAS_VINDAS =
  "Olá! Eu cadastro veículo novo no estoque por mensagem.\n" +
  "Escreva os dados do jeito que você fala, em qualquer ordem, e eu monto a ficha. " +
  "Antes de gravar eu mostro tudo e peço a sua confirmação.";

// O campo de texto lembra o que o assistente acabou de perguntar.
const DICA: Record<NonNullable<EstadoAssistente["aguardando"]>, string> = {
  marca: "Marca e modelo…",
  modelo: "Modelo…",
  tipo: "Moto ou carro?",
  valor_compra: "Valor de compra…",
  preco_venda: "Preço de venda…",
  placa: "Placa certa…",
  chassi: "Chassi certo…",
  confirmacao: "O que precisa corrigir?",
};

const LIMITE = 1000;
const pausa = (ms: number) => new Promise((ok) => setTimeout(ok, ms));
const semMovimento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const telaDeToque = () => window.matchMedia("(pointer: coarse)").matches;

// Falha de rede ou do servidor no meio de uma confirmação: o veículo pode ter sido gravado.
const CONFIRA_ANTES =
  " Se você estava confirmando o cadastro, veja no Estoque se o veículo entrou antes de confirmar de novo.";

function Avatar() {
  return (
    <span aria-hidden className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-tinta">
      <span className="scale-[0.62]">
        <Barras />
      </span>
    </span>
  );
}

function Balao({ de, children }: { de: Mensagem["de"]; children: React.ReactNode }) {
  if (de === "voce") {
    return (
      <div className="flex justify-end">
        <p className="entrar max-w-[85%] whitespace-pre-line break-words rounded-2xl rounded-br-md bg-azul px-4 py-2.5 text-[15px] leading-relaxed text-white sm:max-w-xl">
          <span className="sr-only">Você: </span>
          {children}
        </p>
      </div>
    );
  }
  if (de === "sistema") {
    return (
      <p role="alert" className="entrar mx-auto max-w-md rounded-xl bg-vermelho/10 px-4 py-2.5 text-center text-sm font-medium text-vermelho">
        {children}
      </p>
    );
  }
  return (
    <div className="flex items-start gap-2.5">
      <Avatar />
      <div className="entrar min-w-0 max-w-[85%] whitespace-pre-line break-words rounded-2xl rounded-tl-md border border-borda bg-white px-4 py-2.5 text-[15px] leading-relaxed sm:max-w-xl">
        <span className="sr-only">Assistente: </span>
        {children}
      </div>
    </div>
  );
}

const ATALHO =
  "inline-flex min-h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition-colors";

function Criado({
  veiculo,
  aoCadastrarOutro,
}: {
  veiculo: NonNullable<Mensagem["veiculo"]>;
  aoCadastrarOutro: () => void;
}) {
  const pode = usePode();
  return (
    <div className="entrar ml-[2.625rem] rounded-2xl border border-verde/30 bg-white p-4 sm:max-w-2xl">
      <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-verde">
        <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="9" />
          <path d="m8 12.5 3 3 5-6.5" />
        </svg>
        Veículo cadastrado
      </p>
      <p className="mt-1 text-lg font-bold leading-snug">{veiculo.descricao}</p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <Link href={`/estoque/${veiculo.id}`} className={`${ATALHO} bg-azul text-white hover:bg-azul-escuro`}>
          Abrir no estoque
        </Link>
        <Link href={`/estoque/${veiculo.id}`} className={`${ATALHO} border border-borda bg-white hover:border-azul`}>
          Adicionar fotos
        </Link>
        {veiculo.placa && pode("procedencia.consultar") && (
          <Link
            href={`/procedencia?placa=${veiculo.placa}`}
            className={`${ATALHO} border border-borda bg-white hover:border-azul`}
          >
            Consultar procedência
          </Link>
        )}
        <button type="button" onClick={aoCadastrarOutro} className={`${ATALHO} text-azul hover:bg-azul/10`}>
          Cadastrar outro
        </button>
      </div>
    </div>
  );
}

export function Assistente() {
  const eu = useEu();
  const { conversa, atual, gravar, limpar } = useConversa(eu.id);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const ocupado = useRef(false); // trava o envio duplo antes mesmo de a tela redesenhar
  const saindo = useRef(false); // a página está sendo fechada ou recarregada
  const secao = useRef<HTMLElement>(null);
  const historico = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);

  const { mensagens, ultima, estado } = conversa;
  const ultimaMensagem = mensagens.at(-1);
  const pedindoConfirmacao =
    !enviando && ultima?.acao === "confirmar" && ultimaMensagem?.de === "assistente";

  // Altura: a conversa vai do título até o rodapé. O topo muda com a faixa de demonstração
  // e, no celular, com o botão "Nova conversa" (que só aparece depois da primeira mensagem).
  const temMensagens = mensagens.length > 0;
  useEffect(() => {
    const el = secao.current;
    if (!el) return;
    const medir = () => el.style.setProperty("--topo", `${el.getBoundingClientRect().top + window.scrollY}px`);
    medir();
    window.addEventListener("resize", medir);
    document.fonts?.ready.then(medir).catch(() => undefined);
    return () => window.removeEventListener("resize", medir);
  }, [temMensagens]);

  // Teclado do celular: ele cobre a parte de baixo da página sem mudar o tamanho dela.
  // O visualViewport diz quanto ficou coberto, e o campo de texto sobe essa altura.
  useEffect(() => {
    const el = secao.current;
    const vv = window.visualViewport;
    if (!el || !vv) return;
    const ajustar = () => {
      const coberto = window.innerHeight - vv.height - vv.offsetTop;
      const teclado = Math.abs(vv.scale - 1) < 0.01 && coberto > 80 ? coberto : 0;
      el.style.setProperty("--teclado", `${Math.round(teclado)}px`);
    };
    ajustar();
    vv.addEventListener("resize", ajustar);
    vv.addEventListener("scroll", ajustar);
    return () => {
      vv.removeEventListener("resize", ajustar);
      vv.removeEventListener("scroll", ajustar);
    };
  }, []);

  // Recarregar com um pedido no ar cancela o pedido: isso não é falta de conexão.
  useEffect(() => {
    const marcar = () => {
      saindo.current = true;
    };
    const desmarcar = () => {
      saindo.current = false; // a página voltou do cache do navegador
    };
    window.addEventListener("beforeunload", marcar);
    window.addEventListener("pagehide", marcar);
    window.addEventListener("pageshow", desmarcar);
    return () => {
      window.removeEventListener("beforeunload", marcar);
      window.removeEventListener("pagehide", marcar);
      window.removeEventListener("pageshow", desmarcar);
    };
  }, []);

  // O campo cresce com o texto, até um limite.
  useEffect(() => {
    const el = campo.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [texto]);

  // Mensagem nova (ou conversa restaurada): rola até o fim.
  const jaRolou = useRef(false);
  useEffect(() => {
    if (mensagens.length === 0 && !enviando) return;
    const suave = jaRolou.current && !semMovimento();
    jaRolou.current = true;
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: suave ? "smooth" : "auto" });
  }, [mensagens.length, enviando]);

  /** `peloBotao`: o botão clicado some com a resposta, então o foco precisa de um novo lugar. */
  async function enviar(mensagem: string, peloBotao = false) {
    const limpa = mensagem.trim();
    if (!limpa || ocupado.current) return;
    ocupado.current = true;
    setEnviando(true);
    setTexto("");
    const antes = atual();
    const proximoId = (antes.mensagens.at(-1)?.id ?? 0) + 1;
    gravar({ ...antes, mensagens: [...antes.mensagens, { id: proximoId, de: "voce", texto: limpa }] });
    try {
      const [resposta] = await Promise.all([
        api<RespostaAssistente>("/assistente/mensagem", { corpo: { mensagem: limpa, estado: antes.estado } }),
        pausa(semMovimento() ? 0 : 450), // tempo de ler a própria mensagem antes da resposta
      ]);
      const agora = atual();
      gravar({
        mensagens: [
          ...agora.mensagens,
          {
            id: proximoId + 1,
            de: "assistente",
            texto: resposta.resposta,
            veiculo: resposta.veiculo,
            duplicado: resposta.duplicado,
          },
        ],
        estado: resposta.estado,
        ultima: resposta,
      });
    } catch (erro) {
      if (saindo.current) return; // a conversa guardada avisa da mensagem sem resposta
      const recusada = erro instanceof ErroApi && erro.status >= 400 && erro.status < 500;
      const confirmando = antes.estado?.aguardando === "confirmacao" && !recusada;
      const agora = atual();
      gravar({
        ...agora,
        mensagens: [
          ...agora.mensagens,
          { id: proximoId + 1, de: "sistema", texto: mensagemDe(erro) + (confirmando ? CONFIRA_ANTES : "") },
        ],
      });
      setTexto((digitado) => digitado || limpa); // devolve o texto para tentar de novo
    } finally {
      ocupado.current = false;
      setEnviando(false);
      if (peloBotao) {
        // no celular, focar o campo abriria o teclado em cima da resposta
        (telaDeToque() ? historico.current : campo.current)?.focus({ preventScroll: true });
      }
    }
  }

  function aoTeclar(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing) return;
    e.preventDefault();
    enviar(texto);
  }

  function focar() {
    campo.current?.focus();
  }

  function novaConversa() {
    limpar();
    setTexto("");
    jaRolou.current = false;
    window.scrollTo({ top: 0 });
    focar();
  }

  return (
    <>
      <Titulo
        sobre="Cadastre um veículo por mensagem"
        acoes={
          mensagens.length > 0 && (
            <Botao tom="neutro" pequeno onClick={novaConversa} disabled={enviando}>
              Nova conversa
            </Botao>
          )
        }
      >
        Assistente
      </Titulo>

      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_21rem] lg:items-start lg:gap-6">
        <section ref={secao} aria-label="Conversa com o assistente" className="assistente">
          <div
            ref={historico}
            role="log"
            aria-live="polite"
            aria-busy={enviando}
            tabIndex={-1}
            className="space-y-3 outline-none"
          >
            <Balao de="assistente">{BOAS_VINDAS}</Balao>

            {mensagens.length === 0 && (
              <div className="ml-[2.625rem]">
                <p className="mb-2 text-xs font-bold uppercase tracking-wider text-suave">
                  Exemplos — toque para usar como modelo
                </p>
                <ul className="space-y-2">
                  {EXEMPLOS.map((exemplo) => (
                    <li key={exemplo}>
                      <button
                        type="button"
                        onClick={() => {
                          setTexto(exemplo);
                          focar();
                        }}
                        className="flex w-full items-start gap-2.5 rounded-2xl border border-dashed border-azul/40 bg-white/70 px-3.5 py-2.5 text-left text-sm leading-snug transition-colors hover:border-azul hover:bg-white sm:max-w-xl"
                      >
                        <span className="mt-px shrink-0 rounded-full bg-amarelo/40 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide">
                          Exemplo
                        </span>
                        <span>{exemplo}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {mensagens.map((m) => {
              const ultimaDoAssistente = m === ultimaMensagem && m.de === "assistente";
              return (
                <div key={m.id} className="space-y-2">
                  <Balao de={m.de}>{m.texto}</Balao>
                  {m.duplicado && (
                    <p className="ml-[2.625rem] text-sm">
                      <Link
                        href={`/estoque/${m.duplicado.id}`}
                        className="font-semibold text-azul underline underline-offset-4"
                      >
                        Abrir {m.duplicado.descricao}
                      </Link>
                    </p>
                  )}
                  {m.veiculo && <Criado veiculo={m.veiculo} aoCadastrarOutro={focar} />}
                  {/* No celular a ficha vem junto da resposta; no computador fica na coluna ao lado. */}
                  {ultimaDoAssistente && ultima && ultima.ficha.length > 0 && (
                    <div className="ml-[2.625rem] lg:hidden">
                      <Ficha resposta={ultima} compacta />
                    </div>
                  )}
                  {ultimaDoAssistente && pedindoConfirmacao && (
                    <div className="ml-[2.625rem] grid grid-cols-2 gap-2 pt-1 sm:flex sm:flex-wrap">
                      <Botao onClick={() => enviar("sim", true)} className="col-span-2">
                        Confirmar cadastro
                      </Botao>
                      <Botao tom="neutro" onClick={focar}>
                        Corrigir
                      </Botao>
                      <Botao tom="fantasma" onClick={() => enviar("cancela", true)}>
                        Cancelar
                      </Botao>
                    </div>
                  )}
                </div>
              );
            })}

            {enviando && (
              <div className="flex items-start gap-2.5">
                <Avatar />
                <div className="rounded-2xl rounded-tl-md border border-borda bg-white px-4 py-2.5">
                  <span className="assistente__pontos" aria-hidden>
                    <i />
                    <i />
                    <i />
                  </span>
                  <span className="sr-only">O assistente está escrevendo…</span>
                </div>
              </div>
            )}
          </div>

          <form
            className="assistente__campo"
            onSubmit={(e) => {
              e.preventDefault();
              enviar(texto);
            }}
          >
            <div className="assistente__caixa flex items-end gap-2 rounded-[1.75rem] border border-borda bg-white p-1.5 pl-2 shadow-[0_8px_24px_-12px_rgb(10_9_64/0.35)]">
              <textarea
                ref={campo}
                rows={1}
                value={texto}
                maxLength={LIMITE}
                readOnly={enviando}
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={aoTeclar}
                enterKeyHint="send"
                autoComplete="off"
                aria-label="Mensagem para o assistente"
                placeholder={(estado?.aguardando && DICA[estado.aguardando]) || "Dados do veículo…"}
                className="max-h-[10.5rem] min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] leading-relaxed placeholder:text-suave/60"
              />
              <Botao type="submit" disabled={enviando || !texto.trim()} className="shrink-0">
                Enviar
              </Botao>
            </div>
            <p className="mt-1.5 hidden text-center text-xs text-suave lg:block">
              Enter envia · Shift+Enter quebra a linha
            </p>
          </form>
        </section>

        <aside className="sticky top-8 hidden lg:block">
          <Ficha resposta={ultima} />
        </aside>
      </div>
    </>
  );
}
