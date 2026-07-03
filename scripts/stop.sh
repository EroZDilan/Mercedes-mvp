#!/usr/bin/env bash
# Para todos los procesos del proyecto

LOG_DIR="/tmp/mercedes-mvp"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
INVENTREE_COMPOSE="$ROOT/inventree-demo/docker-compose.yml"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $1"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $1"; }

echo -e "${CYAN}Parando proyecto...${NC}"

# Backend y frontend por PID guardado
if [[ -f "$LOG_DIR/pids" ]]; then
  source "$LOG_DIR/pids"
  [[ -n "$BACKEND_PID" ]]  && kill "$BACKEND_PID"  2>/dev/null && ok "Backend parado"
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null && ok "Frontend parado"
  rm -f "$LOG_DIR/pids"
fi

# Forzar limpieza de puertos por si acaso
lsof -ti:8000 2>/dev/null | xargs kill 2>/dev/null && ok "Puerto 8000 liberado" || true
lsof -ti:3000 2>/dev/null | xargs kill 2>/dev/null && ok "Puerto 3000 liberado" || true

# Docker (InvenTree) — preguntar antes de parar
if command -v docker &>/dev/null && [[ -f "$INVENTREE_COMPOSE" ]]; then
  RUNNING=$(docker compose -f "$INVENTREE_COMPOSE" ps --status running --quiet 2>/dev/null | wc -l)
  if [[ "$RUNNING" -gt 0 ]]; then
    read -rp "  ¿Parar InvenTree (Docker)? [s/N] " resp
    if [[ "$resp" =~ ^[sS]$ ]]; then
      docker compose -f "$INVENTREE_COMPOSE" down
      ok "InvenTree parado"
    else
      warn "InvenTree sigue corriendo"
    fi
  fi
fi

echo ""
echo -e "${GREEN}  Listo.${NC}"
