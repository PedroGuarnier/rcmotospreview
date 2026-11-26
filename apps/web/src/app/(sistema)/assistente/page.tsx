"use client";

import { Assistente } from "@/components/assistente/Assistente";
import { PERMISSOES_DO_ASSISTENTE, useEu, usePode } from "@/components/Sessao";

export default function Pagina() {
  const eu = useEu();
  const pode = usePode();
  // Cadastrar/alterar (estoque.editar) ou vender (vendas.registrar) por mensagem; perguntas:
  // qualquer perfil, com a IA ligada.
  if (!PERMISSOES_DO_ASSISTENTE.some((p) => pode(p)) && !eu.ia_ligada) {
    return (
      <div className="rounded-2xl bg-white p-10 text-center text-suave">
        Seu perfil não tem acesso a esta página.
      </div>
    );
  }
  return <Assistente />;
}
