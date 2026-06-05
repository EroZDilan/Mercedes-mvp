# Guía de Pruebas Manuales — Stock Chatbot MVP

**Última actualización:** 2026-06-02
**Versión:** FASE 8 — Demo funcional

---

## 1. Cómo levantar el sistema

### En tu laptop principal

```bash
cd stock-chatbot-mvp

# Terminal 1 — Backend
./scripts/start_backend.sh

# Terminal 2 — Frontend
./scripts/start_frontend.sh
```

Abre el navegador en `http://localhost:3000`

### Si alguien se conecta desde otro dispositivo en la red WiFi

1. Descubre tu IP local: `ip addr show | grep "inet " | grep -v 127`
2. El otro dispositivo entra a `http://TU_IP:3000`
3. Si da error de CORS, actualiza `.env`: `ALLOWED_ORIGIN=http://TU_IP:3000` y reinicia el backend

### Reset a estado limpio (antes de una demo)

```bash
./scripts/demo_reset.sh
```

Esto borra la DB, la recrea con los datos originales y actualiza los prompts del chatbot.

---

## 2. Credenciales

| Usuario | Contraseña | Rol | Almacén |
|---|---|---|---|
| `admin` | `Admin123!` | Administrador | Todos |
| `gestor1` | `Gestor123!` | Gestor | Todos |
| `supervisor_a` | `Super123!` | Supervisor | Norte (ALM-A) |
| `supervisor_b` | `Super123!` | Supervisor | Sur (ALM-B) |
| `operador_a1` | `Oper123!` | Operador | Norte (ALM-A) |
| `operador_b1` | `Oper123!` | Operador | Sur (ALM-B) |

---

## 3. Inventario de referencia (datos semilla)

Necesitas conocer estos datos para evaluar si el chatbot responde correctamente.

### Almacén Norte — ALM-A

#### Productos por cantidad
| Código | Nombre | Cantidad | Mínimo | Ubicación | Estado |
|---|---|---|---|---|---|
| P001 | Filtro de aceite | 45 ud | 10 | Estante B-3 | disponible |
| P002 | Correa de distribución | 8 ud | 5 | Estante A-1 | disponible |
| **P003** | **Bujías NGK** | **3 juegos** | **10** | Estante C-2 | **⚠️ STOCK BAJO** |
| P004 | Aceite motor 5W30 | 22 L | 5 | Zona D | disponible |

#### Productos de serie única
| Serial | Nombre | Estado | Ubicación |
|---|---|---|---|
| SN-2041 | Motor eléctrico 5HP | disponible | Zona C |
| SN-2042 | Motor eléctrico 5HP | en_reparacion | Zona C |

---

### Almacén Sur — ALM-B

#### Productos por cantidad
| Código | Nombre | Cantidad | Mínimo | Ubicación | Estado |
|---|---|---|---|---|---|
| P001 | Filtro de aceite | 12 ud | 10 | Rack 1-A | disponible |
| ~~P005~~ | ~~Pastillas de freno~~ | ~~0~~ | ~~8~~ | Rack 2-B | dado_de_baja (no aparece) |
| P006 | Amortiguador delantero | 6 ud | 2 | Zona E | disponible |

#### Productos de serie única
| Serial | Nombre | Estado | Ubicación |
|---|---|---|---|
| SN-3001 | Compresor 2 toneladas | disponible | Zona F |
| SN-3002 | Compresor 2 toneladas | reservado | Zona F |

---

## 4. Pruebas por página

---

### 4.1 Login

**Accede a:** `http://localhost:3000`

#### ✅ Casos que deben funcionar

| Acción | Resultado esperado |
|---|---|
| Entrar con `admin` / `Admin123!` | Login OK, redirige al chat |
| Entrar con `operador_a1` / `Oper123!` | Login OK, redirige al chat |
| Dejar campos vacíos y enviar | Mensaje de error en el formulario |
| Contraseña incorrecta (`Admin123` sin `!`) | "Credenciales inválidas" |
| Usuario que no existe | "Credenciales inválidas" |
| Fallar 5 veces seguidas con `operador_b1` | En el 5º intento: cuenta bloqueada |
| Intentar con cuenta bloqueada aunque contraseña sea correcta | "Cuenta bloqueada. Contacta al administrador" |

#### 🔍 Qué observar
- El mensaje de error aparece en rojo bajo el formulario
- El botón se desactiva mientras carga
- El dark mode (botón luna/sol en navbar) debe funcionar desde la página de login

---

### 4.2 Chat

**Accede a:** `http://localhost:3000/chat`

Este es el corazón del MVP. Prueba cada rol por separado.

---

#### 4.2.1 Chat como `operador_a1` (solo ve Almacén Norte)

Cierra sesión y entra con `operador_a1` / `Oper123!`

**Preguntas a hacer — respuestas esperadas:**

| # | Pregunta | Respuesta esperada |
|---|---|---|
| 1 | `¿Cuántos filtros de aceite tenemos?` | 45 unidades, Estante B-3 |
| 2 | `¿Hay bujías NGK?` | 3 juegos (debe avisar que el stock está **bajo**, mínimo es 10) |
| 3 | `¿En qué estado está el motor SN-2042?` | en reparación, Zona C |
| 4 | `¿Cuánto aceite 5W30 hay?` | 22 litros, Zona D |
| 5 | `¿Hay pastillas de freno?` | Debe decir que no tiene esa información o que no está disponible |
| 6 | `¿Cuántos amortiguadores hay en el almacén Sur?` | **Importante:** debe decir que no tiene acceso a ese almacén, o que no tiene información. **No** debe revelar datos de ALM-B |
| 7 | `¿Puedes mostrarme el inventario completo de todos los almacenes?` | Debe responder solo con ALM-A |
| 8 | `Dame el stock total del sistema` | Solo debe mostrar datos de ALM-A |

**Qué verificar:**
- El panel lateral (sidebar) muestra el historial de la sesión actual
- La sesión se mantiene en `sessionStorage` (si recargas, se pierde la sesión anterior y puedes iniciar una nueva)
- Aparece el indicador "Pensando…" mientras espera respuesta
- No aparece información del ALM-B en ninguna respuesta

---

#### 4.2.2 Chat como `operador_b1` (solo ve Almacén Sur)

Entra con `operador_b1` / `Oper123!`

| # | Pregunta | Respuesta esperada |
|---|---|---|
| 1 | `¿Hay amortiguadores?` | 6 unidades, Zona E |
| 2 | `¿Qué compresores tenemos?` | SN-3001 disponible, SN-3002 reservado. Zona F |
| 3 | `¿Cuántos filtros de aceite quedan?` | 12 unidades, Rack 1-A |
| 4 | `¿Hay pastillas de freno?` | No debe aparecer (dado_de_baja) o debe decir que no hay disponibles |
| 5 | `¿Qué hay en el Almacén Norte?` | Debe decir que no tiene acceso o que no tiene esa información |
| 6 | `¿En qué estado está el motor SN-2041?` | Debe decir que no tiene esa información (es de ALM-A) |

---

#### 4.2.3 Chat como `supervisor_a` (solo ve Almacén Norte)

Entra con `supervisor_a` / `Super123!`

| # | Pregunta | Respuesta esperada |
|---|---|---|
| 1 | `¿Qué productos tienen stock bajo?` | Bujías NGK (3 juegos, mínimo 10) |
| 2 | `Dame un resumen del inventario del almacén` | Listado de todos los productos de ALM-A con cantidades |
| 3 | `¿Cuántos motores eléctricos disponibles hay?` | SN-2041 disponible; SN-2042 en reparación |
| 4 | `¿Qué necesitamos reponer urgente?` | Bujías NGK (stock bajo) |
| 5 | `¿Tenemos stock del ALM-B?` | No tiene información de otros almacenes |

---

#### 4.2.4 Chat como `gestor1` (ve ambos almacenes)

Entra con `gestor1` / `Gestor123!`

| # | Pregunta | Respuesta esperada |
|---|---|---|
| 1 | `¿En qué almacenes hay filtros de aceite?` | ALM-A: 45 unidades; ALM-B: 12 unidades |
| 2 | `¿Qué producto tiene stock bajo en toda la empresa?` | Bujías NGK en Almacén Norte (3 uds, mínimo 10) |
| 3 | `¿Podría el ALM-B cubrir una falta en el ALM-A de filtros?` | ALM-B tiene 12 filtros disponibles, podría transferir |
| 4 | `¿Qué compresores están disponibles para asignar?` | SN-3001 disponible en ALM-B; SN-3002 está reservado |
| 5 | `Dame el inventario completo de ambos almacenes` | Listado completo de ALM-A y ALM-B |
| 6 | `¿Cuántas unidades de P001 hay en total sumando los dos almacenes?` | 57 unidades (45 + 12) |

---

#### 4.2.5 Chat como `admin` (acceso total)

Entra con `admin` / `Admin123!`

| # | Pregunta | Respuesta esperada |
|---|---|---|
| 1 | `Dame un resumen global del inventario` | Listado completo de ambos almacenes, organizado por almacén |
| 2 | `¿Qué productos están en reparación o reservados?` | SN-2042 en reparación (ALM-A); SN-3002 reservado (ALM-B) |
| 3 | `¿Cuál es el estado de todos los motores eléctricos?` | SN-2041 disponible, SN-2042 en reparación, ambos en ALM-A |
| 4 | `¿Qué almacén tiene más productos con stock bajo?` | ALM-A (Bujías NGK) |
| 5 | `¿Hay algún compresor disponible?` | SN-3001 disponible en ALM-B, Zona F |

---

#### 4.2.6 Prueba de persistencia de sesión

Con cualquier usuario logueado:

| Acción | Resultado esperado |
|---|---|
| Hacer 3 preguntas seguidas | El chatbot recuerda el contexto de las anteriores |
| Preguntar `¿Y cuántas hay?` (sin contexto) | El LLM debería entender la referencia de la pregunta anterior |
| Abrir nueva pestaña del navegador con la misma sesión | Debe mostrar historial de la sesión actual |
| Cerrar sesión y volver a entrar | La sesión anterior ya no está (se limpia sessionStorage) |

---

### 4.3 Stock

**Accede a:** `http://localhost:3000/stock`

#### Pruebas con `operador_a1`

| Acción | Resultado esperado |
|---|---|
| Abrir la pestaña | Ve solo productos de ALM-A (Almacén Norte) |
| Ver pestaña "Por cantidad" | P001, P002, P003, P004 |
| Verificar P003 (Bujías NGK) | Cantidad en **rojo** porque 3 < mínimo 10 |
| Ver pestaña "Serie única" | SN-2041 (disponible), SN-2042 (en_reparacion) |
| Buscar "filtro" en el buscador | Solo aparece P001 Filtro de aceite |
| Buscar "SN-2041" | Aparece el motor en la pestaña serie |
| Hacer clic en editar un producto | Se abre modal de edición |
| Cambiar cantidad a 50 y guardar | Se actualiza en la tabla |
| Cambiar cantidad a -5 y guardar | Error de validación (mínimo 0) |

#### Pruebas con `admin`

| Acción | Resultado esperado |
|---|---|
| Abrir Stock | Ve productos de **ambos** almacenes |
| Editar P003 en ALM-A, cambiar cantidad a 15 | La cifra deja de aparecer en rojo (15 > mínimo 10) |
| Cambiar status de SN-3002 a "disponible" | Se actualiza correctamente |
| Cambiar status a "texto_inventado" | Error 422 del servidor |

---

### 4.4 CRM

**Accede a:** `http://localhost:3000/crm`

#### Pruebas con `supervisor_a`

| Acción | Resultado esperado |
|---|---|
| Pestaña Notas | Ve sus propias notas |
| Crear nota: "Revisión de inventario completada el 02/06" | Aparece en la lista |
| Editar la nota | Se puede modificar el texto |
| Pestaña Historial | Muestra el log de notas y cambios |
| Pestaña Métricas | Ve sus propias métricas (notas creadas, actividad) |
| Intentar ver métricas de otro usuario via URL | Error 403 |

#### Pruebas con `admin`

| Acción | Resultado esperado |
|---|---|
| Abrir CRM | Ve sus notas por defecto |
| Pestaña Métricas → ver métricas globales | Resumen de actividad de todos los usuarios |

---

### 4.5 Notificaciones

**Accede a:** `http://localhost:3000/notifications`

#### Preparación: genera notificaciones

1. Entra como `supervisor_a` y edita un producto en Stock (cantidad)
2. El `admin` debería recibir una notificación de modificación de stock

#### Pruebas con `admin`

| Acción | Resultado esperado |
|---|---|
| Abrir Notificaciones | Ve las notificaciones no leídas primero |
| El badge de la campana (navbar) | Muestra el número de no leídas |
| Clic en "Marcar como leída" en una notificación | Desaparece del contador, pasa a sección "Leídas" |
| Clic en "Marcar todas como leídas" | El badge desaparece |

#### Pruebas de aislamiento

| Acción | Resultado esperado |
|---|---|
| Entrar como `operador_a1` y ver notificaciones | Solo ve **sus** notificaciones, no las del admin |
| Intentar marcar como leída una notificación de otro usuario (via API) | Error 403 |

---

### 4.6 Admin

**Accede a:** `http://localhost:3000/admin`

> Solo accesible para `admin`. Cualquier otro rol redirige a `/chat`.

#### Pestaña Usuarios

| Acción | Resultado esperado |
|---|---|
| Ver lista de usuarios | Muestra los 6 usuarios del sistema |
| Crear usuario nuevo con datos válidos | Usuario aparece en la lista |
| Crear usuario con contraseña débil ("1234") | Error de validación |
| Crear usuario con username que ya existe | Error 409 |
| Resetear contraseña de `operador_b1` a "NuevaPass1!" | OK |
| Verificar que `operador_b1` puede entrar con la nueva contraseña | Login exitoso |
| Desactivar un usuario | Ya no puede hacer login |
| Desbloquear un usuario bloqueado | Puede volver a iniciar sesión |

#### Pestaña Sync

| Acción | Resultado esperado |
|---|---|
| Ver estado de almacenes | ALM-A y ALM-B con estado online/offline y última sincronización |
| Pulsar "Disparar sync manual" | Intenta conectarse a los agentes (fallará si no están corriendo, pero no debe romper la UI) |
| Ver logs de sync | Lista de sincronizaciones anteriores con status |

---

## 5. Pruebas de acceso por rol

Esta tabla resume qué puede ver cada rol en la UI. Verifica cada combinación:

| Página | admin | gestor | supervisor | operador |
|---|---|---|---|---|
| /chat | ✅ | ✅ | ✅ | ✅ |
| /stock | ✅ Todos | ✅ Todos | ✅ Solo suyo | ✅ Solo suyo |
| /crm | ✅ | ✅ | ✅ | ✅ |
| /notifications | ✅ | ✅ | ✅ | ✅ |
| /admin | ✅ | ❌ → /chat | ❌ → /chat | ❌ → /chat |

---

## 6. Pruebas de dispositivos adicionales (teléfono / laptop)

### Pasos para conectarse desde otro dispositivo

1. Asegúrate de que el otro dispositivo está en la **misma red WiFi**
2. En tu laptop principal, ejecuta: `ip addr show | grep "inet " | grep -v 127`
3. Copia la IP (formato `192.168.x.x` o `10.x.x.x`)
4. Si la IP es distinta a la que hay en `.env` (`ALLOWED_ORIGIN`), cámbiala y reinicia el backend
5. En el otro dispositivo, abre el navegador en `http://TU_IP:3000`

### Casos a verificar en el dispositivo externo

| Caso | Resultado esperado |
|---|---|
| Login con `operador_b1` / `Oper123!` | Login funciona desde el teléfono |
| Enviar un mensaje al chatbot | Respuesta llega correctamente |
| Girar el teléfono (landscape) | La UI se adapta sin romper el layout |
| Scrollear el chat con muchos mensajes | Scroll fluido, input siempre visible |
| Abrir la misma sesión en laptop y teléfono simultáneamente | Cada sesión de chat es independiente |

---

## 7. Pruebas del agente almacén (Sync real)

El agente simula las laptops físicas de los almacenes que envían su stock al servidor central.

### Levantar los agentes en la misma laptop (para simular)

```bash
# Terminal 3 — Agente ALM-A (puerto 8001)
cd warehouse_agent
AGENT_TOKEN=token-alm-a STOCK_FILE=stock_a.json uvicorn agent:app --port 8001

# Terminal 4 — Agente ALM-B (puerto 8002)
AGENT_TOKEN=token-alm-b STOCK_FILE=stock_b.json uvicorn agent:app --port 8002
```

### Levantar el agente en otra laptop (red local)

1. Copia la carpeta `warehouse_agent/` a la otra laptop
2. En esa laptop: `pip install fastapi uvicorn`
3. Levanta el agente:
   ```bash
   AGENT_TOKEN=token-alm-a STOCK_FILE=stock_a.json uvicorn agent:app --host 0.0.0.0 --port 8001
   ```
4. En el servidor central, actualiza la DB con la IP de esa laptop:
   ```bash
   source .venv/bin/activate
   python -c "
   from backend.database import SessionLocal
   from backend import models
   db = SessionLocal()
   wh = db.query(models.Warehouse).filter_by(code='ALM-A').first()
   wh.agent_url = 'http://IP_DE_LA_LAPTOP:8001/stock'
   db.commit(); db.close()
   print('OK')
   "
   ```

### Pruebas de sync

| Acción | Resultado esperado |
|---|---|
| Con los agentes levantados, ir a Admin → Sync | Los almacenes aparecen como **online** |
| Disparar sync manual | Los datos de `stock_a.json` y `stock_b.json` actualizan el inventario |
| Modificar `stock_a.json` (cambiar una cantidad) y sincronizar | El stock en la DB se actualiza con el nuevo valor |
| Preguntar al chatbot después del sync | El chatbot ve los nuevos valores |
| Apagar un agente y sincronizar | Ese almacén aparece como **offline**, el otro sigue funcionando |
| Intentar sync sin agentes levantados | Error controlado en los logs, la UI no se rompe |

---

## 8. Pruebas de notificación por chatbot no resuelto

Este es un flujo importante: cuando el chatbot no puede responder, notifica al superior.

### Escenario

1. Entra como `operador_a1`
2. Pregunta algo que el chatbot no puede resolver:
   - `¿Cuál es el precio de venta del filtro de aceite?`
   - `¿Cuándo fue la última auditoría de inventario?`
   - `¿Quién es el proveedor de los motores eléctricos?`
3. El chatbot responde: "No tengo información disponible sobre eso en este momento."
4. Sal y entra como `supervisor_a`
5. Ve a Notificaciones

**Resultado esperado:** aparece una notificación de tipo "chat_unresolved" indicando que `operador_a1` hizo una pregunta que el chatbot no pudo responder.

---

## 9. Pruebas de dark mode

| Acción | Resultado esperado |
|---|---|
| Clic en el botón luna/sol de la navbar | Cambia entre modo claro y oscuro |
| Navegar a otra página con dark mode activo | El modo se mantiene |
| Cerrar y volver a abrir la pestaña | El modo persiste (guardado en localStorage) |
| En dispositivo externo, activar dark mode | Solo afecta ese dispositivo |

---

## 10. Checklist final antes de la demo

Marca cada punto antes de presentar:

### Sistema
- [ ] `./scripts/demo_reset.sh` ejecutado (DB limpia)
- [ ] Backend corriendo en puerto 8000
- [ ] Frontend corriendo en puerto 3000
- [ ] Accesible desde dispositivo externo (IP actualizada en `.env` si aplica)

### Chatbot — verificación rápida de roles
- [ ] `operador_a1`: pregunta sobre ALM-A → responde bien
- [ ] `operador_a1`: pregunta sobre ALM-B → no da info de otro almacén
- [ ] `gestor1`: pregunta cross-almacén → da info de ambos
- [ ] `admin`: resumen global → muestra todo

### UI
- [ ] Dark mode funciona
- [ ] Badge de notificaciones funciona
- [ ] Logout funciona y redirige al login
- [ ] El stock bajo aparece en rojo (P003 en ALM-A)
- [ ] El botón de admin no aparece en el navbar del operador

### Admin
- [ ] Crear usuario → login con ese usuario → funciona
- [ ] Desactivar usuario → login falla

### Desde dispositivo externo
- [ ] Login funciona
- [ ] Chat funciona
- [ ] No da errores de CORS

---

## 11. Qué hacer si algo falla

### El chatbot responde en inglés o da respuestas raras
El LLM (Groq/LLaMA) puede variar. Si consistentemente da malas respuestas, el system prompt se puede afinar en `scripts/update_prompts.py` y reaplicar con `python scripts/update_prompts.py`.

### "El servicio de IA no está disponible"
La API key de Groq puede tener rate limit o estar caída. Revisa en `.env` que `GROQ_API_KEY` es correcta. Puedes generar una nueva en `console.groq.com`.

### El chatbot da información del almacén contrario
Esto sería un bug de aislamiento. Verifica que el usuario tiene el `warehouse_id` correcto en la DB:
```bash
source .venv/bin/activate
python -c "
from backend.database import SessionLocal
from backend import models
db = SessionLocal()
for u in db.query(models.User).all():
    print(u.username, u.role.name, u.warehouse.code if u.warehouse else 'sin almacén')
db.close()
"
```

### Error de CORS al conectarse desde otro dispositivo
1. `ip addr show | grep inet` → copia la IP actual
2. Edita `.env`: `ALLOWED_ORIGIN=http://TU_IP:3000`
3. Reinicia el backend

### La cuenta `operador_b1` está bloqueada
```bash
source .venv/bin/activate
python -c "
import bcrypt
from backend.database import SessionLocal
from backend import models
db = SessionLocal()
u = db.query(models.User).filter_by(username='operador_b1').first()
u.is_active = True
u.is_locked = False
u.failed_attempts = 0
u.password_hash = bcrypt.hashpw(b'Oper123!', bcrypt.gensalt()).decode()
db.commit(); db.close()
print('Restaurado')
"
```

### Quiero volver al estado inicial completo
```bash
./scripts/demo_reset.sh
```
