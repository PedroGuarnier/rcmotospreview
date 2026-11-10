"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { SITUACAO, SITUACOES_ESTOQUE, valorParaApi, valorParaCampo } from "@/lib/formato";
import type { Situacao, TipoVeiculo, VeiculoDetalhe } from "@/lib/tipos";
import { AreaTexto, Aviso, Botao, Campo, CampoValor, Selecao, useAcao } from "./ui";

const numeroOuNulo = (texto: string) => (texto.trim() ? Number(texto) : null);

/** Cadastro e edição de veículo. Na edição, a situação é mudada na própria página do veículo. */
export function FormVeiculo({
  veiculo,
  aoSalvar,
  aoCancelar,
}: {
  veiculo?: VeiculoDetalhe;
  aoSalvar: (veiculo: VeiculoDetalhe) => void;
  aoCancelar: () => void;
}) {
  const [tipo, setTipo] = useState<TipoVeiculo>(veiculo?.tipo ?? "moto");
  const [situacao, setSituacao] = useState<Situacao>("compra");
  const [f, setF] = useState({
    marca: veiculo?.marca ?? "",
    modelo: veiculo?.modelo ?? "",
    ano_fabricacao: veiculo?.ano_fabricacao?.toString() ?? "",
    ano_modelo: veiculo?.ano_modelo?.toString() ?? "",
    cor: veiculo?.cor ?? "",
    km: veiculo?.km?.toString() ?? "",
    placa: veiculo?.placa ?? "",
    chassi: veiculo?.chassi ?? "",
    renavam: veiculo?.renavam ?? "",
    data_compra: veiculo?.data_compra ?? "",
    observacoes: veiculo?.observacoes ?? "",
  });
  const [valorCompra, setValorCompra] = useState(valorParaCampo(veiculo?.valor_compra));
  const [precoVenda, setPrecoVenda] = useState(valorParaCampo(veiculo?.preco_venda));
  const { ocupado, erro, executar } = useAcao();

  const campo = (nome: keyof typeof f) => ({
    value: f[nome],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setF((atual) => ({ ...atual, [nome]: e.target.value })),
  });

  function salvar(e: React.FormEvent) {
    e.preventDefault();
    executar(async () => {
      const corpo: Record<string, unknown> = {
        tipo,
        marca: f.marca,
        modelo: f.modelo,
        ano_fabricacao: numeroOuNulo(f.ano_fabricacao),
        ano_modelo: numeroOuNulo(f.ano_modelo),
        cor: f.cor || null,
        km: numeroOuNulo(f.km),
        placa: f.placa || null,
        chassi: f.chassi || null,
        renavam: f.renavam || null,
        data_compra: f.data_compra || null,
        observacoes: f.observacoes || null,
        valor_compra: valorParaApi(valorCompra),
        preco_venda: valorParaApi(precoVenda),
      };
      if (!veiculo) corpo.situacao = situacao;
      const salvo = veiculo
        ? await api<VeiculoDetalhe>(`/veiculos/${veiculo.id}`, { metodo: "PATCH", corpo })
        : await api<VeiculoDetalhe>("/veiculos", { corpo });
      aoSalvar(salvo);
    });
  }

  return (
    <form onSubmit={salvar} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Selecao
          rotulo="Tipo"
          valor={tipo}
          aoMudar={setTipo}
          opcoes={[
            { valor: "moto", rotulo: "Moto" },
            { valor: "carro", rotulo: "Carro" },
          ]}
        />
        <Campo rotulo="Marca" placeholder="Honda" required {...campo("marca")} />
        <Campo rotulo="Modelo" placeholder="CG 160 Fan" required {...campo("modelo")} />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Campo rotulo="Ano fabricação" inputMode="numeric" maxLength={4} {...campo("ano_fabricacao")} />
        <Campo rotulo="Ano modelo" inputMode="numeric" maxLength={4} {...campo("ano_modelo")} />
        <Campo rotulo="Cor" {...campo("cor")} />
        <Campo rotulo="Km" inputMode="numeric" {...campo("km")} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Campo rotulo="Placa" placeholder="ABC1D23" maxLength={8} autoCapitalize="characters" {...campo("placa")} />
        <Campo rotulo="Chassi" maxLength={17} autoCapitalize="characters" {...campo("chassi")} />
        <Campo rotulo="RENAVAM" inputMode="numeric" maxLength={11} {...campo("renavam")} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <CampoValor rotulo="Valor de compra" valor={valorCompra} aoMudar={setValorCompra} required />
        <Campo rotulo="Data da compra" type="date" {...campo("data_compra")} />
        <CampoValor
          rotulo="Preço de venda"
          valor={precoVenda}
          aoMudar={setPrecoVenda}
          dica="Obrigatório para colocar à venda"
        />
      </div>
      {!veiculo && (
        <Selecao
          rotulo="Situação"
          valor={situacao}
          aoMudar={setSituacao}
          opcoes={SITUACOES_ESTOQUE.map((s) => ({ valor: s, rotulo: SITUACAO[s] }))}
          className="sm:max-w-xs"
        />
      )}
      <AreaTexto rotulo="Observações" {...campo("observacoes")} />
      <Aviso>{erro}</Aviso>
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Botao tom="neutro" onClick={aoCancelar}>
          Cancelar
        </Botao>
        <Botao type="submit" ocupado={ocupado}>
          {veiculo ? "Salvar alterações" : "Cadastrar veículo"}
        </Botao>
      </div>
    </form>
  );
}
