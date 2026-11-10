# apps/web — interface (Next.js)

Interface do Sistema RC Motos Digital. Como rodar, variáveis e deploy estão no
[README da raiz](../../README.md).

- `src/app/(sistema)/…` — telas da área logada (painel, estoque, vendas, comissões, aportes, equipe, histórico, conta).
- `src/app/login` — tela de entrada.
- `src/app/api/[...caminho]` e `src/app/arquivos/[...caminho]` — repassam para a API (variável `API_URL`), para o cookie de sessão ficar na mesma origem.
- `src/components/Sessao.tsx` — sessão, menu e permissões (a lista de permissões vem pronta da API em `/auth/eu`).
- `src/lib/formato.ts` — R$, datas DD/MM/AAAA, rótulos em português.
- `src/lib/tipos.ts` — espelha os schemas da API (`apps/api/app/schemas.py`).

```bash
npm install
API_URL=http://localhost:8000 npm run dev
```
