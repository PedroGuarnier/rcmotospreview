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
| Imposto estimado sobre a margem de cada venda, com alíquota configurada pelo dono | pronto |
| Aportes (gastos pessoais investidos na loja), visíveis só a quem o dono habilitar | pronto |
| Site público: vitrine sincronizada com o estoque, página por veículo, WhatsApp por veículo, SEO local, sitemap, prévia do link, contagem de procura | pronto; falta domínio e hospedagem |
| Procedência pela placa: tela de consulta, semáforo, laudo salvo no veículo | pronto; provedor Consultar Placa integrado, falta a conta da loja com créditos (ver abaixo) |
| Assistente por mensagem: cadastra e altera veículo, registra venda e anexa fotos, sempre com confirmação | pronto |
| Assistente de IA: responde perguntas sobre vendas, estoque, comissões e painel com os dados do sistema | pronto; Groq (gratuito) ou Claude, falta a conta da loja |
| Asaas, cobrança, WhatsApp/Instagram com IA, linha do veículo, voz | a fazer |

O `index.html` na raiz é a prévia antiga do site mostrada ao cliente; o site de verdade é a
página inicial de `apps/web`.

## Site público

A página inicial (`/`) é o site da loja; o sistema da equipe fica em `/login`.

O site é a vitrine da loja: os produtos vêm primeiro, a procedência é um apoio.

- **Primeira dobra**: os veículos que chegaram por último já aparecem ao lado do título, com
  atalhos para motos e carros.
- **Vitrine**: mostra exatamente o que está "à venda" no sistema, em grade, com preço, fotos,
  filtro por tipo, busca e ordenação. Vendeu ou mudou de etapa, sai do site na hora. Veículo
  sem foto aparece com um cartão só com o nome do modelo.
- **Página do veículo** (`/veiculo/ID-marca-modelo-ano`): galeria, ficha, botão de WhatsApp com
  mensagem pronta, laudo de procedência e outros veículos da vitrine. Cada página tem título,
  descrição e dados estruturados próprios para o Google (os dados estruturados não saem com
  dados de demonstração).
- **Procedência**: o visitante digita a placa (ou abre o laudo na página do veículo) e vê o
  laudo guardado daquele veículo. Só vale para veículo à venda na loja — o site não faz consulta
  paga de placa de terceiros.
- **Proposta**: monta a mensagem de WhatsApp (veículo, forma de pagamento, entrada, parcelas,
  troca). O site não calcula juros nem promete valor.
- Telefone, cidade, endereço, horário e Instagram vêm das variáveis `LOJA_*`. O que não for
  preenchido não aparece — nada é inventado. **Preencha `LOJA_WHATSAPP` antes de publicar**: sem
  ele os botões abrem o WhatsApp sem destinatário.
- A placa completa não é publicada (só `ABC•••1`), para não facilitar clonagem. Quem digita a
  placa inteira, porque viu o veículo, consegue o laudo.
- **Laudo**: o site não promete laudo para todo veículo. Anúncio com laudo mostra o laudo; sem
  laudo, mostra uma linha discreta. Na área da equipe, veículo à venda sem laudo ganha um aviso
  e a etiqueta "Sem laudo" no Estoque (não bloqueia, porque a consulta é paga).
- **Google**: `/sitemap.xml` (início, cada veículo à venda e `/privacidade`) e `/robots.txt`
  (fora a área da equipe). Só valem com `SITE_URL` preenchido; com dados de demonstração o site
  pede para não ser indexado.
- **Prévia do link** (WhatsApp, Instagram, Facebook): a página do veículo usa a foto de capa; sem
  foto, uma imagem gerada com nome, ano, km e preço (`/og/veiculo/ID`). O início usa `/og/inicio`.
- **Rodapé**: `LOJA_CNPJ` (validado; inválido não aparece) e `LOJA_RAZAO_SOCIAL`, mais o link da
  página `/privacidade`, que descreve o que o site realmente guarda.
- **Contagem de procura**: visitas à página do veículo e cliques nos botões de WhatsApp (do
  cartão, da página e da proposta), por veículo e por dia. Sem cookie, sem IP e sem serviço de
  fora (`POST /publico/eventos`, com limite de taxa; robôs não contam). A equipe vê os números
  na página do veículo e em "Mais procurados no site" no painel.

## Assistente

Na área da equipe, **Assistente** (logo abaixo de Estoque no menu) faz por mensagem o que as
telas fazem, e responde perguntas sobre o negócio. Nada é gravado antes da confirmação ("sim" ou
o botão), e cada ação exige a mesma permissão da tela correspondente.

**Por mensagem (motor de regras, sem IA, sem custo):**
- **Cadastrar veículo** (`estoque.editar`): `chegou uma Honda CG 160 Fan 2022 vermelha, placa
  ABC1D23, 18.500 km, comprei ontem por 11.500 e vou vender por 14.900`. Obrigatórios: marca e
  modelo, tipo e valor de compra; o que faltar, ele pergunta. Data da compra entende "hoje",
  "ontem", "dia 20" e "15/11" (futura não vale). Marca fora do catálogo vira a pergunta "é moto
  ou carro?". Um veículo por mensagem; placa ou chassi repetido é avisado.
- **Alterar veículo** (`estoque.editar`): `a CG placa ABC1D23 agora custa 13.900`, `põe a XRE 300
  à venda`. Mostra antes → depois e grava pelo mesmo caminho do formulário.
- **Registrar venda** (`vendas.registrar`): `vendi a CG placa ABC1D23 pro João Silva por 14.900
  à vista, vendedor Carlos`. Acha o veículo entre os que estão à venda (mais de um candidato vira
  lista para escolher), mostra lucro, imposto e comissão previstos a quem vê custos e grava pelo
  mesmo serviço da tela de vendas. O vendedor registra só em nome próprio.
- **Fotos**: depois de cadastrar ou alterar, "Adicionar fotos" envia as fotos ali mesmo (no
  celular, abre a câmera).
- Número sem pista ou valor em escala duvidosa vira pergunta, nunca chute.

**Perguntas (IA):** "quantas motos vendemos este mês?", "qual o lucro de outubro?", "o que está
parado há mais de 30 dias?", "tem alguma CG 160 no estoque?", "e em setembro?".
- O modelo só responde com o que cinco consultas ao banco devolvem (vendas, estoque, comissões,
  painel, aportes), e cada uma devolve só o que o perfil de quem pergunta vê na tela: o vendedor
  vê as próprias vendas e comissões, sem lucro; aportes só para quem o dono habilitou.
- Quem não cadastra nem vende (financeiro) usa o assistente só para perguntas.
- Provedor trocável por `IA_PROVEDOR`: `groq` (padrão; modelo `openai/gpt-oss-120b`, há camada
  gratuita) ou `anthropic` (Claude Haiku 5.5). Sem a chave do provedor, o assistente avisa que as
  perguntas não estão ligadas e o resto funciona.
- Camada gratuita do Groq: cerca de 2 perguntas por minuto e 60 por dia (cada pergunta usa uns
  3 mil tokens). Passando disso, o assistente pede para esperar um minuto. No plano pago, cada
  pergunta custa uma fração de centavo.
- O log da aplicação registra provedor, modelo, tokens e tempo de cada pergunta, sem o texto.

**Onde está o código:** `apps/api/app/assistente.py` (interpretação e cadastro; `interpretar()`
é função pura), `assistente_acoes.py`, `assistente_venda.py`, `assistente_edicao.py`,
`assistente_busca.py`, `assistente_datas.py` (venda, alteração, datas), `app/ia/` (IA:
`atendimento.py` decide quem responde, `agente.py` faz o laço, `ferramentas.py` as consultas,
`provedores.py` Groq e Anthropic). Sem estado no servidor: o rascunho e as últimas perguntas vão e
voltam no `estado`, validados a cada mensagem.

## Procedência pela placa

- Na área da equipe (**Procedência**), dono e gerente consultam qualquer placa. O laudo fica no
  histórico; se a placa é de um veículo do estoque, aparece na página dele. Placa consultada
  antes da compra é ligada ao veículo quando ele for cadastrado.
- Sem `PROCEDENCIA_PROVEDOR`, a tela avisa que a consulta está desligada. Com `demonstracao`
  (ou `DADOS_DEMO=true`) os resultados são **ilustrativos** e marcados como tal — placas
  terminadas em 3 dão "atenção" e em 7, "alerta". O modo demonstração é recusado com
  `AMBIENTE=producao`, e laudo ilustrativo nunca aparece no site fora da demonstração.
- **Provedor real: Consultar Placa** (`PROCEDENCIA_PROVEDOR=consultarplaca`, código em
  `apps/api/app/consultarplaca.py`, documentação em <https://docs.consultarplaca.com.br>).
  - Criar a conta **no nome da loja** em consultarplaca.com.br, gerar a chave em Minha Conta →
    API e preencher `CONSULTARPLACA_EMAIL` e `CONSULTARPLACA_API_KEY`. Sem os dois, a consulta
    fica desligada.
  - É pré-pago: comprar créditos no site deles. Cada placa faz quatro consultas avulsas
    (básica, roubo e furto, leilão, Renajud), cerca de R$ 30 no preço de tabela de 11/2026.
    A básica vai primeiro; se a placa não existe, as outras três não são feitas.
  - A placa `AAA0000` devolve dados fictícios sem gastar crédito; o laudo dela sai marcado
    como ilustrativo. Serve para conferir a chave depois de configurar.
  - Laudo completo da mesma placa feito nas últimas `PROCEDENCIA_REUSO_HORAS` horas (24) é
    reaberto em vez de pagar outra consulta. Item que o provedor não conseguiu verificar
    fica em "atenção" (o laudo não dá verde) e a próxima consulta refaz tudo.
  - A consulta de leilão pode levar alguns minutos quando há oferta registrada (o provedor
    pede espera de até 300 s); o proxy na frente do sistema precisa tolerar esse tempo.
  - Regras do semáforo: Renajud ativo, roubo ou furto sem devolução e leilão classe C ou D
    dão "alerta"; roubo ou furto já devolvido, leilão classe A ou B, sinistro, remarketing e
    divergência de chassi ou ano com o cadastro da loja dão "atenção".
- Para trocar de provedor: escrever uma função que devolve o mesmo formato de `dados`
  (`veiculo` + `itens` com `situacao` ok/atencao/alerta) e registrá-la em `_PROVEDORES`
  (`apps/api/app/procedencia.py`). Telas, semáforo e histórico funcionam em cima disso.

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
| dono | tudo: equipe, aportes, histórico geral, excluir veículo, alíquota do imposto |
| gerente | estoque (editar, custos, fotos), vendas (registrar e cancelar), painel, comissões (ver) |
| financeiro | vendas e clientes (ver), comissões (ver e marcar como paga) |
| vendedor | ver estoque **sem** valor de compra/custos/lucro, registrar venda no próprio nome, ver as próprias vendas e comissões |

Consultar procedência: dono e gerente. Ver o laudo já salvo de um veículo: todos.

Aportes: só o dono e quem ele marcar em **Equipe → Pode ver os aportes**.

## Regras de negócio que valem saber

- **Lucro** = valor da venda − valor de compra − custos lançados no veículo.
- **Imposto estimado** = alíquota × margem, onde margem = valor da venda − valor de compra (os
  custos não entram; margem negativa não gera imposto). A alíquota é uma só, informada pelo dono
  em **Configurações** com o número do contador; começa em 0, que desliga o cálculo. Cada venda
  guarda a alíquota do dia da baixa: mudar a alíquota não altera vendas já registradas. O imposto
  não entra no lucro (base da comissão); aparece à parte, com o **lucro líquido** = lucro − imposto,
  nas vendas, no veículo e no painel. É estimativa: o valor a pagar é o apurado pelo contador.
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
| `PROCEDENCIA_PROVEDOR` | provedor da consulta de placa: vazio (desligada), `demonstracao` ou `consultarplaca` | vazio |
| `CONSULTARPLACA_EMAIL` / `CONSULTARPLACA_API_KEY` | conta da loja na Consultar Placa | vazio |
| `PROCEDENCIA_REUSO_HORAS` | horas em que um laudo pago da mesma placa é reaproveitado (0 = nunca) | 24 |
| `IA_PROVEDOR` | IA das perguntas do assistente: `groq` ou `anthropic` | `groq` |
| `GROQ_API_KEY` / `ANTHROPIC_API_KEY` | chave do provedor escolhido; vazia = perguntas desligadas | vazio |
| `IA_MODELO` | modelo; vazio = `openai/gpt-oss-120b` (Groq) ou `claude-haiku-5-5` (Anthropic) | vazio |
| `DIAS_PARADO_ALERTA` | dias na mesma etapa para aparecer em "parados" | 45 |
| `FUSO_HORARIO` | fuso da loja | `America/Fortaleza` |

| Variável (web) | Para quê | Padrão |
|---|---|---|
| `API_URL` | endereço interno da API | `http://localhost:8000` |
| `SITE_URL` | endereço público do site (SEO) | vazio |
| `LOJA_WHATSAPP`, `LOJA_CIDADE`, `LOJA_ENDERECO`, `LOJA_HORARIO`, `LOJA_INSTAGRAM` | dados da loja mostrados no site | vazios |
| `LOJA_CNPJ`, `LOJA_RAZAO_SOCIAL` | rodapé do site (CNPJ inválido não aparece) | vazios |
