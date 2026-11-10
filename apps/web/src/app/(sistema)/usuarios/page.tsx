"use client";

import { useState } from "react";
import useSWR from "swr";
import { Exigir, useEu } from "@/components/Sessao";
import { Aviso, Botao, Campo, CampoValor, Carregando, Cartao, Etiqueta, Modal, Selecao, Titulo, useAcao } from "@/components/ui";
import { api, buscar, mensagemDe } from "@/lib/api";
import { PERFIL, REGRA, regraDescrita, valorParaApi, valorParaCampo } from "@/lib/formato";
import type { Perfil, RegraComissao, Usuario } from "@/lib/tipos";

const ACESSOS: Record<Perfil, string> = {
  dono: "Tudo, inclusive aportes e equipe.",
  gerente: "Estoque, vendas, painel e comissões.",
  financeiro: "Vendas e comissões (marca como paga).",
  vendedor: "Estoque, registrar venda e as próprias comissões.",
};

function FormUsuario({ usuario, aoFechar, aoSalvar }: { usuario?: Usuario; aoFechar: () => void; aoSalvar: () => void }) {
  const eu = useEu();
  const [nome, setNome] = useState(usuario?.nome ?? "");
  const [email, setEmail] = useState(usuario?.email ?? "");
  const [senha, setSenha] = useState("");
  const [perfil, setPerfil] = useState<Perfil>(usuario?.perfil ?? "vendedor");
  const [ativo, setAtivo] = useState(usuario?.ativo ?? true);
  const [aportes, setAportes] = useState(usuario?.acesso_aportes ?? false);
  const [regra, setRegra] = useState<RegraComissao | "">(usuario?.comissao_regra ?? "");
  const [regraValor, setRegraValor] = useState(
    usuario?.comissao_valor
      ? usuario.comissao_regra === "valor_fixo"
        ? valorParaCampo(usuario.comissao_valor)
        : String(Number(usuario.comissao_valor)).replace(".", ",")
      : "",
  );
  const { ocupado, erro, executar } = useAcao();
  const euMesmo = usuario?.id === eu.id;

  function salvar(e: React.FormEvent) {
    e.preventDefault();
    executar(async () => {
      const corpo: Record<string, unknown> = {
        nome,
        email,
        perfil,
        acesso_aportes: aportes,
        comissao_regra: regra || null,
        comissao_valor: regra ? valorParaApi(regraValor) : null,
      };
      if (usuario) {
        corpo.ativo = ativo;
        await api(`/usuarios/${usuario.id}`, { metodo: "PATCH", corpo });
        if (senha) await api(`/usuarios/${usuario.id}/redefinir-senha`, { corpo: { nova_senha: senha } });
      } else {
        await api("/usuarios", { corpo: { ...corpo, senha } });
      }
      aoSalvar();
      aoFechar();
    });
  }

  return (
    <Modal titulo={usuario ? "Editar pessoa" : "Nova pessoa na equipe"} aoFechar={aoFechar}>
      <form onSubmit={salvar} className="space-y-4">
        <Campo rotulo="Nome" required value={nome} onChange={(e) => setNome(e.target.value)} />
        <Campo
          rotulo="E-mail (usado para entrar)"
          type="email"
          required
          autoComplete="off"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Campo
          rotulo={usuario ? "Nova senha (deixe em branco para manter)" : "Senha inicial"}
          type="password"
          autoComplete="new-password"
          minLength={8}
          required={!usuario}
          disabled={euMesmo}
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          dica={euMesmo ? "Para trocar a sua senha, use “Minha conta”." : "Mínimo de 8 caracteres."}
        />
        <Selecao
          rotulo="Perfil de acesso"
          valor={perfil}
          aoMudar={setPerfil}
          disabled={euMesmo}
          opcoes={(Object.keys(PERFIL) as Perfil[]).map((p) => ({ valor: p, rotulo: PERFIL[p] }))}
        />
        <p className="-mt-2 text-xs text-suave">{ACESSOS[perfil]}</p>

        <div className="grid gap-3 sm:grid-cols-2">
          <Selecao
            rotulo="Comissão por venda"
            valor={regra}
            aoMudar={setRegra}
            opcoes={[
              { valor: "", rotulo: "Sem comissão" },
              ...(Object.keys(REGRA) as RegraComissao[]).map((r) => ({ valor: r, rotulo: REGRA[r] })),
            ]}
          />
          {regra === "valor_fixo" && (
            <CampoValor rotulo="Valor por venda" valor={regraValor} aoMudar={setRegraValor} required />
          )}
          {(regra === "percentual_lucro" || regra === "percentual_venda") && (
            <Campo
              rotulo="Percentual (%)"
              inputMode="decimal"
              required
              placeholder="10"
              value={regraValor}
              onChange={(e) => setRegraValor(e.target.value.replace(/[^\d.,]/g, ""))}
            />
          )}
        </div>

        {perfil !== "dono" && (
          <label className="flex items-start gap-2.5 text-sm">
            <input
              type="checkbox"
              checked={aportes}
              onChange={(e) => setAportes(e.target.checked)}
              className="mt-0.5 size-4 accent-azul"
            />
            <span>
              <b>Pode ver os aportes</b>
              <span className="block text-xs text-suave">Gastos pessoais do dono investidos na loja.</span>
            </span>
          </label>
        )}
        {usuario && !euMesmo && (
          <label className="flex items-center gap-2.5 text-sm">
            <input
              type="checkbox"
              checked={ativo}
              onChange={(e) => setAtivo(e.target.checked)}
              className="size-4 accent-azul"
            />
            <b>Acesso ativo</b>
            <span className="text-xs text-suave">(desmarque para bloquear a entrada)</span>
          </label>
        )}

        <Aviso>{erro}</Aviso>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Botao tom="neutro" onClick={aoFechar}>
            Cancelar
          </Botao>
          <Botao type="submit" ocupado={ocupado}>
            Salvar
          </Botao>
        </div>
      </form>
    </Modal>
  );
}

function Conteudo() {
  const { data: usuarios, error, mutate } = useSWR<Usuario[]>("/usuarios", buscar);
  const [editando, setEditando] = useState<Usuario | "novo" | null>(null);

  return (
    <>
      <Titulo sobre="Logins e permissões" acoes={<Botao onClick={() => setEditando("novo")}>+ Nova pessoa</Botao>}>
        Equipe
      </Titulo>
      {error && <Aviso>{mensagemDe(error)}</Aviso>}
      {!usuarios && !error && <Carregando />}
      {usuarios && (
        <Cartao className="divide-y divide-borda">
          {usuarios.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => setEditando(u)}
              className={`flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left hover:bg-gelo/60 sm:px-5 ${
                u.ativo ? "" : "opacity-60"
              }`}
            >
              <span className="min-w-0">
                <span className="block truncate font-semibold">{u.nome}</span>
                <span className="block truncate text-sm text-suave">
                  {u.email}
                  {u.comissao_regra && u.comissao_valor && ` · ${regraDescrita(u.comissao_regra, u.comissao_valor)}`}
                </span>
              </span>
              <span className="flex shrink-0 flex-wrap justify-end gap-1.5">
                {!u.ativo && <Etiqueta cor="vermelho">Desativado</Etiqueta>}
                {u.acesso_aportes && u.perfil !== "dono" && <Etiqueta cor="amarelo">Vê aportes</Etiqueta>}
                <Etiqueta cor={u.perfil === "dono" ? "azul" : "cinza"}>{PERFIL[u.perfil]}</Etiqueta>
              </span>
            </button>
          ))}
        </Cartao>
      )}
      {editando && (
        <FormUsuario
          usuario={editando === "novo" ? undefined : editando}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => mutate()}
        />
      )}
    </>
  );
}

export default function Pagina() {
  return (
    <Exigir permissao="usuarios.gerir">
      <Conteudo />
    </Exigir>
  );
}
