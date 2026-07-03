#!/usr/bin/env bash
# PC-A — Servidor central
# Levanta el stack completo: Ollama, InvenTree, backend y frontend.
# Uso: bash scripts/start_server.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# Forzar rol de servidor en el entorno de este proceso
export NODE_ROLE=server
export NODE_ID="${NODE_ID:-server-principal}"

# Detectar IP local para mostrarla al final
LOCAL_IP=$(ip route get 1 2>/dev/null | awk '{print $7; exit}' || hostname -I | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Mercedes MVP — SERVIDOR CENTRAL (PC-A) ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  IP de esta máquina en la red: $LOCAL_IP"
echo "  Los clientes (PC-B) apuntarán a: http://$LOCAL_IP:8000"
echo ""
echo "  Recuerda añadir la IP del cliente en ALLOWED_ORIGINS del .env:"
echo "  ALLOWED_ORIGINS=https://localhost:3000,https://<IP-PC-B>:3000"
echo ""
read -rp "  ¿Continuar? [Enter para sí / Ctrl+C para cancelar] "

exec bash "$SCRIPT_DIR/start.sh"
