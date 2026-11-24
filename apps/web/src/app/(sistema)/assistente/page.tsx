"use client";

import { Assistente } from "@/components/assistente/Assistente";
import { Exigir } from "@/components/Sessao";

export default function Pagina() {
  return (
    // a mesma permissão do formulário de cadastro
    <Exigir permissao="estoque.editar">
      <Assistente />
    </Exigir>
  );
}
