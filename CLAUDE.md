# Sistema RC Motos Digital

Plataforma sob medida para a RC Motos, loja de motos e carros no Piauí. Desenvolvedor: Pedro Guarnier. Contrato assinado em 04/11/2026; pago em 10/11/2026.

## Prazos (contrato, contados da assinatura)
- Primeira versão em uso: até **25/11/2026**
- Entrega final: até **03/01/2027**
- Depois da entrega: 3 meses de manutenção sem custo; compromisso mínimo do desenvolvedor de 2 anos.

## Stack
- `apps/web`: Next.js (App Router) + TypeScript
- `apps/api`: FastAPI (Python) + SQLAlchemy 2 + Alembic
- PostgreSQL; `docker-compose.yml` para rodar local
- IA: Claude Haiku para a maior parte das conversas, Sonnet quando precisar raciocinar mais
- Pagamentos: Asaas (API + webhooks). WhatsApp: API oficial da Meta. Voz: Retell ou Vapi + Twilio/Zenvia.

## Regras de propriedade (contrato, cláusula 6)
- O software é cedido à RC Motos na entrega: código-fonte, banco, documentação e acessos.
- Domínio, hospedagem, banco e contas administrativas ficam **no nome da RC Motos**, com o Pedro como administrador. Montar a infra já assim (contas de cloud, IA e telefonia da loja).
- Documentar o suficiente para outro profissional continuar (README, `.env.example`, como subir e fazer deploy).

## Identidade visual
- Navy `#0A0940`, azul `#1610C4`, amarelo `#ECD02F`; fundo claro `#F2F3FA`
- Logo circular amarela com "RC MOTOS — DEUS É FIEL"; barras de velocidade do "R" como motivo
- Tipografia forte (Inter Display / Anton para títulos)

## Perfis e permissões
| Perfil | Vê / faz |
|---|---|
| dono | tudo, inclusive aportes pessoais e gestão de usuários |
| gerente | estoque, vendas, painel, cobrança; sem aportes, salvo se o dono habilitar |
| financeiro | parcelas, cobrança, renegociação, recebimentos, comissões |
| vendedor | estoque, registrar venda, suas próprias comissões |
- Histórico de ações (audit log) de toda criação/alteração: quem, quando, o quê.
- "Gastos pessoais investidos na loja" (aportes): módulo visível só para quem o dono habilitar.

## Escopo (cláusula 1 do contrato)

### 1. Gestão e vendas — primeira versão (até 25/11)
- Estoque de motos e carros: fotos, placa, chassi, RENAVAM, ano, cor, km, valor de compra, custos (manutenção, documentação, débitos pagos), preço de venda, situação.
- Baixa de venda em dois toques: comprador, valor, forma (à vista, financiado banco, parcelado na loja), vendedor; calcula lucro = venda − compra − custos; gera comissão pela regra do vendedor.
- Assistente de IA (chat): responde perguntas sobre vendas, estoque e financeiro ("quantas motos vendemos em outubro?") usando tools que consultam o banco; registra venda por mensagem com confirmação.
- Verificação de procedência pela placa (consulta básica: roubo/furto, leilão, Renajud, dados cadastrais), semáforo verde/amarelo/vermelho, laudo salvo no histórico do veículo. Provedor nacional (ex.: Infosimples).
- Login e senha individuais + hierarquia de acesso.

### 2. Atendimento e site
- IA no WhatsApp e Instagram: preço, disponibilidade, financiamento, horário; transfere para humano quando o cliente quer fechar.
- Site com catálogo sincronizado com o estoque, botão de WhatsApp por veículo (mensagem pré-preenchida), SEO local ("loja de motos em [cidade]").

### 3. Financeiro e cobrança
- Venda parcelada cria o carnê no Asaas automaticamente; webhooks (`PAYMENT_CREATED`, `PAYMENT_OVERDUE`, `PAYMENT_RECEIVED`) fazem a baixa. O Asaas é a fonte da verdade sobre o que foi pago.
- Avisos ao dono do que vence no dia; lembrete ao cliente com Pix.
- Régua configurável (não hardcoded): D-3 lembrete, D0 vence hoje, D+2 educada, D+5 firme, D+7 ligação se não respondeu, D+15 alerta interno. Pausa ao pagar, com promessa ativa, com humano assumindo ou contestação. Disparos idempotentes.
- Agente de cobrança no WhatsApp com tools: `consultar_parcelas`, `gerar_pix_ou_segunda_via`, `registrar_promessa`, `simular_acordo`, `propor_ao_responsavel`, `registrar_acordo`, `transferir_humano`, `registrar_optout`. Confirmar identidade antes de falar da dívida; nunca falar com terceiros; respeitar CDC art. 42 e horário comercial.
- Ligação automática (voz natural) só para quem ignorou o WhatsApp: dias úteis 9h–18h, 1 tentativa/dia, máx. 3; manda o Pix no WhatsApp durante a ligação; salva transcrição e resumo. Confirmar com o fornecedor se precisa do prefixo 0303.
- Renegociação: política configurada pelo dono (prazo máx., divisão do atraso, desconto só em juros/multa, entrada mínima, 1 acordo/contrato a cada 6 meses). Fora da alçada → card para o dono aprovar/contrapropor/recusar. Aceite do cliente registrado ("ACEITO"); acordo quebrado retoma a régua.
- Painel de inadimplência: quem deve, quanto, há quantos dias, promessas.
- Tabela `eventos_cobranca` registrando todo evento desde o início.

### 4. Linha do veículo
- Etapas: compra → documentação → preparação → à venda → vendido → pós-venda → concluído. Quadro com veículos por etapa e parados há muito tempo.
- Débitos na compra (IPVA, licenciamento): digitados pela equipe no início; prazo limite e alertas (15, 7 dias e no dia); entram como custo; veículo com débito aberto não vai "à venda".
- Transferência pelo comprador: contagem de 30 dias a partir da venda, lembretes no WhatsApp (dias 10, 20, 25), alerta ao dono no vencimento e geração da notificação extrajudicial preenchida (modelo fornecido pelo advogado da loja).
- Gravame: alienação registrada na **B3**, baixa na **Tecnobank** — o sistema acompanha status e número do contrato e avisa na quitação da última parcela ("fazer a baixa na Tecnobank"). O registro oficial continua nessas plataformas; integração direta só se houver API acessível.
- RENAVE: status de entrada/saída do estoque por veículo e pendências.

### 5. Painel financeiro
- A receber até o mês que vem, ticket médio (por mês, moto/carro), faturamento e lucro em tempo real, comissões por vendedor (relatório do mês), recebimentos do Asaas conciliados com a venda.

### 6. Equipe
- E-mails profissionais no domínio da loja.

## Ordem sugerida
1. Base: monorepo, docker-compose, banco, auth/perfis, audit log.
2. Estoque + vendas + lucro + comissões + painel (primeira versão).
3. Assistente de IA no sistema + procedência pela placa.
4. Disparar cedo (dependem de terceiros): verificação Meta Business, templates de WhatsApp, conta Asaas/sandbox, número de telefonia, domínio.
5. Asaas + parcelas + régua WhatsApp → agente de cobrança → renegociação.
6. Site + atendimento IA WhatsApp/Instagram.
7. Linha do veículo, transferência, gravame, RENAVE.
8. Voz: piloto com ~10 clientes, ouvir gravações, ajustar, liberar.

## Convenções
- Interface e mensagens em português do Brasil; valores em R$, datas DD/MM/AAAA.
- Desenvolver o Asaas contra o sandbox com datas simuladas para rodar a régua inteira em minutos.
- Números de exemplo em telas/demos devem ser marcados como ilustrativos.

## Estado do código (atualizado em 10/11/2026)
- Feito: itens 1 e 2 da ordem sugerida (base, auth/perfis, audit log, estoque, vendas, lucro, comissões, painel, aportes); o site público (item 6, sem a IA de atendimento); e a procedência pela placa (telas, semáforo, laudo no veículo) — **ainda sem provedor real**, só o de demonstração. Próximo: assistente de IA; adaptador do provedor de placa quando a conta da loja existir.
- Site público = página inicial de `apps/web` (`src/components/site/`, conceito visual "O Farol"); sistema da equipe em `/login`. `index.html` na raiz é só a prévia antiga.
- Dados da loja no site vêm de `LOJA_*` (nunca escrever telefone/endereço no código). O site não inventa número, depoimento nem taxa de juros.
- Rotas `/publico/*` da API não têm login: só pode sair delas o que é público (sem custos, chassi, RENAVAM, comprador, placa completa em listagem).
- A placa interativa é um componente só (`apps/web/src/components/placa/`), usado no site e na área da equipe.
- Permissões: matriz única em `apps/api/app/permissoes.py`; a web recebe a lista em `/auth/eu`.
- Audit log é automático (`apps/api/app/audit.py`, listener do SQLAlchemy): toda mudança feita pelo ORM é registrada. Não usar SQL direto para alterar dados de negócio.
- Schemas da API (`apps/api/app/schemas.py`) e tipos da web (`apps/web/src/lib/tipos.ts`) andam juntos: mudou um, mude o outro.
- O Next instalado tem mudanças em relação a versões antigas: ver `apps/web/AGENTS.md` antes de mexer.

## Comandos
- API (em `apps/api`): `uv run pytest` · `uv run ruff check . && uv run ruff format .` · `uv run alembic revision --autogenerate -m "..."` · `uv run uvicorn app.main:app --reload`
- Web (em `apps/web`): `npm run lint` · `npx tsc --noEmit` · `npm run build` · `API_URL=http://localhost:8000 npm run dev`
- Tudo junto: `docker compose up --build` e `docker compose exec api python -m app.seed [--demo]`
- Testes da API precisam do Postgres local com o banco `rcmotos_teste` (usuário/senha `rcmotos`).
