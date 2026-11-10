#!/bin/bash
# Sobe a demonstração: migrações, dados ilustrativos, API (só local) e web (porta pública).
set -euo pipefail

cd /app/api
alembic upgrade head
python -m app.seed --demo

uvicorn app.main:app --host 127.0.0.1 --port 8000 &

cd /app/web
API_URL=http://127.0.0.1:8000 HOSTNAME=0.0.0.0 node server.js &

# Se um dos dois cair, o container termina e a hospedagem reinicia tudo.
wait -n
exit 1
