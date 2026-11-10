FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv
WORKDIR /app

# Dependências primeiro: a camada só é refeita quando o lock muda.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN useradd --system --uid 1001 app \
    && mkdir -p /dados/uploads \
    && chown -R app /dados
USER app
ENV UPLOADS_DIR=/dados/uploads

EXPOSE 8000
# Aplica as migrações pendentes e sobe a API.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
