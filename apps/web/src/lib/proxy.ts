/**
 * Repassa /api/* e /arquivos/* para a API (FastAPI).
 *
 * O navegador só fala com o Next: o cookie de sessão fica na mesma origem
 * (sem CORS) e o endereço da API é lido em tempo de execução (API_URL).
 */
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const REPASSAR_IDA = ["cookie", "content-type", "accept", "user-agent"];

// Maior corpo aceito (a maior coisa enviada é uma foto, de até 15 MB).
const LIMITE_CORPO = 20 * 1024 * 1024;

/** Lê o corpo da requisição, desistindo se passar do limite (não deixa encher a memória). */
async function lerCorpo(req: Request): Promise<ArrayBuffer | null> {
  if (Number(req.headers.get("content-length") ?? 0) > LIMITE_CORPO) return null;
  if (!req.body) return new ArrayBuffer(0);
  const leitor = req.body.getReader();
  const partes: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await leitor.read();
    if (done) break;
    total += value.byteLength;
    if (total > LIMITE_CORPO) {
      await leitor.cancel();
      return null;
    }
    partes.push(value);
  }
  const corpo = new Uint8Array(total);
  let posicao = 0;
  for (const parte of partes) {
    corpo.set(parte, posicao);
    posicao += parte.byteLength;
  }
  return corpo.buffer;
}
const REPASSAR_VOLTA = ["content-type", "cache-control", "etag", "last-modified", "content-disposition"];

export async function repassar(req: Request, caminho: string[], prefixo = ""): Promise<Response> {
  const origem = new URL(req.url);
  const destino = `${API_URL}${prefixo}/${caminho.map(encodeURIComponent).join("/")}${origem.search}`;

  const headers = new Headers();
  for (const nome of REPASSAR_IDA) {
    const valor = req.headers.get(nome);
    if (valor) headers.set(nome, valor);
  }
  // IP de quem chamou: só o último salto do X-Forwarded-For, que é o que o proxy da frente
  // (Caddy) escreveu. O que o próprio cliente mandar nesse cabeçalho não é repassado.
  const salto = req.headers.get("x-forwarded-for")?.split(",").pop()?.trim();
  if (salto) headers.set("x-forwarded-for", salto);

  const temCorpo = !["GET", "HEAD"].includes(req.method);
  const corpo = temCorpo ? await lerCorpo(req) : undefined;
  if (corpo === null) {
    return Response.json({ detail: "Arquivo grande demais (máximo de 20 MB)." }, { status: 413 });
  }

  let resposta: Response;
  try {
    resposta = await fetch(destino, {
      method: req.method,
      headers,
      body: corpo,
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
  // Respostas da API podem ter dados de um usuário: nenhum cache intermediário deve guardar.
  if (prefixo === "" && !saida.has("cache-control")) saida.set("cache-control", "no-store");
  for (const cookie of resposta.headers.getSetCookie()) saida.append("set-cookie", cookie);
  return new Response(resposta.status === 204 ? null : resposta.body, {
    status: resposta.status,
    headers: saida,
  });
}
