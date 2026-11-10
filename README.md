# RC Motos Digital

Sistema sob medida da RC Motos (loja de motos e carros no Piauí): estoque, vendas, lucro,
comissões e painel — com login individual, hierarquia de acesso e histórico de tudo o que é
feito — e o site público da loja, com a vitrine ligada ao estoque e o laudo de procedência
pela placa. Escopo completo, prazos e regras do contrato estão em [`CLAUDE.md`](CLAUDE.md).

## O que já está pronto

| Módulo | Situação |
|---|---|
| Login e senha individuais, perfis (dono, gerente, financeiro, vendedor) | pronto |
| Histórico de ações (audit log): quem, quando, o quê | pronto |
| Estoque de motos e carros: dados, fotos, custos, situação | pronto |
| Baixa de venda em dois toques, lucro = venda − compra − custos | pronto |
| Comissão pela regra de cada vendedor + relatório do mês | pronto |
| Painel: faturamento e lucro do mês, ticket médio moto/carro, estoque, parados | pronto |
| Aportes (gastos pessoais investidos na loja), visíveis só a quem o dono habilitar | pronto |
| Site público: vitrine sincronizada com o estoque, WhatsApp por veículo, SEO local | pronto |
| Procedência pela placa: tela de consulta, semáforo, laudo salvo no veículo | pronto, **sem provedor real ainda** (ver abaixo) |
| Assistente de IA | a fazer (próximo passo) |
| Asaas, cobrança, WhatsApp/Instagram com IA, linha do veículo, voz | a fazer |

O `index.html` na raiz é a prévia antiga do site mostrada ao cliente; o site de verdade é a
página inicial de `apps/web`.

## Site público

A página inicial (`/`) é o site da loja; o sistema da equipe fica em `/login`.

- **Vitrine**: mostra exatamente o que está "à venda" no sistema, com preço, fotos e botão de
  WhatsApp com mensagem pronta. Vendeu ou mudou de etapa, sai do site na hora.
- **Procedência**: o visitante digita a placa (ou toca em "Ver procedência" num anúncio) e vê o
  laudo guardado daquele veículo. Só vale para veículo à venda na loja — o site não faz consulta
  paga de placa de terceiros.
- **Proposta**: monta a mensagem de WhatsApp (veículo, forma de pagamento, entrada, parcelas,
  troca). O site não calcula juros nem promete valor.
- Telefone, cidade, endereço, horário e Instagram vêm das variáveis `LOJA_*`. O que não for
  preenchido não aparece — nada é inventado. **Preencha `LOJA_WHATSAPP` antes de publicar**: sem
  ele os botões abrem o WhatsApp sem destinatário.
- A placa completa não é publicada (só `ABC•••1`), para não facilitar clonagem. Quem digita a
  placa inteira, porque viu o veículo, consegue o laudo.

## Procedência pela placa

- Na área da equipe (**Procedência**), dono e gerente consultam qualquer placa. O laudo fica no
  histórico; se a placa é de um veículo do estoque, aparece na página dele. Placa consultada
  antes da compra é ligada ao veículo quando ele for cadastrado.
- **Ainda não há provedor real conectado.** Sem `PROCEDENCIA_PROVEDOR`, a tela avisa que a
  consulta está desligada. Com `demonstracao` (ou `DADOS_DEMO=true`) os resultados são
  **ilustrativos** e marcados como tal — placas terminadas em 3 dão "atenção" e em 7, "alerta".
  O modo demonstração é recusado com `AMBIENTE=producao`, e laudo ilustrativo nunca aparece no
  site fora da demonstração.
- Para ligar o provedor nacional (ex.: Infosimples, na conta da loja): escrever em
  `apps/api/app/procedencia.py` uma função que chama a API dele e devolve o mesmo formato de
  `dados` (`veiculo` + `itens` com `situacao` ok/atencao/alerta), registrá-la em `_PROVEDORES`
  e apontar `PROCEDENCIA_PROVEDOR` para ela. Telas, semáforo e histórico já funcionam em cima disso.

## Estrutura

```
apps/api   FastAPI + SQLAlchemy 2 + Alembic (Python 3.13, gerenciado com uv)
apps/web   Next.js (App Router) + TypeScript + Tailwind
docker-compose.yml   banco (PostgreSQL 16) + api + web
```

O navegador só fala com a web. Ela repassa `/api/*` e `/arquivos/*` para a API pela rede
interna, então o cookie de sessão fica na mesma origem e a API não precisa ser exposta.

## Rodar com Docker (jeito mais simples)

```bash
cp .env.example .env
```

Edite o `.env` (senha do banco, `DONO_NOME`, `DONO_EMAIL`, `DONO_SENHA`) e suba:

```bash
docker compose up --build -d
```

Crie o primeiro usuário (o dono), uma única vez:

```bash
docker compose exec api python -m app.seed
```

Abra <http://localhost:3000> e entre com o e-mail e a senha do dono. Os demais usuários são
criados pelo dono na tela **Equipe**. As migrações do banco são aplicadas sozinhas toda vez
que a API sobe.

Para experimentar com dados de exemplo (veículos, vendas e usuários **ilustrativos**), ponha
`DADOS_DEMO=true` no `.env` e rode:

```bash
docker compose exec api python -m app.seed --demo
```

Os usuários de exemplo (`gerente@exemplo.com`, `financeiro@exemplo.com`,
`vendedor1@exemplo.com`, `vendedor2@exemplo.com`) entram com a senha `rcmotos123`. O `--demo`
se recusa a rodar com `AMBIENTE=producao`.

## Rodar sem Docker (desenvolvimento)

Pré-requisitos: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22 e um PostgreSQL 16
local com um banco `rcmotos` (e `rcmotos_teste` para os testes).

API, em `apps/api`:

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
DONO_EMAIL=voce@exemplo.com DONO_SENHA=uma-senha-forte uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

Web, em `apps/web`:

```bash
npm install
API_URL=http://localhost:8000 npm run dev
```

A documentação interativa da API fica em <http://localhost:8000/docs> (desligada em produção).

## Testes e verificações

API (roda contra um Postgres de verdade, no banco `rcmotos_teste`, que é apagado a cada teste):

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Web:

```bash
npm run lint && npx tsc --noEmit && npm run build
```

O GitHub Actions (`.github/workflows/ci.yml`) roda tudo isso a cada pull request.

## Banco e migrações

Depois de mudar `apps/api/app/models.py`:

```bash
uv run alembic revision --autogenerate -m "descrição da mudança"
uv run alembic upgrade head
```

Revise o arquivo gerado em `apps/api/alembic/versions/` antes de commitar.

## Perfis e permissões

A matriz fica em um único lugar: `apps/api/app/permissoes.py`. A API valida cada rota e a
interface recebe a lista pronta em `/auth/eu` (não há regra duplicada no front).

| Perfil | Pode |
|---|---|
| dono | tudo: equipe, aportes, histórico geral, excluir veículo |
| gerente | estoque (editar, custos, fotos), vendas (registrar e cancelar), painel, comissões (ver) |
| financeiro | vendas e clientes (ver), comissões (ver e marcar como paga) |
| vendedor | ver estoque **sem** valor de compra/custos/lucro, registrar venda no próprio nome, ver as próprias vendas e comissões |

Consultar procedência: dono e gerente. Ver o laudo já salvo de um veículo: todos.

Aportes: só o dono e quem ele marcar em **Equipe → Pode ver os aportes**.

## Regras de negócio que valem saber

- **Lucro** = valor da venda − valor de compra − custos lançados no veículo.
- **Comissão**: cada usuário tem uma regra (% do lucro, % da venda ou valor fixo). A venda guarda
  um retrato da regra; mudar a regra depois não altera vendas antigas. Venda com prejuízo não
  gera comissão negativa.
- Custo lançado **depois** da venda refaz o lucro; a comissão acompanha enquanto estiver pendente
  e fica congelada depois de paga.
- Só veículo **à venda** (com preço de venda) pode receber baixa. Cancelar a venda devolve o
  veículo para "à venda" e cancela a comissão (se já estiver paga, é preciso desfazer o pagamento antes).
- Etapas do veículo já seguem a linha do contrato: compra → documentação → preparação → à venda →
  vendido → pós-venda → concluído.
- Fotos são redimensionadas (1920 px + miniatura de 480 px) e têm os metadados removidos (GPS).
- Cinco senhas erradas seguidas bloqueiam o login daquele e-mail por 15 minutos. Trocar a senha
  ou desativar o usuário derruba as sessões abertas na hora.

## Colocar em produção

Pela cláusula 6 do contrato, domínio, hospedagem, banco e contas ficam **no nome da RC Motos**,
com o desenvolvedor como administrador.

1. Servidor (ou serviço de containers) com Docker, na conta da loja.
2. `.env` com `AMBIENTE=producao`, senha forte do banco e `SEGREDO_JWT` gerado com
   `openssl rand -hex 32`. A API se recusa a subir em produção sem esse segredo.
3. **HTTPS obrigatório**: em produção o cookie de sessão só trafega por HTTPS. Coloque um proxy
   com certificado (Caddy, Nginx ou o balanceador da nuvem) na frente da porta da web.
4. `docker compose up --build -d` e `docker compose exec api python -m app.seed` para criar o dono.
5. **Backups**: os dados vivem em dois volumes — `dados_banco` (PostgreSQL) e `fotos`. Agende
   `pg_dump` diário e cópia do volume de fotos para fora do servidor.

Atualizar a versão: `git pull` seguido de `docker compose up --build -d` (as migrações rodam ao subir).

## Demonstração gratuita (Render)

Para mostrar o sistema a alguém antes de ter a hospedagem da loja, há uma versão de
demonstração que roda API e site **em um container só**, com dados ilustrativos:

1. Crie uma conta em render.com e conecte o GitHub.
2. **New > Blueprint**, escolha este repositório e o ramo. O Render lê o `render.yaml` e cria
   o serviço `rcmotos-demo` e o banco `rcmotos-demo-db`.
3. Quando terminar, o endereço aparece no topo do serviço (`https://….onrender.com`).
4. Para entrar na área da equipe: `dono@exemplo.com` com a senha em **Environment >
   DONO_SENHA**; os usuários de exemplo usam a senha em **SENHA_DEMO**. As duas são geradas
   pelo Render — a senha padrão da documentação não funciona lá.

Limites do plano gratuito (confira os atuais na página de preços do Render): o serviço dorme
depois de um tempo sem visitas e demora cerca de um minuto para acordar; o banco gratuito tem
prazo de validade; fotos enviadas somem a cada reinício. Serve para demonstrar, não para a
loja usar. Arquivos: `render.yaml`, `deploy/demonstracao/`.

Se o Blueprint não for aceito, crie na mão: um **PostgreSQL** gratuito e um **Web Service**
do tipo Docker com *Dockerfile Path* `./deploy/demonstracao/Dockerfile`, *Docker Context* `.`
e as variáveis listadas no `render.yaml` (`DATABASE_URL` = *Internal Database URL* do banco).

## Variáveis de ambiente

Docker (`.env` na raiz): veja [`.env.example`](.env.example).

| Variável (API) | Para quê | Padrão |
|---|---|---|
| `DATABASE_URL` | conexão com o PostgreSQL | banco local `rcmotos` |
| `AMBIENTE` | `desenvolvimento` ou `producao` | `desenvolvimento` |
| `SEGREDO_JWT` | assina a sessão; obrigatório em produção (≥ 32 caracteres) | segredo de desenvolvimento |
| `SESSAO_HORAS` | duração do login | 168 (7 dias) |
| `UPLOADS_DIR` | pasta das fotos | `uploads` |
| `DADOS_DEMO` | mostra o aviso "números ilustrativos" | `false` |
| `PROCEDENCIA_PROVEDOR` | provedor da consulta de placa (vazio = desligada) | vazio |
| `DIAS_PARADO_ALERTA` | dias na mesma etapa para aparecer em "parados" | 45 |
| `FUSO_HORARIO` | fuso da loja | `America/Fortaleza` |

| Variável (web) | Para quê | Padrão |
|---|---|---|
| `API_URL` | endereço interno da API | `http://localhost:8000` |
| `SITE_URL` | endereço público do site (SEO) | vazio |
| `LOJA_WHATSAPP`, `LOJA_CIDADE`, `LOJA_ENDERECO`, `LOJA_HORARIO`, `LOJA_INSTAGRAM` | dados da loja mostrados no site | vazios |
