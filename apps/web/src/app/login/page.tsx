"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useSWRConfig } from "swr";
import { paginaInicial } from "@/components/Sessao";
import { Aviso, Barras, Botao, Campo, useAcao } from "@/components/ui";
import { api } from "@/lib/api";
import type { Eu } from "@/lib/tipos";

export default function Login() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const { ocupado, erro, executar } = useAcao();

  function entrar(e: React.FormEvent) {
    e.preventDefault();
    executar(async () => {
      const eu = await api<Eu>("/auth/entrar", { corpo: { email, senha } });
      await mutate("/auth/eu", eu, { revalidate: false });
      router.replace(paginaInicial(eu));
    });
  }

  return (
    <div className="relative grid min-h-dvh place-items-center overflow-hidden bg-tinta px-4 py-10">
      <div
        aria-hidden
        className="absolute -right-40 -top-40 size-[520px] rounded-full bg-azul/50 blur-3xl"
      />
      <div className="relative w-full max-w-sm">
        <div className="mb-8 text-center text-white">
          <Image src="/logo.png" alt="RC Motos — Deus é fiel" width={112} height={112} priority className="mx-auto" />
          <p className="mt-6 flex items-center justify-center gap-2 text-xs font-bold uppercase tracking-[0.25em] text-amarelo">
            <Barras /> Sistema da loja
          </p>
          <h1 className="display mt-2 text-4xl">
            RC Motos <span className="text-amarelo">Digital</span>
          </h1>
        </div>
        <form onSubmit={entrar} className="space-y-4 rounded-3xl bg-white p-6 shadow-2xl">
          <Campo
            rotulo="E-mail"
            type="email"
            autoComplete="username"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Campo
            rotulo="Senha"
            type="password"
            autoComplete="current-password"
            required
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
          <Aviso>{erro}</Aviso>
          <Botao type="submit" ocupado={ocupado} className="w-full">
            Entrar
          </Botao>
          <p className="text-center text-xs text-suave">
            Esqueceu a senha? Peça ao dono da loja para redefinir.
          </p>
        </form>
      </div>
    </div>
  );
}
