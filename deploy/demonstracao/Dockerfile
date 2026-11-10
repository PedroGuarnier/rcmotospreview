# Demonstração em UM container (API + web), para hospedagem gratuita.
#
# Não é a imagem de produção: lá, API e web sobem separadas (docker-compose.yml).
# Aqui as duas rodam juntas para caber em um único serviço gratuito e acordar de uma vez só.
# Contexto de build: a raiz do repositório.

FROM node:22-slim AS web
WORKDIR /web
ENV NEXT_TELEMETRY_DISABLED=1
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    UPLOADS_DIR=/dados/uploads \
    DADOS_DEMO=true \
    PORT=3000

# Só o executável do Node, para rodar o servidor do Next
COPY --from=web /usr/local/bin/node /usr/local/bin/node

RUN pip install --no-cache-dir uv
WORKDIR /app/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api ./

WORKDIR /app/web
COPY --from=web /web/.next/standalone ./
COPY --from=web /web/.next/static ./.next/static
COPY --from=web /web/public ./public

COPY deploy/demonstracao/iniciar.sh /app/iniciar.sh
RUN useradd --system --uid 1001 app \
    && mkdir -p /dados/uploads \
    && chown -R app /dados \
    && chmod +x /app/iniciar.sh
USER app

EXPOSE 3000
CMD ["/app/iniciar.sh"]
