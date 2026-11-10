export class ErroApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

async function ler(resposta: Response) {
  if (resposta.status === 204) return null;
  const tipo = resposta.headers.get("content-type") ?? "";
  return tipo.includes("application/json") ? resposta.json() : null;
}

/** Chama a API pelo proxy do Next (`/api/...`). Lança ErroApi com a mensagem pronta para a tela. */
export async function api<T = unknown>(
  caminho: string,
  opcoes: { metodo?: string; corpo?: unknown; arquivo?: File } = {},
): Promise<T> {
  const init: RequestInit = { method: opcoes.metodo ?? (opcoes.corpo ? "POST" : "GET") };
  if (opcoes.arquivo) {
    const form = new FormData();
    form.append("arquivo", opcoes.arquivo);
    init.method = "POST";
    init.body = form;
  } else if (opcoes.corpo !== undefined) {
    init.headers = { "content-type": "application/json" };
    init.body = JSON.stringify(opcoes.corpo);
  }

  let resposta: Response;
  try {
    resposta = await fetch(`/api${caminho}`, init);
  } catch {
    throw new ErroApi(0, "Sem conexão. Confira a internet e tente de novo.");
  }
  const dados = await ler(resposta).catch(() => null);
  if (!resposta.ok) {
    const detalhe = typeof dados?.detail === "string" ? dados.detail : "Algo deu errado. Tente de novo.";
    throw new ErroApi(resposta.status, detalhe);
  }
  return dados as T;
}

export const buscar = <T,>(caminho: string) => api<T>(caminho);

export function mensagemDe(erro: unknown): string {
  return erro instanceof Error ? erro.message : "Algo deu errado. Tente de novo.";
}
