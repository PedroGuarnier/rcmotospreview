"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { paginaInicial } from "@/components/Sessao";
import { Carregando } from "@/components/ui";
import type { Eu } from "@/lib/tipos";

/** Raiz: manda para o painel/estoque se estiver logado; senão, para o login. */
export default function Inicio() {
  const router = useRouter();
  useEffect(() => {
    api<Eu>("/auth/eu")
      .then((eu) => router.replace(paginaInicial(eu)))
      .catch(() => router.replace("/login"));
  }, [router]);
  return <Carregando />;
}
