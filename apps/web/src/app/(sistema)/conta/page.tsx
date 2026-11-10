"use client";

import { useState } from "react";
import { useEu } from "@/components/Sessao";
import { Aviso, Botao, Campo, Cartao, Titulo, useAcao } from "@/components/ui";
import { api } from "@/lib/api";
import { PERFIL, regraDescrita } from "@/lib/formato";

export default function Conta() {
  const eu = useEu();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [repetir, setRepetir] = useState("");
  const [feito, setFeito] = useState(false);
  const { ocupado, erro, executar } = useAcao();
  const diferentes = repetir !== "" && nova !== repetir;

  function trocar(e: React.FormEvent) {
    e.preventDefault();
    if (diferentes) return;
    setFeito(false);
    executar(async () => {
      await api("/auth/trocar-senha", { corpo: { senha_atual: atual, nova_senha: nova } });
      setAtual("");
      setNova("");
      setRepetir("");
      setFeito(true);
    });
  }

  return (
    <>
      <Titulo sobre={PERFIL[eu.perfil]}>Minha conta</Titulo>
      <div className="grid gap-4 lg:grid-cols-2">
        <Cartao className="p-5 sm:p-6">
          <h2 className="mb-3 text-lg font-bold">Seus dados</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-suave">Nome</dt>
              <dd className="font-medium">{eu.nome}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-suave">E-mail</dt>
              <dd className="font-medium">{eu.email}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-suave">Comissão</dt>
              <dd className="font-medium">
                {eu.comissao_regra && eu.comissao_valor
                  ? regraDescrita(eu.comissao_regra, eu.comissao_valor)
                  : "Sem comissão"}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-suave">Para mudar nome, e-mail ou comissão, fale com o dono da loja.</p>
        </Cartao>

        <Cartao className="p-5 sm:p-6">
          <h2 className="mb-3 text-lg font-bold">Trocar senha</h2>
          <form onSubmit={trocar} className="space-y-3">
            <Campo
              rotulo="Senha atual"
              type="password"
              autoComplete="current-password"
              required
              value={atual}
              onChange={(e) => setAtual(e.target.value)}
            />
            <Campo
              rotulo="Nova senha"
              type="password"
              autoComplete="new-password"
              minLength={8}
              required
              value={nova}
              onChange={(e) => setNova(e.target.value)}
              dica="Mínimo de 8 caracteres."
            />
            <Campo
              rotulo="Repita a nova senha"
              type="password"
              autoComplete="new-password"
              required
              value={repetir}
              onChange={(e) => setRepetir(e.target.value)}
            />
            <Aviso>{diferentes ? "As senhas não são iguais." : erro}</Aviso>
            {feito && <Aviso tom="info">Senha trocada. Os outros aparelhos foram desconectados.</Aviso>}
            <Botao type="submit" ocupado={ocupado} disabled={diferentes}>
              Trocar senha
            </Botao>
          </form>
        </Cartao>
      </div>
    </>
  );
}
