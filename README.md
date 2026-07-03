# Stock Chatbot MVP — Sistema de Gestión de Inventario con IA

Sistema de chatbot para gestión de stock en almacenes de taller automotriz. Permite consultar y ejecutar acciones sobre el inventario en lenguaje natural, con flujo de confirmación obligatorio antes de aplicar cambios. Diseñado para operar **100% offline** en red local.

---

## Concepción y objetivo

El objetivo es demostrar que un sistema puede:

- **Unificar stock** de múltiples almacenes sincronizados desde laptops en red local
- **Responder en lenguaje natural**, filtrando información según el rol del usuario
- **Ejecutar acciones** sobre el stock con confirmación explícita antes de aplicar
- **Simular la integración con Spiga+** (DMS automotriz de Lidera Soluciones) usando InvenTree como stand-in offline
- **Transcribir audio** para enviar mensajes por voz
- Funcionar **sin internet** para inferencia LLM, audio y datos

El sistema fue concebido como MVP de ventas para demostrar a concesionarios Mercedes que el chatbot puede integrarse con su ERP (Spiga+) sin depender de la nube.

---

## Arquitectura

```
[Laptop Almacén A :8001]     [Laptop Almacén B :8002]
   FastAPI agente               FastAPI agente
   stock_local.json             stock_local.json
          |                            |
          └──────────┬─────────────────┘
                     | PULL cada 30 min (o manual por admin)
             [Servidor Central]
                     |
         ┌───────────┴────────────────────────┐
     FastAPI :8000                         SQLite
         |                        (stock + usuarios
         |                         + historial CRM
     Ollama :11434                 + logs + alertas
     qwen2.5:7b                    + action_log)
         |
     faster-whisper (audio local)
         |
  [InvenTree :8080] ← Docker, simulador Spiga+
         |
  [React Frontend :3000] → Cualquier dispositivo en red WiFi
```

### Flujo de sincronización

```
Laptop Almacén → [PULL cada 30 min] → Servidor actualiza SQLite
Chatbot ejecuta acción → SQLite + action_log + InvenTree (sync tiempo real)
```

### Flujo de acción del chatbot

```
Usuario escribe/dicta
  → LLM interpreta intención
  → Backend valida permisos del rol
  → Se genera resumen con datos reales (no alucinados)
  → Usuario confirma (token UUID de un solo uso, TTL 60s)
  → Backend ejecuta → SQLite + InvenTree + notificaciones al superior
```

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| LLM | Ollama + qwen2.5:7b (local) / OpenRouter fallback |
| Transcripción audio | faster-whisper (modelo small, local) |
| Backend | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy 2.x |
| Auth | JWT + bcrypt, refresh tokens, sesiones revocables |
| Orquestación LLM | LangChain (tool calling, streaming SSE) |
| Scheduler | APScheduler (sync cada 30 min) |
| Base de datos | SQLite (MVP) → PostgreSQL (producción) |
| Simulador DMS | InvenTree 1.3.5 (Docker) |
| Frontend | React 19 + Tailwind CSS 4 + Vite |
| Streaming | SSE (Server-Sent Events) |

---

## Roles y permisos

```
ADMIN (nivel 1)
  └── GESTOR (nivel 2)
        └── SUPERVISOR (nivel 3)
              └── OPERADOR (nivel 4)
```

| Acción | Admin | Gestor | Supervisor | Operador |
|--------|:-----:|:------:|:----------:|:--------:|
| Consultar stock propio almacén | ✅ | ✅ | ✅ | ✅ |
| Consultar stock todos los almacenes | ✅ | ✅ | ❌ | ❌ |
| Transferir / mover stock | ✅ | ✅ | ✅ | ✅ |
| Cambiar estado de producto | ✅ | ✅ | ✅ | ✅ |
| Crear producto nuevo | ✅ | ✅ | ✅ | ❌ |
| Editar producto existente | ✅ | ✅ | ✅ | ❌ |
| Eliminar producto | ✅ | ✅ | ❌ | ❌ |
| Gestionar usuarios | ✅ | ❌ | ❌ | ❌ |
| Resetear contraseñas | ✅ | ❌ | ❌ | ❌ |
| Ver CRM de subordinados | ✅ | ✅ | ✅* | ❌ |
| Trigger sync manual | ✅ | ❌ | ❌ | ❌ |

*Supervisor solo ve operadores de su propio almacén.

---

## Usuarios de demo

| Usuario | Contraseña | Rol | Almacén |
|---------|-----------|-----|---------|
| `admin` | `Admin123!` | Admin | Todos |
| `gestor1` | `Gestor123!` | Gestor | Todos |
| `supervisor_a` | `Super123!` | Supervisor | Almacén Norte (ALM-A) |
| `supervisor_b` | `Super123!` | Supervisor | Almacén Sur (ALM-B) |
| `operador_a1` | `Oper123!` | Operador | Almacén Norte (ALM-A) |
| `operador_b1` | `Oper123!` | Operador | Almacén Sur (ALM-B) |

---

## Cómo levantar el sistema

### Requisitos previos
- Python 3.11+
- Node.js 20+
- Docker Desktop (para InvenTree)
- Ollama con modelo `qwen2.5:7b`

### 1. Backend

```powershell
cd Mercedes-mvp
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt

# Inicializar DB con datos de demo
python -m backend.seed

# Arrancar
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
# Abrir: https://localhost:3000
```

### 3. InvenTree (simulador Spiga+)

```powershell
cd C:\inventree-demo
docker compose up -d
# Primera vez: docker compose run --rm inventree-server invoke update

# Cargar datos de demo:
python scripts/populate_inventree.py

# Sincronizar usuarios del chatbot con InvenTree:
python scripts/sync_users_to_inventree.py
```

### 4. Ollama

```powershell
ollama serve
ollama pull qwen2.5:7b   # primera vez
```

Accesos:
- **MVP Frontend**: `https://localhost:3000`
- **Backend API docs**: `http://localhost:8000/docs`
- **InvenTree**: `http://localhost:8080` (`admin` / `admin1234`)

---

## Variables de entorno (.env)

```env
# JWT
JWT_SECRET_KEY=cambia_esto_por_clave_larga_aleatoria_128_chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_HOURS=8

# LLM
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OPENROUTER_API_KEY=           # fallback cloud opcional

# InvenTree (simulador Spiga+)
INVENTREE_URL=http://localhost:8080/api/
INVENTREE_TOKEN=<tu-token-de-inventree>

# Almacenes
WAREHOUSE_A_ID=ALM-A
WAREHOUSE_A_NAME=Almacén Norte
WAREHOUSE_B_ID=ALM-B
WAREHOUSE_B_NAME=Almacén Sur

# Seguridad
MAX_LOGIN_ATTEMPTS=5
LOGIN_RATE_LIMIT=10/minute    # usar 200/minute en desarrollo
ALLOWED_ORIGIN=http://localhost:3000

# Whisper
WHISPER_MODEL=small
WHISPER_LANGUAGE=es

# DB
DATABASE_URL=sqlite:///./stock_chatbot.db
```

---

## Tests

```powershell
cd Mercedes-mvp
.venv\Scripts\activate
python -m pytest tests/ -v
```

| Suite | Tests |
|-------|-------|
| test_auth.py | 18 |
| test_chatbot.py | 12 |
| test_crm.py | 16 |
| test_e2e.py | 35 |
| test_inventree_sync.py | 14 |
| test_notifications.py | 14 |
| test_security.py | 21 |
| test_stock.py | 28 |
| test_sync.py | 22 |
| test_users.py | 12 |
| **Total** | **192** |

---

## Progreso de desarrollo

### FASE 0 — Setup base ✅
Estructura de proyecto, modelos SQLAlchemy (12 tablas), seed de datos, endpoint `/health`.

### FASE 1 — Autenticación ✅ (27/27 tests)
JWT access + refresh, bcrypt, bloqueo tras 5 intentos, audit log, force logout, rate limiting.

### FASE 2 — Agentes de almacén + Sync ✅ (18/18 tests)
FastAPI agente ligero por laptop, sync pull cada 30 min, upsert de stock, stock_history, notificaciones de almacén offline y stock bajo.

### FASE 3 — Chatbot (LangChain + LLM) ✅ (17/17 tests)
Contexto de stock filtrado por rol, historial conversacional, SSE streaming, notificación al superior si pregunta no resuelta.

### FASE 4 — Roles y permisos en todos los endpoints ✅ (46/46 tests)
Stock CRUD con aislamiento por almacén, gestión de usuarios (admin only), notificaciones con jerarquía completa.

### FASE 5 — CRM y métricas ✅ (23/23 tests)
Notas con filtro por `related_to` (MAT:, PROV:, PROD:), historial unificado chat+stock+notas, métricas por usuario y globales (admin).

### FASE 6 — Frontend React ✅
Chat con streaming, Stock con edición inline, CRM con 3 tabs, Admin con gestión de usuarios y sync, Notifications, modo oscuro.

### FASE 7 — Seguridad y hardening ✅ (21/21 tests)
HTTPS, CORS restringido, validaciones Pydantic (ge=0, min_length=1), manejo de errores LLM, tests de inyección y escalada de privilegios.

### FASE 8 — Tests E2E y refinamientos ✅ (35 tests E2E)
Flujos completos de extremo a extremo, system prompts mejorados, script de demo reset.

### FASE 9 — Chatbot con acciones ✅
Tool calling por rol, flujo de confirmación con action_token UUID (TTL 60s), action_log append-only, notificaciones automáticas.

### FASE 10 — Audio Whisper ✅
faster-whisper local, `POST /audio/transcribe`, grabación en frontend, integración con flujo de chat.

### FASE 11 — InvenTree + sync bidireccional ✅ (14/14 tests)
Docker Compose con InvenTree 1.3.5, datos de demo (10 productos, 4 seriales, 6 usuarios), sync en tiempo real cuando el chatbot ejecuta acciones (transfer, status_change, create/delete producto, create/deactivate usuario).

---

## Seguridad — mitigaciones implementadas

| Riesgo | Mitigación |
|--------|-----------|
| Fuerza bruta login | Bloqueo tras 5 intentos, rate limit configurable |
| JWT interceptado | HTTPS, refresh tokens con revocación por sesión |
| Acción sin confirmación | Token UUID de un solo uso (TTL 60s) requerido en backend |
| Replay de confirmación | Token marcado como `used=True` al consumirse |
| Prompt injection | Tools disponibles inyectadas dinámicamente por rol; LLM no puede escalar permisos |
| SQL injection | SQLAlchemy con queries parametrizadas |
| XSS en campos de estado | Validación Pydantic — solo valores permitidos |
| CORS abierto | Solo acepta origen del frontend configurado en `.env` |
| Escalada de privilegios | Rol validado en backend, no en LLM ni en frontend |
| Acceso cross-warehouse | `get_accessible_warehouse_ids()` filtra por jerarquía |
| Datos sensibles en logs | Audit log no guarda passwords ni tokens |

---

## Estructura del proyecto

```
Mercedes-mvp/
├── backend/
│   ├── main.py                  # FastAPI app + APScheduler
│   ├── config.py                # Settings (pydantic-settings)
│   ├── models.py                # SQLAlchemy models (12 tablas)
│   ├── schemas.py               # Pydantic schemas
│   ├── routers/                 # auth, stock, chatbot, actions, crm,
│   │                            # notifications, users, sync, audio
│   ├── services/                # auth, chatbot, action, stock, sync,
│   │                            # crm, metrics, inventree, audio
│   ├── tools/                   # LangChain tool registry por rol
│   └── middleware/              # JWT auth, rate limiter
├── frontend/
│   └── src/
│       ├── pages/               # Login, Chat, Stock, CRM, Notifications, Admin
│       ├── components/          # Navbar, RoleGuard, SlashCommandMenu/Wizard
│       ├── context/             # AuthContext (JWT, roles, dark mode)
│       ├── hooks/               # useNotifications
│       └── api/client.js        # Axios con auto-refresh
├── warehouse_agent/             # FastAPI ligero para laptops-almacén
├── scripts/
│   ├── populate_inventree.py    # Carga datos demo en InvenTree
│   └── sync_users_to_inventree.py  # Sincroniza usuarios chatbot → InvenTree
├── tests/                       # 192 tests organizados por módulo
├── C:\inventree-demo/
│   └── docker-compose.yml       # InvenTree 1.3.5 + PostgreSQL + worker
└── .env                         # Variables de entorno (no commitear)
```

---

## CRM — uso recomendado

El campo `related_to` permite vincular notas a entidades de negocio:

```
PROV:Bosch          → notas sobre un proveedor
MAT:1234-ABC        → historial de un vehículo por matrícula
PROD:SN-2041        → incidencia sobre un equipo serializado
ORDEN:WO-2026-047   → notas de una orden de trabajo
```

Filtrar: `GET /crm/notes?related_to=MAT:1234-ABC`

---

## Migración LLM

| Proveedor | Estado | Motivo |
|-----------|--------|--------|
| Groq Llama 3.3 70B | Descartado | VPN bloqueada |
| Google Gemini | Descartado | Cuota agotada |
| Anthropic Claude | Descartado | Solo pago |
| OpenRouter (kimi-k2.6:free) | Fallback disponible | Cuotas variables |
| **Ollama qwen2.5:7b** | **Activo** | 100% local, sin internet |
