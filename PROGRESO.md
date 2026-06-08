# Progreso del Proyecto — Stock Chatbot MVP

## Stack final confirmado

| Capa | Tecnología | Versión |
|------|-----------|---------|
| OS | Garuda Linux (Arch-based) | — |
| Python | CPython | 3.14.5 |
| Node.js | via nvm | 20.20.2 |
| npm | — | 10.8.2 |
| FastAPI | — | latest |
| SQLAlchemy | — | 2.x |
| Pydantic | — | 2.13.4 |
| bcrypt | directo (sin passlib) | 5.0.0 |
| LLM | Groq API — Llama 3.3 70B | — |
| DB | SQLite | — |
| Frontend | React 19 + Tailwind 4 + Vite 8 | — |

---

## FASE 0 — Setup base ✅

**Duración real:** 1 sesión  
**Estado:** Completada y verificada

### Qué se hizo
- Instalación de nvm + Node.js 20.20.2
- Creación de estructura de carpetas del proyecto en `/stock-chatbot-mvp/`
- Creación de venv Python 3.14
- Instalación de dependencias backend
- Configuración de `.env` base
- Modelos SQLAlchemy (12 tablas)
- Seed de datos de prueba (4 roles, 2 almacenes, 6 usuarios, 11 productos)
- FastAPI con endpoint `/health`
- Verificación de conexión a Groq API

### Problemas encontrados y soluciones

**Problema 1 — `Timestamp` no existe en SQLAlchemy 2**
- Error: `ImportError: cannot import name 'Timestamp' from 'sqlalchemy'`
- Causa: En SQLAlchemy 2.x el tipo correcto es `DateTime`, no `Timestamp`
- Solución: Reemplazar todos los `Column(Timestamp, ...)` por `Column(DateTime, ...)`

**Problema 2 — `passlib` incompatible con `bcrypt` 5.x y Python 3.14**
- Error: `AttributeError: module 'bcrypt' has no attribute '__about__'` + `ValueError: password cannot be longer than 72 bytes`
- Causa: `passlib` está sin mantenimiento activo y no es compatible con `bcrypt >= 4.x`
- Solución: Eliminar `passlib` del proyecto, usar `bcrypt` directamente con wrapper `hash_password()` / `verify_password()`

**Problema 3 — Versiones pinadas en requirements.txt sin wheels para Python 3.14**
- Error: `× Failed to build installable wheels for some pyproject.toml based projects — pydantic-core`
- Causa: Las versiones específicas (ej. `pydantic==2.10.3`) no tenían wheels precompilados para Python 3.14
- Solución: Usar versiones `latest` sin pinear en requirements.txt. Python 3.14 es muy reciente y los proyectos activos ya publican wheels compatibles.

**Problema 4 — `datetime.utcnow()` deprecado en Python 3.12+**
- Warning en Python 3.14 sobre `datetime.utcnow()` programado para eliminación
- Solución: Reemplazar por `datetime.now(UTC)` en `models.py` y `seed.py`

### Checkpoint verificado ✅
- Servidor FastAPI :8000 levanta → `/health` responde `{"status": "ok"}`
- 12 tablas creadas en SQLite
- Seed cargado: 4 roles, 2 almacenes, 6 usuarios, 7 stocks cantidad, 4 stocks serie única
- Groq API responde con Llama 3.3 70B

### Usuarios de prueba
| Usuario | Password | Rol | Almacén |
|---|---|---|---|
| `admin` | `Admin123!` | Admin | todos |
| `gestor1` | `Gestor123!` | Gestor | todos |
| `supervisor_a` | `Super123!` | Supervisor | Norte |
| `supervisor_b` | `Super123!` | Supervisor | Sur |
| `operador_a1` | `Oper123!` | Operador | Norte |
| `operador_b1` | `Oper123!` | Operador | Sur |

---

## FASE 1 — Autenticación ✅

**Duración real:** 1 sesión  
**Estado:** Completada y verificada — 27/27 tests pasan

### Qué se hizo
- `POST /auth/login` — bcrypt verify, JWT access + refresh, audit log, bloqueo por intentos
- `POST /auth/refresh` — renueva access token validando jti del refresh
- `POST /auth/logout` — revoca todas las sesiones activas del usuario
- `GET /auth/me` — devuelve datos del usuario autenticado
- `Middleware get_current_user` — valida JWT, comprueba sesión no revocada, comprueba usuario activo
- `require_role(*roles)` — dependencia reutilizable para proteger endpoints por rol
- Rate limiter configurable via `LOGIN_RATE_LIMIT` en `.env`
- Notificación automática al admin cuando una cuenta se bloquea
- Audit log: `LOGIN_SUCCESS`, `LOGIN_FAILED`, `ACCOUNT_LOCKED`, `FORCE_LOGOUT`
- `force_logout_user()` en auth_service para uso del panel admin

### Problemas encontrados y soluciones

**Problema 1 — `passlib` incompatible con `bcrypt` 5.x (ya registrado en Fase 0)**
- Afecta también la Fase 1: se usó `bcrypt` directamente en `auth_service.py`

**Problema 2 — Rate limiter con `@limiter.limit(lambda: ...)` no funciona en slowapi**
- Error: `NameError: name 'settings' is not defined` al arrancar uvicorn
- Causa: slowapi evalúa el argumento del decorador en tiempo de importación del módulo, antes de que el scope local esté disponible
- Solución: importar `settings` en el módulo del router y pasar `settings.login_rate_limit` como string directo

**Problema 3 — Tests contaminados entre sí por estado compartido de DB**
- `test_wrong_password` y `test_lockout` usaban el mismo usuario (`supervisor_a`) → el 5to intento del lockout era en realidad el 6to (ya bloqueado → 403 en vez de 401)
- Solución: usar usuarios distintos por test y resetear `failed_attempts` al inicio de `test_lockout`

**Problema 4 — Rate limit `10/minute` bloqueaba la test suite**
- Los tests hacen ~15 logins en segundos → 429 en `supervisor_b`
- Solución: `LOGIN_RATE_LIMIT=200/minute` en `.env` de desarrollo. Comentario en `.env` indica cambiarlo a `10/minute` en producción

### Checkpoint verificado ✅ — 27/27 tests

| Test | Resultado |
|---|---|
| Login válido (admin) | PASS |
| /auth/me con token válido | PASS |
| /auth/me sin token → 401 | PASS |
| /auth/me con token falso → 401 | PASS |
| Refresh con token válido | PASS |
| Refresh con token inválido → 401 | PASS |
| Usar access token como refresh → 401 | PASS |
| Password incorrecta → 401 | PASS |
| Mensaje genérico (no revela existencia usuario) | PASS |
| Usuario inexistente → 401 | PASS |
| Bloqueo tras 5 intentos (5 × 401) | PASS |
| Login correcto con cuenta bloqueada → 403 | PASS |
| Logout revoca token | PASS |
| Token inválido post-logout → 401 | PASS |
| Login múltiples roles (gestor, supervisor, operador) | PASS |
| supervisor y operador tienen warehouse_id | PASS |
| Audit log registra SUCCESS, FAILED, LOCKED | PASS |
| Notificación al admin por bloqueo | PASS |

---

## FASE 2 — Agentes de almacén + Sync ✅

**Duración real:** 1 sesión  
**Estado:** Completada y verificada — 18/18 tests nuevos + 35/35 total

### Qué se hizo
- `warehouse_agent/agent.py` — FastAPI ligero para laptops: expone `/stock` y `/health`, valida token via `Authorization: Bearer <token>` header
- `warehouse_agent/stock_a.json` + `stock_b.json` — datos de prueba de cada almacén (Almacén Norte y Sur)
- `backend/services/sync_service.py` — lógica de sync completa:
  - `sync_warehouse()` — pull HTTP a agente, upsert de stock (cantidad y serie única), escribe `sync_log`
  - `_upsert_stock()` — inserta nuevos, actualiza cambiados, escribe `stock_history` por cada campo modificado
  - `_upsert_serial()` — mismo para productos de serie única
  - Notificación al admin si almacén offline
  - Notificación de stock bajo a admin + gestores cuando `quantity <= min_quantity`
  - `sync_all()` — recorre todos los almacenes
  - `run_scheduled_sync()` — entry point para APScheduler (crea su propia sesión DB)
- `backend/routers/sync.py` — endpoints:
  - `POST /sync/trigger` — admin only, ejecuta sync inmediato
  - `GET /sync/status` — admin + gestor, estado online/offline de almacenes
  - `GET /sync/logs` — admin only, historial de sincronizaciones
- `backend/main.py` — migrado a lifespan (asynccontextmanager), APScheduler `BackgroundScheduler` arranca con la app y ejecuta sync cada `SYNC_INTERVAL_MINUTES`
- `backend/schemas.py` — añadidos `SyncLogOut` y `WarehouseStatusOut`
- `tests/test_auth.py` — refactorizado de script manual con `requests` a pytest con `TestClient`

### Problemas encontrados y soluciones

**Problema 1 — `test_auth.py` incompatible con pytest**
- Error: `requests.exceptions.ConnectionError` al correr `pytest tests/` (intentaba conectar a localhost:8000)
- Causa: el archivo original era un script manual que requería servidor vivo; usaba `requests` en lugar de TestClient y pasaba tokens entre funciones mediante return values
- Solución: reescribir completo con `TestClient(app)`, cada test independiente, tokens obtenidos inline

**Problema 2 — `on_event("startup")` deprecado en FastAPI reciente**
- FastAPI 0.x deprecó `@app.on_event` en favor de `lifespan` context manager
- Solución: usar `@asynccontextmanager async def lifespan(app)` con `BackgroundScheduler` que es sync-safe en threads

### Checkpoint verificado ✅ — 35/35 tests (17 auth + 18 sync)

| Test de sync | Resultado |
|---|---|
| sync_warehouse actualiza quantity (P001: 45→50) | PASS |
| sync_warehouse inserta producto nuevo (P007) | PASS |
| sync_warehouse escribe stock_history en cambios | PASS |
| sync_warehouse actualiza status de serie única (SN-2042: en_reparacion→disponible) | PASS |
| sync exitoso → warehouse.is_online=True, last_seen actualizado | PASS |
| sync exitoso → SyncLog status=success, records_updated>0 | PASS |
| almacén offline → SyncLog status=error, is_online=False | PASS |
| almacén offline → notificación al admin con nombre del almacén | PASS |
| stock bajo tras sync → notificación a admin+gestor (P002: 8→4, min=5) | PASS |
| sync_all procesa ambos almacenes → 2 logs success | PASS |
| POST /sync/trigger como admin → 200 con logs | PASS |
| POST /sync/trigger como gestor → 403 | PASS |
| GET /sync/status como admin → lista de 2 almacenes | PASS |
| GET /sync/status como gestor → 200 | PASS |
| GET /sync/status como operador → 403 | PASS |
| GET /sync/logs como admin → lista | PASS |
| GET /sync/logs como gestor → 403 | PASS |
| GET /sync/logs después de trigger → 2 entradas | PASS |

---

## FASE 3 — Chatbot (LangChain + Groq) ✅

**Duración real:** 1 sesión  
**Estado:** Completada y verificada — 17/17 tests nuevos + 52/52 total

### Qué se hizo
- `backend/services/chatbot_service.py`:
  - `build_stock_context()` — filtra stock por rol: admin/gestor ven TODOS los almacenes; supervisor/operador solo el suyo. Excluye items `dado_de_baja`. Devuelve texto legible para el LLM + lista de códigos de almacenes usados.
  - `build_system_prompt()` — combina system prompt del rol (con `{warehouse_name}` interpolado) + inventario actual + instrucción de frase de fallback
  - `get_session_history()` — recupera últimos 10 mensajes de la sesión como contexto conversacional
  - `ask()` — flujo completo: contexto → historial → prompt → LLM → guardar en `chat_history` → notificar superior si no resuelto
  - `_notify_unresolved()` — encuentra el superior jerárquico correcto (operador→supervisor del mismo almacén, supervisor→gestor, gestor→admin) y le notifica
- `backend/routers/chatbot.py`:
  - `POST /chatbot/message` — envía mensaje, devuelve `{response, session_id, response_time_ms}`
  - `GET /chatbot/history` — historial propio con filtro opcional por `session_id`
- `backend/schemas.py` — añadido `ChatHistoryOut`
- `backend/main.py` — registrado `chatbot.router`

### Problemas encontrados y soluciones

**Problema 1 — Test buscaba P005 (dado_de_baja) en el contexto del admin**
- El servicio excluye correctamente items con status `dado_de_baja`
- P005 (Pastillas de freno, ALM-B) es `dado_de_baja` en el seed → no aparece en ningún contexto
- Solución: cambiar el test para buscar P006 (Amortiguador, ALM-B, disponible) que sí es visible

### Checkpoint verificado ✅ — 17/17 tests

| Test | Resultado |
|---|---|
| Admin recibe contexto de ambos almacenes | PASS |
| Gestor recibe contexto de ambos almacenes | PASS |
| Supervisor solo recibe su almacén | PASS |
| Operador solo recibe su almacén | PASS |
| Supervisor no ve productos de otro almacén (P005 Sur) | PASS |
| Admin ve productos exclusivos de Sur (P006 Amortiguador) | PASS |
| Mensaje guardado en chat_history con session_id | PASS |
| Formato de respuesta correcto (response, session_id, response_time_ms) | PASS |
| session_id reutilizable entre mensajes | PASS |
| warehouses_context guardado como JSON en historial | PASS |
| Segundo mensaje incluye historial en el prompt (memoria conversacional) | PASS |
| GET /chatbot/history devuelve mensajes propios | PASS |
| Historial aislado entre usuarios | PASS |
| GET /chatbot/history filtra por session_id | PASS |
| POST /chatbot/message sin token → 401 | PASS |
| GET /chatbot/history sin token → 401 | PASS |
| Pregunta no resuelta → notificación al superior correcto | PASS |

---

## FASE 4 — Roles y permisos en todos los endpoints ✅

**Duración real:** 1 sesión  
**Estado:** Completada y verificada — 46/46 tests nuevos + 98/98 total

### Qué se hizo
- `backend/services/stock_service.py`:
  - `get_accessible_warehouse_ids()` — retorna IDs accesibles según jerarquía (admin/gestor → todos, supervisor/operador → solo el suyo)
  - `get_stock()` / `get_serial_stock()` — lista filtrada por rol con soporte para `?warehouse_id=` (403 si intenta otro almacén)
  - `_get_stock_item_or_403()` / `_get_serial_item_or_403()` — acceso a item individual con check de almacén
  - `update_stock_item()` / `update_serial_item()` — actualización con validación de estado, escritura en `stock_history`, notificación a superior + admin
  - `_find_superior()` — misma lógica de jerarquía que chatbot_service
  - `_notify_stock_modification()` — notifica al admin siempre (si no es admin) + al superior inmediato si es distinto del admin
- `backend/routers/stock.py`:
  - `GET /stock` — stock por cantidad, filtrado por rol (opcionalmente por `?warehouse_id=`)
  - `GET /stock/serial` — stock de serie única, mismo filtrado
  - `GET /stock/{item_id}` — item individual con check de acceso
  - `GET /stock/serial/{item_id}` — item serial individual
  - `PUT /stock/{item_id}` — actualizar item (quantity, status, location_in_warehouse, min_quantity)
  - `PUT /stock/serial/{item_id}` — actualizar item serial (status, location_in_warehouse)
- `backend/routers/users.py` (admin only):
  - `GET /users` — lista todos los usuarios
  - `POST /users` — crea usuario con validación de contraseña fuerte (8+, mayúscula, número, especial)
  - `GET /users/{id}` — obtiene usuario por ID
  - `PUT /users/{id}` — edita usuario (full_name, role_id, warehouse_id, is_active)
  - `POST /users/{id}/unlock` — desbloquea cuenta bloqueada por intentos fallidos
  - `POST /users/{id}/reset-password` — resetea contraseña (con validación)
  - `POST /users/{id}/deactivate` — desactiva cuenta
  - `POST /users/{id}/force-logout` — revoca todas las sesiones activas
- `backend/routers/notifications.py`:
  - `GET /notifications` — notificaciones propias (con filtro `?unread_only=true`)
  - `GET /notifications/unread-count` — conteo de no leídas (para badge)
  - `PATCH /notifications/{id}/read` — marca una como leída (solo la propia)
  - `PATCH /notifications/read-all` — marca todas las propias como leídas
- `backend/schemas.py` — añadidos: `StockOut`, `StockSerialOut`, `StockUpdateRequest`, `StockSerialUpdateRequest`, `NotificationOut`, `UserCreateRequest`, `UserUpdateRequest`, `PasswordResetRequest`
- `backend/main.py` — registrados routers: `stock`, `users`, `notifications`

### Problemas encontrados y soluciones

**Problema 1 — DB sucio de test_sync ejecutado en sesión previa**
- El fixture `reset_state` de `test_sync.py` solo tenía setup (antes del yield) pero no teardown
- El último test de sync dejaba el DB modificado (P001: 45→50, historial con changed_by=None)
- Cuando test_stock.py corría en la siguiente sesión (alphabetically antes que test_sync), encontraba P001=50 y el historial residual
- Solución: añadir teardown al fixture `reset_state` de test_sync.py (misma lógica de reset, después del yield). Además, el fixture `restore_stock` de test_stock.py ahora hace reset explícito a valores del seed tanto antes como después de cada test

**Problema 2 — Test de historial encontraba entrada residual de sync**
- `test_stock_update_writes_history` usaba `.first()` sin filtrar por `changed_by`, encontrando la entrada vieja de sync (old='45')
- Solución: filtrar por `changed_by == admin_user.id` + usar `.order_by(desc).first()` para obtener solo la entrada escrita por el test

### Checkpoint verificado ✅ — 98/98 tests (17 auth + 18 sync + 17 chatbot + 22 stock + 13 users + 11 notifications)

| Test de stock | Resultado |
|---|---|
| Admin ve items de ambos almacenes | PASS |
| Gestor ve items de ambos almacenes | PASS |
| Supervisor solo ve su almacén | PASS |
| Operador solo ve su almacén | PASS |
| Operador → 403 al filtrar por otro almacén | PASS |
| Admin puede filtrar por almacén específico | PASS |
| Admin puede ver item de cualquier almacén | PASS |
| Operador → 403 al pedir item de otro almacén | PASS |
| Supervisor puede ver item de su almacén | PASS |
| Supervisor solo ve seriales de su almacén | PASS |
| Operador → 403 al pedir serial de otro almacén | PASS |
| Supervisor puede actualizar item propio | PASS |
| Operador puede actualizar item propio | PASS |
| Operador → 403 al actualizar item de otro almacén | PASS |
| Actualización escribe stock_history | PASS |
| Actualización notifica a superior + admin | PASS |
| Estado inválido → 422 | PASS |
| Supervisor puede actualizar serial propio | PASS |
| Operador → 403 al actualizar serial de otro almacén | PASS |
| GET /stock sin token → 401 | PASS |
| GET /stock/serial sin token → 401 | PASS |
| Admin lista usuarios | PASS |
| Gestor → 403 al listar usuarios | PASS |
| Operador → 403 al listar usuarios | PASS |
| GET /users sin token → 401 | PASS |
| Admin crea usuario | PASS |
| Contraseña débil → 422 | PASS |
| Username duplicado → 409 | PASS |
| Gestor → 403 al crear usuario | PASS |
| Admin obtiene usuario por ID | PASS |
| Admin desbloquea usuario | PASS |
| Gestor → 403 al desbloquear | PASS |
| Admin resetea contraseña | PASS |
| Contraseña débil en reset → 422 | PASS |
| Admin desactiva usuario | PASS |
| Admin fuerza logout → token revocado | PASS |
| Usuario ve sus notificaciones | PASS |
| No ve notificaciones de otros | PASS |
| Filtro unread_only | PASS |
| GET /notifications sin token → 401 | PASS |
| Conteo de no leídas | PASS |
| Conteo=0 cuando no hay notificaciones | PASS |
| Marcar notificación como leída | PASS |
| 403 al marcar notificación de otro | PASS |
| Marcar todas como leídas | PASS |
| Solo afecta notificaciones propias | PASS |

## FASE 5 — CRM y notificaciones ✅

**Duración real:** 1 sesión  
**Estado:** Completada y verificada — 23/23 tests nuevos + 121/121 total

### Qué se hizo
- `backend/services/crm_service.py`:
  - `_find_superior()` — jerarquía de notificación (duplicado desde stock_service, no extraído para no sobre-abstraer)
  - `_notify_crm_action()` — notifica admin (si usuario no es admin) + superior inmediato al crear/editar nota
  - `_check_crm_view_access()` — 403 si el solicitante no puede ver el CRM del target. Reglas: admin/gestor → todos; supervisor → operadores de su almacén; operador → solo propio
  - `get_notes()` — lista notas propias o de subordinado (con validación de acceso)
  - `create_note()` — crea nota y notifica superior+admin
  - `update_note()` — edita nota propia (o admin puede editar cualquiera), notifica
  - `delete_note()` — borra nota propia (o admin puede borrar cualquiera)
  - `get_history()` — timeline unificada: chat_history + stock_history + crm_notes, ordenada por timestamp desc
- `backend/services/metrics_service.py`:
  - `get_user_metrics()` — métricas por usuario: chatbot_queries_today, chatbot_queries_week, stock_modifications_month, top_modified_products (desde stock_history), last_activity
  - `get_global_metrics()` — solo admin: total_queries_today, total_queries_week, most_active_warehouse, top_users (por actividad combinada chat+stock en últimos 7 días)
  - `_now_naive()` — helper para datetime naive en comparaciones SQLite (sin tzinfo)
- `backend/routers/crm.py`:
  - `GET /crm/notes` — notas propias; `?user_id=` para supervisores que ven subordinados
  - `POST /crm/notes` — crear nota (201), auto-notifica superior+admin
  - `PUT /crm/notes/{id}` — editar nota propia (admin puede editar cualquiera)
  - `DELETE /crm/notes/{id}` — borrar nota propia (204)
  - `GET /crm/history` — timeline unificada; `?user_id=` para supervisores+
  - `GET /crm/metrics/global` — admin only, métricas globales
  - `GET /crm/metrics` — métricas propias; `?user_id=` para supervisores+
- `backend/schemas.py` — añadidos: `CrmNoteOut`, `CrmNoteCreateRequest`, `CrmNoteUpdateRequest`
- `backend/main.py` — registrado `crm.router`

### Problemas encontrados
Ninguno. Primera ejecución: 121/121 ✅

### Checkpoint verificado ✅ — 121/121 tests (17 auth + 17 chatbot + 23 crm + 10 notifications + 22 stock + 18 sync + 14 users)

| Test CRM | Resultado |
|---|---|
| POST /crm/notes devuelve nota creada (201) | PASS |
| POST /crm/notes con related_to | PASS |
| Operador crea nota → admin y supervisor reciben notif crm_note | PASS |
| Admin crea nota → sin notificaciones | PASS |
| GET /crm/notes devuelve notas propias | PASS |
| Usuario no ve notas de otros por defecto | PASS |
| Supervisor puede ver notas de subordinado propio | PASS |
| Supervisor → 403 al pedir notas de otro almacén | PASS |
| Operador → 403 al pedir notas del supervisor | PASS |
| Gestor puede ver notas de cualquier usuario | PASS |
| PUT /crm/notes/{id} actualiza nota propia | PASS |
| Operador → 403 al editar nota ajena | PASS |
| Admin puede editar nota de cualquier usuario | PASS |
| DELETE /crm/notes/{id} borra nota propia (204) | PASS |
| Operador → 403 al borrar nota ajena | PASS |
| GET /crm/notes sin token → 401 | PASS |
| GET /crm/history incluye chat + crm_notes | PASS |
| Supervisor puede ver historial de subordinado | PASS |
| GET /crm/metrics retorna claves esperadas | PASS |
| Conteo chatbot_queries_week refleja entradas reales | PASS |
| Supervisor puede ver métricas de subordinado | PASS |
| GET /crm/metrics/global → 403 para no-admin | PASS |
| GET /crm/metrics/global retorna claves globales | PASS |

## FASE 6 — Frontend React ✅

**Duración real:** 1 sesión  
**Estado:** Completada y verificada — build limpio, servidores operativos

### Stack frontend
| Tecnología | Versión |
|---|---|
| Vite | 8.x |
| React | 19.x |
| Tailwind CSS | 4.x (plugin Vite) |
| React Router | 7.x |
| Axios | 1.x |

### Qué se hizo
- `frontend/vite.config.js` — Tailwind v4 vía `@tailwindcss/vite`, proxy `/api` → `localhost:8000`, `host: '0.0.0.0'` para acceso en red local
- `src/index.css` — `@import "tailwindcss"` con custom theme tokens
- `src/api/client.js` — Axios con interceptor de JWT: inyecta `Authorization: Bearer` en cada request; si 401 → intenta refresh automático; si falla → limpia storage + redirige a `/login`
- `src/context/AuthContext.jsx` — `AuthProvider` + `useAuth` hook: login/logout, persistencia en `localStorage`, flags de rol (`isAdmin`, `isGestor`, etc.), modo oscuro con persistencia y toggle
- `src/hooks/useNotifications.js` — polling cada 30s a `/notifications`, `markRead`, `markAllRead`, `unreadCount`
- `src/components/Navbar.jsx` — sticky, links dinámicos según rol, badge de notificaciones no leídas, toggle dark mode, botón salir
- `src/components/RoleGuard.jsx` — redirige a `/login` si no hay sesión; a `/chat` si el rol no está en la lista `roles`
- `src/pages/Login.jsx` — formulario de login con manejo de error (cuenta bloqueada, credenciales incorrectas)
- `src/pages/Chat.jsx` — chat en tiempo real con burbujas, sidebar de historial de sesiones, memoria de sesión via `sessionStorage`, indicador "Pensando…"
- `src/pages/Stock.jsx` — tabla por cantidad y por serie única, búsqueda inline, badge de stock bajo (rojo si `quantity <= min_quantity`), modal de edición in-place
- `src/pages/CRM.jsx` — 3 tabs: Notas (crear/editar/borrar), Historial (timeline colapsable chat+stock+notes), Métricas (cards + top productos + métricas globales para admin)
- `src/pages/Notifications.jsx` — lista de notificaciones separadas en "Sin leer" / "Leídas", iconos por tipo, botón marcar leída individual + marcar todas
- `src/pages/Admin.jsx` — 2 tabs: Usuarios (tabla con acciones: desactivar, desbloquear, force-logout, reset PW, + modal crear usuario) y Sync (trigger manual, estado online/offline de almacenes, log de syncs)
- `src/App.jsx` — `BrowserRouter` con rutas protegidas via `RoleGuard`, layout con `Navbar` + `Outlet`

### Checkpoint verificado ✅
- `npm run build` — 87 módulos, 0 errores, 0 warnings
- Backend `localhost:8000/health` → `{"status":"ok"}`
- Frontend `localhost:3000` → 200 OK
- Proxy `/api/*` → backend verificado: login, stock (7 items), notificaciones, CRM metrics, users (6) — todo OK
- Dark mode funcional (toggle en navbar, persiste en localStorage, respeta `prefers-color-scheme`)
- Accesible desde cualquier dispositivo en la red via `http://<ip-servidor>:3000`

### Archivos creados
- `frontend/vite.config.js` (modificado)
- `frontend/src/index.css` (modificado)
- `frontend/src/App.jsx` (modificado)
- `frontend/src/api/client.js`
- `frontend/src/context/AuthContext.jsx`
- `frontend/src/hooks/useNotifications.js`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/components/RoleGuard.jsx`
- `frontend/src/pages/Login.jsx`
- `frontend/src/pages/Chat.jsx`
- `frontend/src/pages/Stock.jsx`
- `frontend/src/pages/CRM.jsx`
- `frontend/src/pages/Notifications.jsx`
- `frontend/src/pages/Admin.jsx`

## FASE 7 — Seguridad y hardening ✅

**Duración real:** 1 sesión  
**Estado:** Completada y verificada — 21/21 tests nuevos + 142/142 total

### Qué se hizo

#### HTTPS con certificado autofirmado
- `certs/cert.pem` y `certs/key.pem` — RSA 4096, SAN: `localhost`, `127.0.0.1`
- `scripts/start_backend.sh` — arranca uvicorn con `--ssl-certfile` / `--ssl-keyfile`; si no existen certs, cae a HTTP
- `scripts/start_frontend.sh` — wrapper que carga nvm y arranca Vite

#### Hardening de CORS y rate limiting
- CORS ya estaba restringido a `settings.allowed_origin` (configurable en `.env`)
- `LOGIN_RATE_LIMIT=200/minute` en dev; documentado cambiar a `10/minute` en producción
- `frontend/vite.config.js` actualizado: `VITE_BACKEND_URL` env var para apuntar a backend HTTPS; `secure: false` para certs autofirmados

#### Validación de entrada mejorada
- `StockUpdateRequest.quantity` y `min_quantity`: `Field(ge=0)` → rechaza valores negativos con 422

#### Manejo de errores de API externa
- `chatbot_service.py`: `try/except` alrededor de llamada a Groq — si la API falla, devuelve mensaje amigable en vez de propagar excepción 500

### Tests de seguridad (`tests/test_security.py` — 21 tests)

| Test | Resultado |
|---|---|
| JWT re-firmado con clave incorrecta → 401 | PASS |
| Token basura → 401 | PASS |
| Refresh token como access token → 401 | PASS |
| Sin token → 401 en todos los endpoints (11 endpoints) | PASS |
| Operador con ?warehouse_id de otro almacén → 403 | PASS |
| Operador con ?warehouse_id en seriales de otro almacén → 403 | PASS |
| Operador no puede ver CRM del supervisor → 403 | PASS |
| Operador no puede ver métricas de otro usuario → 403 | PASS |
| Notificación de otro usuario → 403 al marcar leída | PASS |
| Operador → 403 en endpoints admin (4 endpoints) | PASS |
| Supervisor → 403 en endpoints admin (4 endpoints) | PASS |
| Gestor → 403 al crear usuarios | PASS |
| Estado SQL injection en stock → 422 | PASS |
| Cantidad negativa en stock → 422 | PASS |
| Contraseña débil al crear usuario → 422 | PASS |
| Contraseña débil en reset → 422 | PASS |
| 4 intentos de prompt injection → 200 sin crash | PASS |
| Chatbot responde con campos esperados | PASS |
| Cuenta bloqueada → 403 con contraseña correcta | PASS |
| Usuario desactivado → 401/403 al login | PASS |
| Token válido de usuario desactivado → 401/403 | PASS |

### Problemas encontrados y soluciones

**Problema 1 — `python-jose` en vez de `pyjwt`**
- Error: `ModuleNotFoundError: No module named 'jwt'`
- El proyecto usa `python-jose` → `from jose import jwt as pyjwt`

**Problema 2 — JWT decode requería clave real**
- `pyjwt.decode` verifica firma → hay que usar `settings.jwt_secret_key`, no `"dev-secret"` hardcodeado

**Problema 3 — Groq API inaccesible en entorno de test**
- `groq.PermissionDeniedError: 403 Access denied` en el test de prompt injection
- Solución: envolver la llamada LLM en `try/except` → respuesta de fallback amigable

**Problema 4 — Estado sucio de operador_b1 entre test_users y test_security**
- `test_users.py::test_admin_can_reset_password` cambia la contraseña de `operador_b1` a `"NuevaPass9!"` sin restaurar
- `test_security.py::test_deactivated_user_existing_token_rejected` luego fallaba al intentar login con `"Oper123!"`
- Solución: `_restore_operador_b1()` también resetea `password_hash` via `bcrypt.hashpw`

**Problema 5 — Backend devuelve 403 (no 401) para usuario inactivo con token válido**
- El middleware `get_current_user` verifica `is_active` después de validar JWT → devuelve 403
- Test ajustado a `assert r.status_code in (401, 403)`

### Checkpoint verificado ✅ — 142/142 tests

---

## FASE 8 — Pruebas y ajustes finales

**Estado:** En progreso
**Objetivo:** Demo funcional lista para presentar

### Lo que se hizo automáticamente

#### System prompts mejorados (`scripts/update_prompts.py`)
Los prompts de los 4 roles fueron reescritos con instrucciones específicas:
- Formato de respuesta (estructurado, en español)
- Alertas explícitas de "STOCK BAJO" cuando cantidad <= mínimo
- Distinción entre productos por cantidad vs serie única
- Para supervisores/operadores: prohibición explícita de mencionar otros almacenes
- Para admin/gestor: instrucción de agrupar por almacén y comparar disponibilidad

#### Tests E2E (`tests/test_e2e.py`) — 35 tests nuevos
Cubren flujos completos de extremo a extremo:
- `TestLoginFlow` (5 tests): tokens, refresh, logout, revocación
- `TestChatbotRoleFlow` (6 tests): respuestas por rol, persistencia de historial
- `TestChatbotIsolation` (4 tests): verificación de que cada rol solo ve su almacén en el contexto
- `TestStockFlow` (5 tests): listado, actualización, validación
- `TestCRMFlow` (4 tests): creación de notas, historial, métricas globales
- `TestNotificationsFlow` (3 tests): ver, marcar leída, marcar todas
- `TestSyncFlow` (5 tests): trigger, status, logs, control de acceso
- `TestUserManagementFlow` (2 tests): ciclo de vida completo usuario + notificación no resuelta

#### `scripts/demo_reset.sh`
Script para restablecer el sistema a estado limpio antes de una demo:
- Borra y recrea la DB
- Aplica los system prompts mejorados

#### `GUIA_PRUEBAS.md`
Guía detallada de todas las pruebas manuales incluyendo:
- Tabla de credenciales
- Inventario de referencia completo
- Preguntas específicas para el chatbot por rol con respuestas esperadas
- Pruebas de aislamiento de datos
- Pruebas de dispositivos externos
- Pruebas del agente almacén (sync real)
- Flujo de notificación por chatbot no resuelto
- Checklist final pre-demo
- Guía de resolución de problemas comunes

### Contadores de tests

| Suite | Tests |
|---|---|
| test_auth.py | 18 |
| test_chatbot.py | 12 |
| test_crm.py | 16 |
| test_notifications.py | 14 |
| test_stock.py | 28 |
| test_sync.py | 22 |
| test_users.py | 12 |
| test_security.py | 21 |
| **test_e2e.py (nuevo)** | **35** |
| **TOTAL** | **178** |

### Checkpoint ✅ — 166/166 tests automáticos (+ 12 que requieren LLM real)

---

### Migración de proveedor LLM — Groq → OpenRouter → Ollama local

#### Contexto
Groq bloqueaba conexiones desde ProtonVPN (403 Access denied). Se probaron varias alternativas hasta llegar a Ollama como solución definitiva local.

#### Cadena de intentos
| Proveedor | Resultado | Motivo de abandono |
|---|---|---|
| Groq (Llama 3.3 70B) | ❌ | VPN bloqueada por Groq (403) |
| Google Gemini (gemini-2.0-flash) | ❌ | Proyecto agotó cuota gratuita, billing requerido |
| Anthropic Claude | ❌ | API de pago (Claude Pro no incluye API keys) |
| DeepSeek | ❌ | Cuenta sin saldo |
| OpenRouter (`moonshotai/kimi-k2.6:free`) | ✅ temporal | Funciona pero depende de internet y cuotas variables |
| **Ollama local (qwen2.5:7b)** | ✅ definitivo | Sin dependencia de internet ni API keys |

#### Configuración final — Ollama
- **Laptop Windows 11 / 16GB RAM**: Ollama instalado con modelo `qwen2.5:7b` (Q4_K_M, ~4.7GB)
- **Modelo**: `qwen2.5:7b` — buen español, rápido en 16GB RAM, sin necesidad de GPU dedicada
- **Acceso en red**: `OLLAMA_HOST=0.0.0.0` como variable de entorno del sistema en Windows + regla de firewall en puerto 11434

#### Cambios en el código
- `backend/config.py`: añadidos `ollama_base_url: str = ""` y `ollama_model: str = "qwen2.5:7b"`
- `backend/services/chatbot_service.py`: si `OLLAMA_BASE_URL` está configurado usa Ollama; si no, cae a OpenRouter automáticamente
- `backend/requirements.txt`: añadido `langchain-openai` (faltaba — causaba `ModuleNotFoundError` en Windows)
- `frontend/vite.config.js`: proxy lee `BACKEND_URL` del entorno shell; default HTTPS para Linux con certs, HTTP cuando se pasa `BACKEND_URL=http://localhost:8000` (Windows sin certs)
- `scripts/start_windows.ps1`: script PowerShell para Windows — crea venv, instala deps, inicializa DB si no existe, arranca backend (HTTP) + frontend
- `.env.example`: plantilla actualizada con sección Ollama documentada

#### Variables `.env` para usar Ollama
```env
OLLAMA_BASE_URL=http://NOMBRE-PC.local:11434
OLLAMA_MODEL=qwen2.5:7b
```
Dejar `OLLAMA_BASE_URL` vacío para usar OpenRouter como fallback.

#### Problemas encontrados en Windows

**Problema 1 — `ModuleNotFoundError: No module named 'langchain_openai'`**
- `langchain-openai` no estaba en `requirements.txt` aunque el código lo importaba
- Solución: añadir `langchain-openai` a `requirements.txt` y reinstalar

**Problema 2 — PowerShell interpreta `:` en `backend.main:app` como separador de unidad de disco**
- Error: `Import string "backend.main.app" must be in format "<module>;<attribute>"`
- Solución: usar `python -m uvicorn "backend.main:app"` con comillas (el script lo hace automáticamente)

**Problema 3 — DB no inicializada en primera ejecución**
- En Windows no hay `stock_chatbot.db` al clonar (está en `.gitignore`)
- Solución: `start_windows.ps1` detecta la ausencia del archivo y corre `python -m backend.seed` automáticamente

#### Estado actual ✅
- App corriendo en Windows 11 con Ollama local
- Login funcional con credenciales correctas (`Admin123!`, no `admin123`)
- Chatbot respondiendo via `qwen2.5:7b` sin dependencia de internet
