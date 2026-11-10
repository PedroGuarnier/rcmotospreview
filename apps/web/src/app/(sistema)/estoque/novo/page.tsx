"use client";

import { useRouter } from "next/navigation";
import { FormVeiculo } from "@/components/FormVeiculo";
import { Exigir } from "@/components/Sessao";
import { Cartao, Titulo } from "@/components/ui";

export default function NovoVeiculo() {
  const router = useRouter();
  return (
    <Exigir permissao="estoque.editar">
      <Titulo sobre="Estoque">Novo veículo</Titulo>
      <Cartao className="p-5 sm:p-7">
        <FormVeiculo
          aoSalvar={(v) => router.replace(`/estoque/${v.id}`)}
          aoCancelar={() => router.push("/estoque")}
        />
      </Cartao>
      <p className="mt-3 text-sm text-suave">
        Depois de cadastrar você adiciona as fotos e os custos na página do veículo.
      </p>
    </Exigir>
  );
}
