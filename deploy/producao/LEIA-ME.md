# Colocar a RC Motos Digital no ar

Passo a passo para publicar o sistema e o site em um servidor, com HTTPS e backup. Serve
para qualquer máquina Linux com Docker: uma VM gratuita na nuvem, um VPS pago ou um computador
da própria loja.

O que este conjunto faz sozinho:

- pede e renova o certificado HTTPS;
- deixa abertas só as portas 80 e 443 (banco e API ficam na rede interna);
- recusa subir sem senha do banco e sem segredo de sessão;
- faz backup do banco todo dia às 3h e das fotos todo domingo, em `./backups`;
- baixa as imagens já prontas do GitHub (o servidor não precisa compilar nada).

## 1. O servidor

Requisitos mínimos: 1 GB de memória, 20 GB de disco, Linux de 64 bits (x86), portas 80 e 443
liberadas no firewall da nuvem.

Instale o Docker:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Em máquina com só 1 GB de memória, crie 2 GB de memória de troca (swap) antes de continuar:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

```bash
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. O domínio

No painel do Registro.br (DNS do domínio), crie dois registros apontando para o IP do servidor:

| Tipo | Nome | Valor |
|---|---|---|
| A | `@` (ou o subdomínio escolhido) | IP do servidor |
| A | `www` | IP do servidor |

**Não mexa nos registros MX, SPF e DKIM**: são eles que fazem o e-mail do Google Workspace
funcionar. Se o domínio já tem um site no ar, usar um subdomínio (por exemplo
`sistema.rcmotos.com.br`) evita derrubá-lo; nesse caso crie só o registro A do subdomínio e
apague do `Caddyfile` o bloco do `www`.

O certificado só é emitido depois que o domínio já aponta para o servidor.

## 3. O projeto no servidor

```bash
git clone https://github.com/PedroGuarnier/rcmotospreview.git && cd rcmotospreview
```

```bash
cp deploy/producao/env.exemplo .env && chmod 600 .env
```

Edite o `.env` (`nano .env`) e preencha tudo. Para gerar o segredo de sessão:

```bash
openssl rand -hex 32
```

## 4. Subir

```bash
sudo docker compose -f docker-compose.producao.yml --env-file .env up -d
```

Crie o primeiro usuário (o dono), uma única vez. Ele usa `DONO_NOME`, `DONO_EMAIL` e
`DONO_SENHA` do `.env`:

```bash
sudo docker compose -f docker-compose.producao.yml --env-file .env exec api python -m app.seed
```

Abra `https://SEU-DOMINIO`. O sistema da equipe fica em `https://SEU-DOMINIO/login`. Os outros
usuários são criados pelo dono na tela **Equipe**.

Depois do primeiro login, apague `DONO_SENHA` do `.env`: ela só serve para criar o usuário.

Se as imagens não baixarem ("denied" ou "unauthorized"), os pacotes do GitHub estão privados.
Torne-os públicos em GitHub → seu perfil → Packages → cada pacote → Package settings → Change
visibility, ou entre no registro pelo servidor com um token de leitura
(`sudo docker login ghcr.io`).

## 5. Backup

Os backups ficam em `./backups` **no próprio servidor**. Isso protege de erro humano, não de
perda do servidor. Copie essa pasta para fora com regularidade — por exemplo, para o Google
Drive da loja.

Ver os backups e o registro do último:

```bash
ls -lh backups/ && sudo docker compose -f docker-compose.producao.yml logs --tail 5 backup
```

Restaurar o banco a partir de um backup (substitui os dados atuais; pare a API antes):

```bash
sudo docker compose -f docker-compose.producao.yml stop api web
```

```bash
gunzip -c backups/banco-AAAAMMDD-HHMM.sql.gz | sudo docker compose -f docker-compose.producao.yml exec -T db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB" && psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

```bash
sudo docker compose -f docker-compose.producao.yml start api web
```

Faça um teste de restauração antes de depender do backup.

## 6. Atualizar para uma versão nova

```bash
git pull && sudo docker compose -f docker-compose.producao.yml --env-file .env pull && sudo docker compose -f docker-compose.producao.yml --env-file .env up -d
```

As mudanças no banco são aplicadas sozinhas quando a API sobe.

## Onde hospedar

| Opção | Custo | Para quem |
|---|---|---|
| Google Cloud, VM `e2-micro` | Gratuita dentro dos limites | Começar sem pagar, na conta Google da loja |
| VPS pequeno (1–2 GB) | Em torno de R$ 25 a R$ 40 por mês | Uso tranquilo no dia a dia |
| Computador na loja + Cloudflare Tunnel | Gratuito | Quem aceita depender da energia e da internet da loja |

**Google Cloud `e2-micro`.** Uma VM por mês sem custo nas regiões dos EUA (`us-east1`,
`us-central1`, `us-west1`), com 30 GB de disco padrão. Tem 1 GB de memória (por isso o swap) e
só 1 GB de tráfego de saída por mês sem custo; acima disso cobra por uso, valores pequenos mas
não zero. Exige cartão no cadastro. Como a loja já tem Google Workspace, a conta fica no nome
dela. Confira os limites atuais em `cloud.google.com/free` antes de criar.

**Oracle Cloud "Always Free"** existe, mas não é recomendada aqui: a Oracle pode recolher VMs
que considera ociosas (uso baixo por 7 dias), e um sistema de loja pequena fica ocioso a maior
parte do tempo. A região de São Paulo também tem relatos de falta de capacidade.

**Computador na loja.** Roda este mesmo conjunto, sem o serviço `caddy`, com o Cloudflare
Tunnel fazendo a ponte para a internet. Exige mover o DNS do domínio para a Cloudflare, o que
obriga a recriar lá os registros de e-mail do Google Workspace — se algum faltar, o e-mail
para. Esse caminho ainda não está montado nem testado neste repositório.

**Render (plano gratuito)** serve só para demonstração: dorme sem visitas, o banco expira e as
fotos se perdem. Ver `render.yaml`.
