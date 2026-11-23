# RC Motos Digital — contexto do projeto

Documento para quem chega agora (pessoa ou IA) entender o projeto inteiro sem ler o histórico:
o que é, o que foi contratado, o que já existe, o que falta, o que depende de quem e por que
certas decisões foram tomadas.

**Atualizado em 23/11/2026** (depois da revisão de pré-produção). Os outros documentos têm papéis diferentes:
[`CLAUDE.md`](CLAUDE.md) é o escopo do contrato e as convenções; [`README.md`](README.md) é o
manual técnico (rodar, testar, publicar).

---

## 1. Em poucas linhas

A **RC Motos** é uma loja de motos e carros seminovos no Piauí. O projeto é uma plataforma sob
medida com duas faces:

- um **sistema de gestão** para a equipe (estoque, vendas, lucro, comissões, prazos, painel);
- o **site público** da loja, com a vitrine ligada ao estoque e o laudo de procedência por placa.

Desenvolvedor: Pedro Guarnier. Contrato assinado em 04/11/2026 e pago em 10/11/2026.

**Onde estamos:** a parte de gestão, o site e os prazos (débitos, transferência, avisos) estão
construídos, testados e revisados por dois revisores independentes. **Nada está publicado
ainda**, mas o conjunto de produção está pronto (seção 8). A loja já tem o domínio
`rcmotos.com.br` no Registro.br, Google Workspace e conta na Check Brasil. Faltam o assistente de IA, toda a parte de cobrança (Asaas, WhatsApp, voz) e um
provedor real para a consulta de placa.

---

## 2. Prazos do contrato

| Marco | Data | Situação |
|---|---|---|
| Primeira versão em uso | **25/11/2026** | Em risco — ver abaixo |
| Entrega final | **03/01/2027** | — |
| Manutenção sem custo | 3 meses após a entrega | — |
| Compromisso mínimo do desenvolvedor | 2 anos | — |

**O que a primeira versão pede e como está cada item:**

| Item da primeira versão | Situação |
|---|---|
| Estoque de motos e carros | Pronto |
| Baixa de venda em dois toques, lucro e comissão | Pronto |
| Login individual e hierarquia de acesso | Pronto |
| Verificação de procedência pela placa | Telas prontas; **sem provedor real** (seção 7) |
| Assistente de IA (chat que consulta o banco) | **Não iniciado** |
| Estar "em uso" pela loja | **Não publicado** — o conjunto de produção está pronto; falta criar o servidor e apontar o domínio |

Os três últimos dependem de coisas fora do código: chave da Anthropic, definição do provedor de
placa e a infraestrutura da loja.

---

## 3. Regras do contrato que moldam o projeto

- **Propriedade (cláusula 6):** o software é cedido à RC Motos na entrega — código, banco,
  documentação e acessos. Domínio, hospedagem, banco e contas ficam **no nome da loja**, com o
  desenvolvedor como administrador.
- **Continuidade:** documentar o suficiente para outro profissional assumir.
- **Idioma e formatos:** tudo em português do Brasil, valores em R$, datas DD/MM/AAAA.
- **Números de exemplo** em telas e demonstrações são sempre marcados como ilustrativos.

---

## 4. Escopo completo e situação

O contrato tem seis blocos (detalhe em `CLAUDE.md`).

### 4.1 Gestão e vendas

| Funcionalidade | Situação |
|---|---|
| Estoque: fotos, placa, chassi, RENAVAM, ano, cor, km, compra, custos, preço, situação | Pronto |
| Baixa de venda (à vista, financiado no banco, parcelado na loja) | Pronto |
| Lucro = venda − compra − custos | Pronto |
| Comissão pela regra de cada vendedor + relatório do mês | Pronto |
| Login, perfis e histórico de ações | Pronto |
| Procedência pela placa com semáforo e laudo no veículo | Pronto, só com dados ilustrativos |
| Assistente de IA | A fazer |

### 4.2 Atendimento e site

| Funcionalidade | Situação |
|---|---|
| Site com catálogo sincronizado com o estoque | Pronto |
| Botão de WhatsApp por veículo com mensagem pronta | Pronto (falta o número da loja) |
| SEO local | Pronto (falta cidade e domínio) |
| IA no WhatsApp e no Instagram | A fazer — depende da Meta |

### 4.3 Financeiro e cobrança

Nada iniciado. Inclui carnê e baixa automática pelo Asaas, régua de cobrança configurável, agente
de cobrança no WhatsApp, ligação automática, renegociação e painel de inadimplência. Depende de
conta no Asaas, API da Meta e fornecedor de voz.

### 4.4 Linha do veículo

| Funcionalidade | Situação |
|---|---|
| Etapas compra → documentação → preparação → à venda → vendido → pós-venda → concluído | Pronto |
| Quadro por etapa, com os parados em destaque | Pronto |
| Débitos (IPVA, licenciamento, multas) com prazo e avisos | Pronto |
| Transferência pelo comprador: 30 dias, aviso, cobrança | Pronto, com envio manual |
| Lembrete automático por WhatsApp (dias 10, 20, 25) | A fazer — depende da Meta |
| Notificação extrajudicial preenchida | A fazer — depende do modelo do advogado |
| Gravame (B3 / Tecnobank) e RENAVE | A fazer |

### 4.5 Painel financeiro

| Funcionalidade | Situação |
|---|---|
| Faturamento e lucro em tempo real | Pronto |
| Ticket médio por mês, moto e carro | Pronto |
| Comissões por vendedor | Pronto |
| A receber até o mês que vem | A fazer — depende das parcelas (Asaas) |
| Recebimentos do Asaas conciliados | A fazer — depende do Asaas |

### 4.6 Equipe

E-mails profissionais no domínio da loja: a fazer — depende do domínio.

---

## 5. O produto hoje

### 5.1 Site público (página inicial)

Direção visual chamada **"O Farol"**: o disco amarelo da logo vira sol e farol sobre uma estrada
à noite; títulos em Anton em escala de outdoor; navy, azul e amarelo da marca.

- **Primeira dobra:** "Moto boa tem passado limpo." e a contagem real de veículos na loja.
- **Vitrine:** o que está "à venda" no sistema, com preço, fotos e WhatsApp por veículo.
- **Puxe a placa:** uma placa Mercosul desenhada em código, em formato de moto e de carro. O
  visitante digita, a placa recusa caractere no lugar errado, um feixe "lê" a chapa e o laudo
  abre com semáforo e a linha do tempo do veículo.
- **Como pagar:** montador de proposta que gera a mensagem de WhatsApp.
- **A loja:** contatos vindos de configuração.

### 5.2 Sistema da equipe (`/login`)

| Tela | Para quê |
|---|---|
| Painel | Faturamento, lucro, ticket médio, estoque, parados, resumo dos avisos |
| Estoque | Lista com busca e filtros; página do veículo com fotos, custos, débitos, laudo, histórico |
| Linha do veículo | Quadro por etapa, com botão de avançar |
| Avisos | Prazos que pedem ação (débitos e transferências) |
| Procedência | Consulta de placa, com o laudo salvo |
| Vendas | Lista do mês, detalhe, cancelamento, transferência |
| Comissões | Relatório do mês, marcar como paga |
| Aportes | Gastos pessoais do dono investidos na loja |
| Equipe | Usuários, perfis, regra de comissão |
| Histórico | Quem fez o quê, e quando |

### 5.3 Perfis

| Perfil | Pode |
|---|---|
| Dono | Tudo, inclusive equipe, aportes e histórico geral |
| Gerente | Estoque, custos, débitos, vendas, painel, procedência |
| Financeiro | Ver vendas, pagar comissões, marcar transferências |
| Vendedor | Ver estoque **sem custos nem lucro**, vender no próprio nome, ver as próprias comissões |

A matriz fica em um arquivo só (`apps/api/app/permissoes.py`); a interface recebe a lista pronta.

---

## 6. Decisões tomadas e por quê

Estas escolhas não estão no contrato; foram tomadas no caminho. Vale confirmar com a loja as
marcadas com ⚠.

**Negócio**

- ⚠ **Só veículo "à venda" recebe baixa.** Garante que nada é vendido antes de ter preço e de
  estar sem débito. Se a loja vende moto ainda em preparação, a regra pode ser afrouxada.
- ⚠ **Vendedor não vê valor de compra, custos nem lucro**, e não cadastra veículo.
- ⚠ **Financeiro não vê lucro nem o painel.**
- **Custo lançado depois da venda refaz o lucro.** A comissão acompanha enquanto está pendente
  e congela depois de paga.
- **A venda guarda um retrato da regra de comissão**: mudar a regra não altera vendas antigas.
- ⚠ **Débito lançado em veículo que já está à venda devolve o veículo para "documentação"** e o
  tira do site, para a regra "com débito não vai à venda" valer nos dois sentidos.
- **O lucro previsto já desconta os débitos em aberto.**
- **O prazo do débito é a data que a equipe digitar**, não uma consulta automática.

**Site**

- **Nenhum número inventado.** A prévia antiga trazia "+800 veículos", "100%" e "24h"; saíram.
  O site mostra só a contagem real do estoque.
- **O site não calcula juros nem promete parcela**: só monta a mensagem para a loja responder.
- ⚠ **A placa completa não aparece nos anúncios** (só `ABC•••1`), para não facilitar clonagem.
  Quem digita a placa inteira vê o laudo.
- **O site só mostra laudo de veículo da loja.** Consulta aberta de qualquer placa custaria por
  requisição e seria abusada.
- **Dados da loja vêm de configuração** (`LOJA_*`). O que não for preenchido não aparece.

**Técnica**

- **O histórico de ações é automático**: toda mudança feita pelo sistema é registrada na mesma
  transação, sem depender de cada tela lembrar.
- **Avisos não têm tabela**: são calculados na hora a partir das datas, então somem sozinhos
  quando o problema é resolvido.
- **O navegador só fala com a web**, que repassa as chamadas para a API. A API não fica exposta.
- **Laudo de demonstração nunca vale em produção** e nunca aparece no site fora do modo demo.
- **Senha:** cinco erros do mesmo endereço de rede bloqueiam aquele endereço por 15 minutos
  (errar a senha de outra pessoa não tranca a conta dela); trocar a senha derruba as outras
  sessões.
- **Sem segredo de sessão configurado, cada inicialização sorteia um**: nunca existe um segredo
  conhecido, já que o código é público.
- **Consulta pública de placa:** 10 por minuto e 60 por hora por endereço, para ninguém
  descobrir a placa completa de um anúncio por tentativa.

---

## 7. O que descobrimos sobre fornecedores

### Infosimples (consulta veicular) — lido em 16/11/2026

O contrato cita a Infosimples como exemplo de provedor. A leitura do catálogo público mostrou
que **ela não entrega a procedência pela placa como o contrato descreve**:

- Não existe consulta só pela placa para o Piauí: as do DETRAN/PI pedem placa **e** RENAVAM.
- Roubo e furto, leilão e Renajud só aparecem juntos na consulta do SENATRAN, que exige login
  gov.br e certificado digital e, pela descrição, só devolve veículo na posse de quem faz o
  login. Não serve para checar uma moto antes de comprar.
- Não há base própria de leilão.

Em compensação, serve bem para **débitos do Piauí** (licenciamento, multas, IPVA), o que
automatizaria o que hoje a equipe digita.

| Consulta | Precisa de | Preço por chamada |
|---|---|---|
| DETRAN / PI / Veículo | Placa + RENAVAM | R$ 0,24 |
| SEFAZ / PI / IPVA | RENAVAM ou chassi | R$ 0,20 |
| DETRAN / PI / Multas | Placa + RENAVAM | R$ 0,20 |
| SENATRAN / Meus Veículos – Completa | gov.br + certificado | R$ 0,36 |

Cobrança pré-paga, com **consumo mínimo de R$ 100,00 por mês**. No volume da loja, o custo real
é esse mínimo. Há R$ 100,00 de crédito de teste por 30 dias ao criar a conta.

Ressalva: isso vem do catálogo público (nomes, descrições e campos). A documentação técnica
exige login e não foi lida; um teste real pode mostrar mais.

**Em aberto:** achar um fornecedor de histórico pela placa (roubo e furto, leilão, Renajud),
que costuma vir de bases privadas e custar mais por consulta.

### Negativação de clientes

A Infosimples não informa se alguém está negativado (não tem Serasa, SPC, Boa Vista nem score).
Isso é serviço de birô de crédito e **não está no contrato**: se a loja quiser para aprovar o
parcelado, é item novo.

### Hospedagem gratuita

Para demonstração, o Render ainda oferece plano gratuito que comporta o projeto. Existe uma
versão "tudo em um container" pronta para ele (`render.yaml`, `deploy/demonstracao/`), testada
localmente mas **não validada no Render**. Serve para mostrar, não para a loja usar.

---

## 8. Contas e integrações externas

Todas ficam no nome da RC Motos. A loja **já tem**: o domínio `rcmotos.com.br` (Registro.br),
Google Workspace (e-mails no domínio, o item 6 do contrato) e uma conta na Check Brasil
(consulta veicular — falta confirmar se o plano dá acesso por API).

**Hospedagem:** o caminho está montado e testado em `docker-compose.producao.yml`, com passo a
passo em `deploy/producao/LEIA-ME.md`. A opção gratuita recomendada é uma VM `e2-micro` do
Google Cloud, na conta Google da loja; a alternativa tranquila é um VPS de R$ 25 a R$ 40 por
mês. A Oracle gratuita não é recomendada (recolhe VMs ociosas) e o Render gratuito serve só
para demonstração.

| Integração | Para quê | Quando |
|---|---|---|
| Servidor | Publicar o sistema e o site | **Agora** — sem isso nada entra em uso |
| Anthropic (Claude) | Assistente de IA | **Agora** — primeira versão |
| Provedor de consulta veicular | Procedência real | **Agora** — primeira versão |
| Asaas | Carnê, Pix, baixa automática | Etapa de cobrança |
| WhatsApp Business (Meta) | Lembretes, cobrança, atendimento | Abrir já: a verificação demora |
| Instagram (Meta) | Atendimento no direct | Etapa de atendimento |
| Voz (Retell ou Vapi + Twilio ou Zenvia) | Ligação de cobrança | Última etapa |

Sem integração (só acompanhamento dentro do sistema): B3, Tecnobank e RENAVE.

---

## 9. Pendências com a loja

**Dados que faltam**

- WhatsApp, cidade, endereço, horário e Instagram da loja (o site está sem eles).
- Fotos reais dos veículos.
- Regra de comissão de cada vendedor.
- Modelo da notificação extrajudicial, com o advogado.
- Política de renegociação (prazo máximo, entrada mínima, desconto).

**Perguntas sem resposta**

1. As motos compradas passam para o CNPJ da loja ou ficam no nome do dono anterior até a venda?
2. A loja tem certificado digital (e-CNPJ)?
3. O prazo do débito deve ser o vencimento oficial ou um prazo interno?
4. Quem deve receber os avisos: só o dono ou o gerente também?
5. A loja já tem conta no Asaas?
6. Quantos veículos compram por mês, mais ou menos?

As duas primeiras definem se a consulta do SENATRAN serve para o estoque.

---

## 10. Como o projeto é feito

```
apps/api   API em Python (FastAPI, SQLAlchemy 2, Alembic), banco PostgreSQL 16
apps/web   Interface e site em Next.js 16 (App Router), TypeScript, Tailwind 4
docker-compose.yml          banco + API + web
deploy/demonstracao/        versão em um container só, para demonstração
index.html                  prévia antiga do site (não faz parte do sistema)
```

**Banco (11 tabelas):** `usuarios`, `veiculos`, `custos_veiculo`, `debitos_veiculo`,
`fotos_veiculo`, `clientes`, `vendas`, `comissoes`, `aportes`, `laudos_procedencia`, `audit_log`.

**Onde olhar**

| Assunto | Arquivo |
|---|---|
| Quem pode o quê | `apps/api/app/permissoes.py` |
| Lucro, comissão, prazos | `apps/api/app/servicos.py` |
| Histórico automático | `apps/api/app/audit.py` |
| Consulta de placa (provedor trocável) | `apps/api/app/procedencia.py` |
| O que o site pode ver | `apps/api/app/rotas/publico.py` |
| Avisos | `apps/api/app/rotas/avisos.py` |
| Site | `apps/web/src/components/site/` |
| Placa interativa | `apps/web/src/components/placa/` |
| Menu, sessão e permissões na tela | `apps/web/src/components/Sessao.tsx` |

**Rodar no computador:** `docker compose up --build -d`, depois
`docker compose exec api python -m app.seed --demo`. Passo a passo no `README.md`.

---

## 11. Estado do repositório

Repositório: `PedroGuarnier/rcmotospreview`. **É público** — ver alertas na seção 13.

| Ramo | O que tem |
|---|---|
| `main` | Gestão, site e procedência (até 10/11) |
| `claude/new-session-4t7f0y` | Tudo do `main` + demonstração em um container + débitos, transferência, avisos e quadro (16/11) + este documento |
| `codex/teste-docker-compose` | Tudo do `main` + teste do Docker Compose na verificação automática (PR nº 1, de 23/11) |

O ramo `claude/…` e o PR nº 1 **ainda não foram juntados ao `main`**. Eles mexem em arquivos
diferentes, então devem se juntar sem conflito.

**Verificação**

- 62 testes da API passando (rodados em 23/11), contra PostgreSQL de verdade.
- Web sem erros de lint, tipos e build.
- Verificação automática no GitHub passou no `main` (10/11) e no PR nº 1 (23/11). Esta última
  construiu as imagens e subiu o Docker Compose completo, confirmando que os Dockerfiles do
  repositório funcionam como estão.
- Roteiros no navegador (computador e celular) cobriram os fluxos principais. Eles não estão no
  repositório; só os testes da API são versionados.

**Revisão de pré-produção (23/11):** dois revisores independentes leram a API e a web. Acharam
24 defeitos, quase todos confirmados em teste. Os que eram defeito real foram corrigidos, cada
um com um teste: entre eles, "14.900" num campo de valor era gravado como R$ 14,90; cancelar
uma venda devolvia o veículo "à venda" mesmo com débito aberto; um dono rebaixado continuava
vendo os aportes; e o `docker-compose.yml` aceitava subir com um segredo de sessão conhecido.

**Ficaram como estão, por decisão:** o vendedor consegue ver a lista de clientes ao registrar
uma venda; "Sair" apaga o cookie mas não invalida o acesso em outros aparelhos (trocar a senha
invalida); e um vendedor com comissão sobre o lucro consegue deduzir o lucro da própria venda.

**Não verificado:** leitor de tela, Safari real, o `render.yaml` no Render, o certificado HTTPS
com um domínio de verdade (foi testado com `localhost`), e o sistema com dados e fotos reais.

---

## 12. Próximos passos, em ordem

1. **Assistente de IA** — ferramentas que consultam o banco e a tela de chat. O código não
   depende de ninguém; a conversa real precisa da chave da Anthropic.
2. **Publicar** — criar o servidor, apontar o domínio e seguir `deploy/producao/LEIA-ME.md`.
   Antes, levar o ramo `claude/…` para o `main`: é do `main` que as imagens de produção saem.
3. **Procedência real** — definir o fornecedor de histórico pela placa e escrever o adaptador.
   As telas, o semáforo e o laudo já funcionam em cima dele.
4. **Débitos automáticos do Piauí** pela Infosimples, se a loja topar o mínimo mensal.
5. **Parcelas e régua de cobrança** — dá para construir e testar com datas simuladas antes de
   Asaas e WhatsApp entrarem.
6. **Abrir já, em paralelo:** verificação do Meta Business e conta do Asaas.
7. Atendimento com IA, gravame, RENAVE e, por último, voz.

---

## 13. Alertas

- **O repositório é público.** O código do sistema e os detalhes do contrato em `CLAUDE.md`
  (datas, prazos, cláusulas) estão visíveis para qualquer pessoa. Chaves e senhas nunca entram
  no código; ficam em variáveis de ambiente.
- **A senha dos usuários de exemplo (`rcmotos123`) está escrita no `README.md`.** Nunca rodar o
  modo demonstração com essa senha em nada exposto à internet. A versão para o Render já gera
  senhas próprias.
- **Prazo de 25/11:** o que falta depende de chave, provedor e hospedagem, não só de código.
- **O site está sem os dados da loja.** Sem `LOJA_WHATSAPP`, os botões abrem o WhatsApp sem
  destinatário.
- **A consulta de placa mostra dados ilustrativos.** Ninguém deve tomar decisão de compra com
  base nela até existir um provedor real.
