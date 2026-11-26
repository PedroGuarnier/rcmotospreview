"use client";

import { Assistente } from "@/components/assistente/Assistente";
import { useEu, usePode } from "@/components/Sessao";

export default function Pagina() {
  const eu = useEu();
  const pode = usePode();
  // Cadastro: a mesma permissão do formulário. Perguntas: qualquer perfil, com a IA ligada.
  if (!pode("estoque.editar") && !eu.ia_ligada) {
    return (
      <div className="rounded-2xl bg-white p-10 text-center text-suave">
        Seu perfil não tem acesso a esta página.
      </div>
    );
  }
  return <Assistente />;
}
