import { repassar } from "@/lib/proxy";

export async function GET(req: Request, { params }: { params: Promise<{ caminho: string[] }> }) {
  return repassar(req, (await params).caminho, "/arquivos");
}
