#!/usr/bin/env bash
# Levanta todo el proyecto: InvenTree (Docker), backend FastAPI y frontend Vite.
# Uso: bash scripts/start.sh [--no-inventree]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/venv"
INVENTREE_COMPOSE="$ROOT/inventree-demo/docker-compose.yml"
LOG_DIR="/tmp/mercedes-mvp"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓${NC} $1"; }
info() { echo -e "${CYAN}  →${NC} $1"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $1"; }
fail() { echo -e "${RED}  ✗ ERROR:${NC} $1"; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}══ $1 ══${NC}"; }

NO_INVENTREE=false
[[ "$1" == "--no-inventree" ]] && NO_INVENTREE=true

mkdir -p "$LOG_DIR"

# ── Verificar setup previo ───────────────────────────────────
if [[ ! -f "$VENV/bin/python" ]]; then
  fail "Entorno Python no configurado. Ejecuta primero: bash scripts/setup.sh"
fi
if [[ ! -f "$ROOT/.env" ]]; then
  fail ".env no encontrado. Ejecuta primero: bash scripts/setup.sh"
fi
if [[ ! -f "$ROOT/stock_chatbot.db" ]]; then
  fail "Base de datos no inicializada. Ejecuta primero: bash scripts/setup.sh"
fi
if [[ ! -d "$FRONTEND/node_modules" ]]; then
  fail "node_modules no encontrado. Ejecuta primero: bash scripts/setup.sh"
fi

# ── 1. Ollama ────────────────────────────────────────────────
step "Ollama"
if ! command -v ollama &>/dev/null; then
  warn "Ollama no instalado — chatbot sin LLM"
elif ! curl -s http://localhost:11434 &>/dev/null; then
  info "Iniciando servidor Ollama en background..."
  ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
  sleep 2
  ok "Ollama iniciado (PID $!)"
else
  ok "Ollama ya está corriendo"
fi

# ── 2. InvenTree (Docker) ────────────────────────────────────
step "InvenTree (Docker)"

if $NO_INVENTREE; then
  warn "InvenTree omitido (--no-inventree)"
elif ! command -v docker &>/dev/null; then
  warn "Docker no instalado — InvenTree no disponible"
  warn "Instalar: sudo pacman -S docker docker-compose && sudo systemctl enable --now docker"
elif [[ ! -f "$INVENTREE_COMPOSE" ]]; then
  warn "docker-compose.yml no encontrado — ejecuta setup.sh primero"
else
  # Arrancar Docker daemon si no está corriendo
  if ! docker info &>/dev/null 2>&1; then
    info "Iniciando Docker daemon..."
    sudo systemctl start docker
    sleep 2
  fi

  # Ver si los contenedores ya están corriendo
  RUNNING=$(docker compose -f "$INVENTREE_COMPOSE" ps --status running --quiet 2>/dev/null | wc -l)
  if [[ "$RUNNING" -ge 3 ]]; then
    ok "InvenTree ya está corriendo"
  else
    info "Levantando base de datos de InvenTree..."
    docker compose -f "$INVENTREE_COMPOSE" up -d inventree-db

    # Esperar a que postgres esté listo
    for i in $(seq 1 10); do
      sleep 2
      if docker exec inventree_db pg_isready -U inventree &>/dev/null; then
        break
      fi
    done

    # Correr migraciones (idempotente — no hace nada si ya están aplicadas)
    info "Aplicando migraciones de base de datos..."
    docker compose -f "$INVENTREE_COMPOSE" run --rm inventree-server invoke migrate &>/dev/null \
      && ok "Migraciones aplicadas" \
      || warn "Migraciones con advertencias (puede ser normal)"

    info "Levantando servidor e InvenTree worker..."
    docker compose -f "$INVENTREE_COMPOSE" up -d inventree-server inventree-worker

    info "Esperando a que InvenTree esté listo..."
    for i in $(seq 1 18); do
      sleep 5
      if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 2>/dev/null | grep -qE "200|301|302"; then
        ok "InvenTree disponible en http://localhost:8080"
        break
      fi
      echo -ne "\r  → Esperando... ${i}/18"
      if [[ $i -eq 18 ]]; then
        warn "InvenTree tardó más de lo esperado. Revisa: docker logs inventree_server"
      fi
    done
    echo ""
  fi
fi

# ── 3. Backend FastAPI ───────────────────────────────────────
step "Backend FastAPI"

# Determinar protocolo
CERT="$ROOT/certs/cert.pem"
KEY="$ROOT/certs/key.pem"
SSL_FLAGS=()
if [[ -f "$CERT" && -f "$KEY" ]]; then
  BACKEND_URL="https://localhost:8000"
  SSL_FLAGS=("--ssl-certfile" "$CERT" "--ssl-keyfile" "$KEY")
else
  BACKEND_URL="http://localhost:8000"
fi

# Matar instancia previa si existe
if lsof -ti:8000 &>/dev/null; then
  warn "Puerto 8000 ocupado — cerrando proceso anterior..."
  kill "$(lsof -ti:8000)" 2>/dev/null || true
  sleep 1
fi

info "Iniciando backend en background..."
cd "$ROOT"
"$VENV/bin/uvicorn" backend.main:app \
  --host 0.0.0.0 --port 8000 \
  "${SSL_FLAGS[@]}" \
  > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# Esperar hasta que responda
for i in $(seq 1 10); do
  sleep 1
  if curl -sk "$BACKEND_URL/health" &>/dev/null; then
    ok "Backend listo en $BACKEND_URL  (PID $BACKEND_PID)"
    break
  fi
  if [[ $i -eq 10 ]]; then
    fail "Backend no respondió. Revisa: tail -50 $LOG_DIR/backend.log"
  fi
done

# ── 4. Frontend Vite ─────────────────────────────────────────
step "Frontend Vite"

if lsof -ti:3000 &>/dev/null; then
  warn "Puerto 3000 ocupado — cerrando proceso anterior..."
  kill "$(lsof -ti:3000)" 2>/dev/null || true
  sleep 1
fi

info "Iniciando frontend en background..."
cd "$FRONTEND"
npm run dev -- --host > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

for i in $(seq 1 10); do
  sleep 1
  if curl -sk https://localhost:3000 &>/dev/null || curl -s http://localhost:3000 &>/dev/null; then
    ok "Frontend listo en https://localhost:3000  (PID $FRONTEND_PID)"
    break
  fi
  if [[ $i -eq 10 ]]; then
    fail "Frontend no respondió. Revisa: tail -50 $LOG_DIR/frontend.log"
  fi
done

# ── Resumen ──────────────────────────────────────────────────
LOCAL_IP=$(ip route get 1 2>/dev/null | awk '{print $7; exit}' || echo "?")

echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Sistema levantado                        ${NC}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Local:${NC}"
echo -e "  ${CYAN}Chatbot:${NC}    http://localhost:3000"
echo -e "  ${CYAN}Backend:${NC}    $BACKEND_URL"
if ! $NO_INVENTREE && command -v docker &>/dev/null; then
echo -e "  ${CYAN}InvenTree:${NC}  http://localhost:8080"
fi
echo ""
echo -e "  ${BOLD}En red local (otros dispositivos):${NC}"
echo -e "  ${CYAN}Chatbot:${NC}    http://$LOCAL_IP:3000"
echo ""
echo -e "  ${BOLD}Logs:${NC}"
echo -e "  Backend:   tail -f $LOG_DIR/backend.log"
echo -e "  Frontend:  tail -f $LOG_DIR/frontend.log"
echo ""
echo -e "  ${BOLD}Para parar todo:${NC}  bash scripts/stop.sh"
echo ""

# Guardar PIDs para stop.sh
echo "BACKEND_PID=$BACKEND_PID" > "$LOG_DIR/pids"
echo "FRONTEND_PID=$FRONTEND_PID" >> "$LOG_DIR/pids"
