#!/usr/bin/env bash
# Arrancar backend con HTTPS (certificado autofirmado)
# Ajustar HOST si se necesita acceso desde la red local
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
source .venv/bin/activate

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
CERT="$PROJECT_ROOT/certs/cert.pem"
KEY="$PROJECT_ROOT/certs/key.pem"

if [[ -f "$CERT" && -f "$KEY" ]]; then
  echo "Arrancando con HTTPS en https://$HOST:$PORT"
  uvicorn backend.main:app --host "$HOST" --port "$PORT" \
    --ssl-certfile "$CERT" --ssl-keyfile "$KEY"
else
  echo "Certs no encontrados, arrancando HTTP en http://$HOST:$PORT"
  uvicorn backend.main:app --host "$HOST" --port "$PORT"
fi
