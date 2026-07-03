#!/usr/bin/env bash
# PC-B — Nodo cliente
# Levanta Ollama + backend local + frontend.
# NO levanta InvenTree (vive en el servidor central).
#
# Uso: bash scripts/start_client.sh <IP-DEL-SERVIDOR>
# Ejemplo: bash scripts/start_client.sh 192.168.1.10

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

fail() { echo -e "${RED}  ✗ ERROR:${NC} $1"; exit 1; }
ok()   { echo -e "${GREEN}  ✓${NC} $1"; }
info() { echo -e "${CYAN}  →${NC} $1"; }

SERVER_IP="${1:-}"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Mercedes MVP — NODO CLIENTE (PC-B)     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Pedir IP del servidor si no se pasó como argumento
if [[ -z "$SERVER_IP" ]]; then
  read -rp "  IP del servidor central (PC-A): " SERVER_IP
fi

[[ -z "$SERVER_IP" ]] && fail "Necesitas la IP del servidor. Ejemplo: bash start_client.sh 192.168.1.10"

CENTRAL_URL="http://$SERVER_IP:8000"

# Verificar conectividad básica con el servidor
info "Verificando conexión con el servidor ($CENTRAL_URL)..."
if curl -s --connect-timeout 3 "$CENTRAL_URL/health" | grep -q '"status"'; then
  SERVER_NODE=$(curl -s "$CENTRAL_URL/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('node_id','?'))")
  ok "Servidor encontrado: $SERVER_NODE en $CENTRAL_URL"
else
  echo ""
  echo -e "${YELLOW}  ⚠ No se pudo conectar con $CENTRAL_URL${NC}"
  echo "    Comprueba que el servidor está corriendo y que el firewall"
  echo "    permite el puerto 8000 (sudo ufw allow 8000)."
  echo ""
  read -rp "  ¿Continuar de todos modos en modo local? [s/N] " RESP
  [[ "${RESP,,}" != "s" ]] && exit 1
fi

# Escribir variables de entorno para este nodo
LOCAL_IP=$(ip route get 1 2>/dev/null | awk '{print $7; exit}' || hostname -I | awk '{print $1}')

info "Configurando .env para modo cliente..."
ENV_FILE="$ROOT/.env"

# Actualizar o añadir NODE_ROLE y CENTRAL_SERVER_URL en .env
python3 - <<PYEOF
import re, pathlib

env_path = pathlib.Path("$ENV_FILE")
text = env_path.read_text()

def set_var(text, key, value):
    pattern = rf'^{key}=.*$'
    replacement = f'{key}={value}'
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, replacement, text, flags=re.MULTILINE)
    return text + f'\n{key}={value}'

text = set_var(text, 'NODE_ROLE', 'client')
text = set_var(text, 'NODE_ID', 'cliente-$LOCAL_IP')
text = set_var(text, 'CENTRAL_SERVER_URL', '$CENTRAL_URL')
# ALLOWED_ORIGINS en cliente apunta a su propio frontend
text = set_var(text, 'ALLOWED_ORIGINS', 'https://localhost:3000,https://$LOCAL_IP:3000')

env_path.write_text(text)
print("  .env actualizado")
PYEOF

ok ".env configurado (NODE_ROLE=client, CENTRAL_SERVER_URL=$CENTRAL_URL)"
echo ""
echo "  Iniciando stack del cliente (sin InvenTree)..."
echo ""

exec bash "$SCRIPT_DIR/start.sh" --no-inventree
