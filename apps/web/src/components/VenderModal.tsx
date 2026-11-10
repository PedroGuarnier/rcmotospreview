"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { api, buscar } from "@/lib/api";
import { FORMA, hojeIso, moeda, telefone, valorParaApi, valorParaCampo } from "@/lib/formato";
import type { Cliente, FormaPagamento, PessoaRef, Veiculo, Venda } from "@/lib/tipos";
import { useEu, usePode } from "./Sessao";
import { Aviso, Botao, Campo, CampoValor, Modal, Rotulo, Selecao, useAcao } from "./ui";

/**
 * Baixa de venda em dois toques: "Vender" abre já preenchido (preço anunciado,
 * à vista, vendedor = quem está logado); falta só o comprador e "Confirmar venda".
 */
export function VenderModal({
  veiculo,
  aoFechar,
  aoVender,
}: {
  veiculo: Veiculo;
  aoFechar: () => void;
  aoVender: (venda: Venda) => void;
}) {
  const eu = useEu();
  const pode = usePode();
  const escolheVendedor = pode("vendas.ver_todas");
  const { data: vendedores } = useSWR<PessoaRef[]>(escolheVendedor ? "/usuarios/vendedores" : null, buscar);

  const [valor, setValor] = useState(valorParaCampo(veiculo.preco_venda));
  const [forma, setForma] = useState<FormaPagamento>("a_vista");
  const [vendedorId, setVendedorId] = useState(String(eu.id));
  const [dataVenda, setDataVenda] = useState(hojeIso());
  const [banco, setBanco] = useState("");
  const [entrada, setEntrada] = useState("");
  const [parcelas, setParcelas] = useState("");
  const [valorParcela, setValorParcela] = useState("");
  const [vencimento, setVencimento] = useState("");
  const [observacoes, setObservacoes] = useState("");

  // Comprador: escolhe um cliente já cadastrado ou digita um novo
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [nome, setNome] = useState("");
  const [fone, setFone] = useState("");
  const [cpf, setCpf] = useState("");
  const [busca, setBusca] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBusca(nome.trim()), 300);
    return () => clearTimeout(t);
  }, [nome]);
  const { data: sugestoes } = useSWR<Cliente[]>(
    !cliente && busca.length >= 3 ? `/clientes?busca=${encodeURIComponent(busca)}` : null,
    buscar,
  );

  const { ocupado, erro, executar } = useAcao();
  const valorApi = valorParaApi(valor);
  const lucro =
    veiculo.custo_total !== null && valorApi !== null ? Number(valorApi) - Number(veiculo.custo_total) : null;

  function confirmar(e: React.FormEvent) {
    e.preventDefault();
    executar(async () => {
      const corpo: Record<string, unknown> = {
        veiculo_id: veiculo.id,
        valor: valorApi,
        forma,
        vendedor_id: Number(vendedorId),
        data_venda: dataVenda,
        observacoes: observacoes || null,
      };
      if (cliente) corpo.cliente_id = cliente.id;
      else corpo.cliente_novo = { nome, telefone: fone || null, cpf_cnpj: cpf || null };
      if (forma !== "a_vista") corpo.entrada = valorParaApi(entrada);
      if (forma === "financiado_banco") corpo.banco = banco || null;
      if (forma === "parcelado_loja") {
        corpo.numero_parcelas = parcelas ? Number(parcelas) : null;
        corpo.valor_parcela = valorParaApi(valorParcela);
        corpo.primeiro_vencimento = vencimento || null;
      }
      aoVender(await api<Venda>("/vendas", { corpo }));
    });
  }

  return (
    <Modal titulo="Dar baixa na venda" aoFechar={aoFechar} largo>
      <form onSubmit={confirmar} className="space-y-4">
        <p className="rounded-xl bg-gelo px-4 py-3 text-sm">
          <b>{veiculo.descricao}</b>
          {veiculo.preco_venda && <> · anunciado por {moeda(veiculo.preco_venda)}</>}
        </p>

        {cliente ? (
          <Rotulo rotulo="Comprador">
            <div className="flex items-center justify-between gap-3 rounded-xl border border-borda px-3.5 py-2.5">
              <span className="text-[15px]">
                <b>{cliente.nome}</b>
                {cliente.telefone && <span className="text-suave"> · {telefone(cliente.telefone)}</span>}
              </span>
              <Botao tom="fantasma" pequeno onClick={() => setCliente(null)}>
                Trocar
              </Botao>
            </div>
          </Rotulo>
        ) : (
          <div className="space-y-3">
            <Campo
              rotulo="Comprador"
              placeholder="Nome completo"
              required
              autoFocus
              autoComplete="off"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
            />
            {sugestoes && sugestoes.length > 0 && (
              <div className="rounded-xl border border-borda p-2">
                <p className="px-2 pb-1 text-xs font-semibold text-suave">Já é cliente? Toque para usar o cadastro:</p>
                {sugestoes.slice(0, 4).map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setCliente(c)}
                    className="block w-full rounded-lg px-2 py-2 text-left text-sm hover:bg-gelo"
                  >
                    <b>{c.nome}</b>
                    {c.telefone && <span className="text-suave"> · {telefone(c.telefone)}</span>}
                  </button>
                ))}
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <Campo
                rotulo="WhatsApp do comprador"
                placeholder="(86) 99999-0000"
                inputMode="tel"
                autoComplete="off"
                value={fone}
                onChange={(e) => setFone(e.target.value)}
              />
              <Campo
                rotulo="CPF ou CNPJ (opcional)"
                autoComplete="off"
                value={cpf}
                onChange={(e) => setCpf(e.target.value)}
              />
            </div>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <CampoValor rotulo="Valor da venda" valor={valor} aoMudar={setValor} required />
          <Selecao
            rotulo="Forma de pagamento"
            valor={forma}
            aoMudar={setForma}
            opcoes={(Object.keys(FORMA) as FormaPagamento[]).map((f) => ({ valor: f, rotulo: FORMA[f] }))}
          />
        </div>

        {forma === "financiado_banco" && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo rotulo="Banco / financeira" value={banco} onChange={(e) => setBanco(e.target.value)} />
            <CampoValor rotulo="Entrada (opcional)" valor={entrada} aoMudar={setEntrada} />
          </div>
        )}
        {forma === "parcelado_loja" && (
          <div className="grid gap-3 sm:grid-cols-2">
            <CampoValor rotulo="Entrada (opcional)" valor={entrada} aoMudar={setEntrada} />
            <Campo
              rotulo="Nº de parcelas"
              inputMode="numeric"
              required
              value={parcelas}
              onChange={(e) => setParcelas(e.target.value.replace(/\D/g, ""))}
            />
            <CampoValor rotulo="Valor da parcela" valor={valorParcela} aoMudar={setValorParcela} required />
            <Campo
              rotulo="1º vencimento"
              type="date"
              required
              value={vencimento}
              onChange={(e) => setVencimento(e.target.value)}
            />
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {escolheVendedor && (
            <Selecao
              rotulo="Vendedor"
              valor={vendedorId}
              aoMudar={setVendedorId}
              opcoes={(vendedores ?? [{ id: eu.id, nome: eu.nome }]).map((v) => ({
                valor: String(v.id),
                rotulo: v.nome,
              }))}
            />
          )}
          <Campo
            rotulo="Data da venda"
            type="date"
            required
            max={hojeIso()}
            value={dataVenda}
            onChange={(e) => setDataVenda(e.target.value)}
          />
        </div>
        <Campo
          rotulo="Observações (opcional)"
          value={observacoes}
          onChange={(e) => setObservacoes(e.target.value)}
        />

        {lucro !== null && (
          <p className="rounded-xl bg-gelo px-4 py-3 text-sm">
            Lucro desta venda:{" "}
            <b className={`num ${lucro < 0 ? "text-vermelho" : "text-verde"}`}>{moeda(lucro)}</b>
            <span className="text-suave"> = venda − compra − custos ({moeda(veiculo.custo_total)})</span>
          </p>
        )}
        <Aviso>{erro}</Aviso>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Botao tom="neutro" onClick={aoFechar}>
            Voltar
          </Botao>
          <Botao tom="amarelo" type="submit" ocupado={ocupado}>
            Confirmar venda
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
