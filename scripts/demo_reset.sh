#!/usr/bin/env bash
# Reinicia el sistema a estado limpio para demostración.
# Uso: ./scripts/demo_reset.sh

set -e
cd "$(dirname "$0")/.."

echo "=== RESET DEMO ==="

# Activar venv
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "ERROR: venv no encontrado en .venv/"
    exit 1
fi

# Matar servidores si están corriendo
pkill -f "uvicorn backend.main" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# Borrar y recrear la base de datos
echo "→ Recreando base de datos..."
rm -f stock_chatbot.db
python -m backend.seed
echo "✓ DB recreada con datos de demostración"

# Actualizar system prompts mejorados
echo "→ Actualizando system prompts..."
python scripts/update_prompts.py
echo "✓ Prompts actualizados"

echo ""
echo "=== SISTEMA LISTO PARA DEMO ==="
echo ""
echo "Usuarios disponibles:"
echo "  admin       / Admin123!   (acceso completo)"
echo "  gestor1     / Gestor123!  (todos los almacenes)"
echo "  supervisor_a/ Super123!   (Almacén Norte)"
echo "  supervisor_b/ Super123!   (Almacén Sur)"
echo "  operador_a1 / Oper123!    (Almacén Norte)"
echo "  operador_b1 / Oper123!    (Almacén Sur)"
echo ""
echo "Para iniciar servidores:"
echo "  Terminal 1: ./scripts/start_backend.sh"
echo "  Terminal 2: ./scripts/start_frontend.sh"
