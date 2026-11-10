import { repassar } from "@/lib/proxy";

type Contexto = { params: Promise<{ caminho: string[] }> };

async function tratar(req: Request, { params }: Contexto) {
  return repassar(req, (await params).caminho);
}

export { tratar as GET, tratar as POST, tratar as PATCH, tratar as PUT, tratar as DELETE };
