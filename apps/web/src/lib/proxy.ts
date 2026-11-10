/**
 * Repassa /api/* e /arquivos/* para a API (FastAPI).
 *
 * O navegador só fala com o Next: o cookie de sessão fica na mesma origem
 * (sem CORS) e o endereço da API é lido em tempo de execução (API_URL).
 */
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const REPASSAR_IDA = ["cookie", "content-type", "accept", "user-agent", "x-forwarded-for"];
const REPASSAR_VOLTA = ["content-type", "cache-control", "etag", "last-modified", "content-disposition"];

export async function repassar(req: Request, caminho: string[], prefixo = ""): Promise<Response> {
  const origem = new URL(req.url);
  const destino = `${API_URL}${prefixo}/${caminho.map(encodeURIComponent).join("/")}${origem.search}`;

  const headers = new Headers();
  for (const nome of REPASSAR_IDA) {
    const valor = req.headers.get(nome);
    if (valor) headers.set(nome, valor);
  }
  const temCorpo = !["GET", "HEAD"].includes(req.method);

  let resposta: Response;
  try {
    resposta = await fetch(destino, {
      method: req.method,
      headers,
      body: temCorpo ? await req.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: "Não foi possível falar com o servidor. Tente de novo em instantes." },
      { status: 502 },
    );
  }

  const saida = new Headers();
  for (const nome of REPASSAR_VOLTA) {
    const valor = resposta.headers.get(nome);
    if (valor) saida.set(nome, valor);
  }
  for (const cookie of resposta.headers.getSetCookie()) saida.append("set-cookie", cookie);
  return new Response(resposta.status === 204 ? null : resposta.body, {
    status: resposta.status,
    headers: saida,
  });
}
