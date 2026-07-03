#!/usr/bin/env bash
# Configuración inicial del proyecto en una laptop nueva.
# Ejecutar una sola vez: bash scripts/setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/venv"

# ── Colores ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓${NC} $1"; }
info() { echo -e "${CYAN}  →${NC} $1"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $1"; }
fail() { echo -e "${RED}  ✗ ERROR:${NC} $1"; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}══ $1 ══${NC}"; }

# ── 1. Python ────────────────────────────────────────────────
step "Python — entorno virtual"

if ! command -v python3 &>/dev/null; then
  fail "python3 no encontrado. Instálalo primero."
fi
PYVER=$(python3 --version)
ok "$PYVER detectado"

if [[ -d "$VENV" ]]; then
  ok "venv ya existe en backend/venv"
else
  info "Creando venv..."
  python3 -m venv "$VENV"
  ok "venv creado"
fi

info "Actualizando pip..."
"$VENV/bin/pip" install --upgrade pip --quiet

info "Instalando dependencias Python (puede tardar 1-2 minutos)..."
echo ""
"$VENV/bin/pip" install -r "$BACKEND/requirements.txt" --progress-bar on
echo ""
ok "Dependencias Python instaladas"

# ── 2. .env ──────────────────────────────────────────────────
step ".env — variables de entorno"

if [[ -f "$ROOT/.env" ]]; then
  ok ".env ya existe, no se sobreescribe"
else
  cp "$ROOT/.env.example" "$ROOT/.env"

  # Generar JWT secret automáticamente
  if command -v openssl &>/dev/null; then
    SECRET=$(openssl rand -hex 32)
    sed -i "s|cambia_esto_por_una_clave_larga_y_aleatoria_antes_de_produccion|$SECRET|" "$ROOT/.env"
    ok "JWT_SECRET_KEY generada automáticamente"
  else
    warn "openssl no encontrado — edita JWT_SECRET_KEY en .env manualmente"
  fi

  # Configurar Ollama local por defecto
  if ollama list &>/dev/null 2>&1; then
    sed -i "s|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://localhost:11434|" "$ROOT/.env"
    ok "OLLAMA_BASE_URL configurada a localhost:11434"
  fi

  ok ".env creado"
fi

# ── 3. Base de datos ─────────────────────────────────────────
step "Base de datos — SQLite + seed"

DB_FILE="$ROOT/stock_chatbot.db"
if [[ -f "$DB_FILE" ]]; then
  ok "Base de datos ya existe, se omite seed"
else
  info "Inicializando base de datos y cargando datos de prueba..."
  cd "$ROOT"
  "$VENV/bin/python" -m backend.seed
  ok "Base de datos creada con datos de prueba"
fi

# ── 4. Frontend ──────────────────────────────────────────────
step "Frontend — npm install"

if [[ -d "$FRONTEND/node_modules" ]]; then
  ok "node_modules ya existe"
else
  if ! command -v npm &>/dev/null; then
    fail "npm no encontrado. Instala Node.js primero."
  fi
  NPMVER=$(npm --version)
  ok "npm $NPMVER detectado"
  info "Instalando dependencias frontend..."
  cd "$FRONTEND"
  npm install
  ok "Dependencias frontend instaladas"
fi

# ── 5. Certificados SSL (opcional) ───────────────────────────
step "Certificados SSL (opcional)"

CERT_DIR="$ROOT/certs"
if [[ -f "$CERT_DIR/cert.pem" && -f "$CERT_DIR/key.pem" ]]; then
  ok "Certificados ya existen"
else
  if command -v openssl &>/dev/null; then
    mkdir -p "$CERT_DIR"
    openssl req -x509 -newkey rsa:4096 \
      -keyout "$CERT_DIR/key.pem" \
      -out "$CERT_DIR/cert.pem" \
      -days 365 -nodes \
      -subj "/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
      2>/dev/null
    ok "Certificados SSL generados (HTTPS habilitado)"
  else
    warn "openssl no disponible — el backend correrá en HTTP"
  fi
fi

# ── 6. Docker-compose para InvenTree (opcional) ──────────────
step "InvenTree — docker-compose"

INVENTREE_DIR="$ROOT/inventree-demo"
COMPOSE_FILE="$INVENTREE_DIR/docker-compose.yml"

if [[ -f "$COMPOSE_FILE" ]]; then
  ok "docker-compose.yml de InvenTree ya existe"
else
  mkdir -p "$INVENTREE_DIR"
  cat > "$COMPOSE_FILE" << 'COMPOSE'
services:
  inventree-db:
    image: postgres:14
    container_name: inventree_db
    environment:
      POSTGRES_DB: inventree
      POSTGRES_USER: inventree
      POSTGRES_PASSWORD: inventree_pass
    volumes:
      - inventree_db_data:/var/lib/postgresql/data
    restart: unless-stopped

  inventree-server:
    image: inventree/inventree:stable
    container_name: inventree_server
    depends_on:
      - inventree-db
    environment:
      INVENTREE_DB_ENGINE: postgresql
      INVENTREE_DB_NAME: inventree
      INVENTREE_DB_USER: inventree
      INVENTREE_DB_PASSWORD: inventree_pass
      INVENTREE_DB_HOST: inventree-db
      INVENTREE_DB_PORT: 5432
      INVENTREE_ADMIN_USER: admin
      INVENTREE_ADMIN_PASSWORD: admin1234
      INVENTREE_ADMIN_EMAIL: admin@demo.com
      INVENTREE_DEBUG: "False"
      INVENTREE_TIMEZONE: Europe/Madrid
      INVENTREE_LANGUAGE: es
    volumes:
      - inventree_data:/home/inventree/data
    ports:
      - "8080:8000"
    restart: unless-stopped

  inventree-worker:
    image: inventree/inventree:stable
    container_name: inventree_worker
    depends_on:
      - inventree-server
    environment:
      INVENTREE_DB_ENGINE: postgresql
      INVENTREE_DB_NAME: inventree
      INVENTREE_DB_USER: inventree
      INVENTREE_DB_PASSWORD: inventree_pass
      INVENTREE_DB_HOST: inventree-db
      INVENTREE_DB_PORT: 5432
    volumes:
      - inventree_data:/home/inventree/data
    command: invoke worker
    restart: unless-stopped

volumes:
  inventree_db_data:
  inventree_data:
COMPOSE
  ok "docker-compose.yml creado en inventree-demo/"

  if command -v docker &>/dev/null; then
    info "Docker detectado. Descargando imágenes de InvenTree en background..."
    docker compose -f "$COMPOSE_FILE" pull &
    ok "Descarga iniciada en background (docker compose pull)"
  else
    warn "Docker no instalado. InvenTree no estará disponible."
    warn "Para instalarlo en Arch/Garuda:"
    warn "  sudo pacman -S docker docker-compose"
    warn "  sudo systemctl enable --now docker"
    warn "  sudo usermod -aG docker \$USER"
  fi
fi

# ── 7. Ollama ────────────────────────────────────────────────
step "Ollama — modelo LLM"

if ! command -v ollama &>/dev/null; then
  warn "Ollama no instalado. Sin él el chatbot no funciona."
  warn "Instálalo desde: https://ollama.com"
elif ollama list 2>/dev/null | grep -q "qwen2.5:7b"; then
  ok "qwen2.5:7b ya está descargado"
else
  info "Descargando qwen2.5:7b (~4.7 GB)..."
  ollama pull qwen2.5:7b
  ok "qwen2.5:7b descargado"
fi

# ── Resumen ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Setup completado correctamente           ${NC}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo -e "  Para levantar el proyecto:"
echo -e "  ${BOLD}bash scripts/start.sh${NC}"
echo ""
echo -e "  URLs:"
echo -e "  ${CYAN}Frontend:${NC}   http://localhost:3000"
echo -e "  ${CYAN}Backend:${NC}    http://localhost:8000"
echo -e "  ${CYAN}InvenTree:${NC}  http://localhost:8080  (si Docker activo)"
echo ""
