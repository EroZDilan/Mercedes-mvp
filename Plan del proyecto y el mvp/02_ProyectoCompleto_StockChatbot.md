# Proyecto Completo — Sistema de Gestión de Stock con Chatbot IA
**Versión:** 3.0 | **Última actualización:** Junio 2026

---

## 1. Visión General

Sistema empresarial con servidor central que:
- Sincroniza stock de múltiples almacenes 2 veces al día desde el sistema nacional
- Permite consultas **y ejecución de acciones** en lenguaje natural mediante chatbot IA local
- El chatbot muestra resumen de la acción y espera confirmación antes de ejecutar
- Controla acceso por jerarquía de roles: cada usuario ve y hace solo lo de su nivel
- Transcribe audio a texto para interactuar con el chatbot por voz
- Integra con Spiga+ (DMS automotriz): lectura en MVP, automatización con Playwright a futuro
- CRM personal por usuario, notificaciones jerárquicas, histórico de acciones
- 100% local para inferencia LLM y datos; solo el módulo de sync usa internet

---

## 2. Arquitectura de Producción

```
                    [Internet — 2x/día, solo sync]
                              |
                    [Celery + Redis — sync robusta]
                              |
          ┌───────────────────┴──────────────────────┐
          |              SERVIDOR CENTRAL              |
          |                                            |
          |  ┌──────────┐      ┌───────────────────┐  |
          |  │  FastAPI  │      │    PostgreSQL 16   │  |
          |  │ (Backend) │←────→│  + pgvector ext.  │  |
          |  └─────┬─────┘      └───────────────────┘  |
          |        |                                    |
          |  ┌─────┴──────┐    ┌──────────────────┐    |
          |  │   Ollama   │    │  faster-whisper  │    |
          |  │ Qwen3 14B  │    │ (transcripción)  │    |
          |  │ (LLM local)│    └──────────────────┘    |
          |  └────────────┘                            |
          |        |                                   |
          |  ┌─────┴──────┐                            |
          |  │   Nginx    │  ← HTTPS, proxy reverso    |
          |  └────────────┘                            |
          └──────────────┬─────────────────────────────┘
                         | Red local (LAN/WiFi)
          ┌──────────────┼──────────────┐
          |              |              |
     [PC Oficina]  [Tablet Almacén]  [Móvil]
     Navegador       Navegador        Navegador
```

---

## 3. Stack Tecnológico de Producción

| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| LLM | **Ollama + Qwen3 14B** | 100% local, sin internet, gratis, open source |
| Transcripción audio | **faster-whisper** (medium) | Local, ~1.5 GB, sin internet, sin API keys |
| Base de datos | **PostgreSQL 16** | Robusto, concurrente, open source |
| Extensión BD | **pgvector** | Búsqueda semántica sobre documentos |
| ORM | **SQLAlchemy + Alembic** | Migraciones versionadas |
| Backend | **FastAPI (Python 3.11+)** | Alto rendimiento, async |
| Orquestación LLM | **LangChain** | Tool calling, streaming, memoria, RAG |
| Embeddings | **nomic-embed-text** (Ollama) | Búsqueda semántica local |
| Task queue | **Celery + Redis** | Jobs de sync robustos con reintentos |
| Frontend | **React + Tailwind CSS** | Responsive, PWA-ready, modo oscuro |
| Auth | **JWT + bcrypt + refresh tokens** | Stateless, multi-dispositivo |
| Proxy | **Nginx** | HTTPS, compresión, estáticos |
| Contenedores | **Docker + Docker Compose** | Despliegue reproducible |
| Monitoreo | **Grafana + Prometheus** | Métricas de sistema y LLM |

---

## 4. Roles y Jerarquía

```
ADMIN (nivel 1)
  └── GESTOR (nivel 2)
        └── SUPERVISOR (nivel 3)
              └── OPERADOR (nivel 4)
```

La jerarquía es dinámica: `hierarchy_level` en la tabla de roles. Añadir un nuevo rol = insertar una fila.

### Tabla de permisos completa

| Permiso | Admin | Gestor | Supervisor | Operador |
|---------|:-----:|:------:|:----------:|:--------:|
| Consultar stock propio almacén | ✅ | ✅ | ✅ | ✅ |
| Consultar stock todos los almacenes | ✅ | ✅ | ❌ | ❌ |
| Mover/transferir stock | ✅ | ✅ | ✅ | ✅ |
| Cambiar estado de producto | ✅ | ✅ | ✅ | ✅ |
| Crear producto nuevo | ✅ | ✅ | ✅ | ❌ |
| Editar producto existente | ✅ | ✅ | ✅ | ❌ |
| Eliminar producto | ✅ | ✅ | ❌ | ❌ |
| Gestionar usuarios | ✅ | ❌ | ❌ | ❌ |
| Resetear contraseñas | ✅ | ❌ | ❌ | ❌ |
| Forzar cierre de sesión | ✅ | ❌ | ❌ | ❌ |
| Ver historial completo de cambios | ✅ | ❌ | ❌ | ❌ |
| Ver CRM de subordinados | ✅ | ✅ | ✅ | ❌ |
| Exportar CRM de usuario | ✅ | ❌ | ❌ | ❌ |
| Iniciar sync manual | ✅ | ❌ | ❌ | ❌ |
| Ver estado online/offline almacenes | ✅ | ✅ | ❌ | ❌ |
| Ver logs del sistema | ✅ | ❌ | ❌ | ❌ |
| Recibir alertas stock bajo | ✅ | ✅ (solo su almacén) | ❌ | ❌ |
| Chatbot: ver stock otros almacenes | ✅ | ✅ | ❌ | ❌ |
| Chatbot: sin restricciones de respuesta | ✅ | ❌ | ❌ | ❌ |
| Configurar almacenes/sistema | Solo programador | ❌ | ❌ | ❌ |
| Dar internet al sistema | Solo programador | ❌ | ❌ | ❌ |

### Regla de notificación jerárquica

Toda acción ejecutada (no solo consultas) genera notificación al rol inmediato superior + admin siempre. Incluye: qué acción, quién, cuándo, sobre qué producto/usuario, resultado.

---

## 5. Chatbot IA — Arquitectura de Acciones

### Flujo de confirmación (obligatorio para toda acción de escritura)

```
Usuario escribe o dicta
        ↓
Whisper transcribe (si es audio)
        ↓
LLM interpreta intención
        ↓
Backend valida permisos del rol
        ↓
¿Es consulta? → Responde con streaming (token a token)
¿Es acción? →
        ↓
Backend consulta SQLite con datos reales
        ↓
LLM formatea resumen con datos reales:
  "Transferir 5 × Filtro de aceite
   De: Almacén Norte (quedarán 40 uds.)
   A: Almacén Sur (pasarán a tener 25 uds.)
   ¿Confirmas?"
        ↓
Backend genera action_token UUID (TTL 60s, un solo uso)
        ↓
Usuario confirma → Backend valida token → Ejecuta → action_log
Usuario cancela → Token invalidado → "Acción cancelada"
        ↓
Notificación automática al superior + admin
```

### Tool calling por rol

Cada rol tiene asignado un conjunto de tools LangChain. El LLM solo puede llamar las tools de su rol:

```python
TOOLS_BY_ROLE = {
    "operador":   [query_stock, transfer_stock, change_status],
    "supervisor": [query_stock, transfer_stock, change_status,
                   create_product, edit_product],
    "gestor":     [query_stock_all, transfer_stock, change_status,
                   create_product, edit_product, delete_product],
    "admin":      [query_stock_all, transfer_stock, change_status,
                   create_product, edit_product, delete_product,
                   create_user, edit_user, deactivate_user,
                   reset_password]
}
```

### Streaming

Respuestas enviadas token a token al frontend. El usuario ve el texto aparecer en tiempo real. Implementado con LangChain streaming callbacks + Server-Sent Events en FastAPI.

### Respuestas concisas

System prompt instruye: máximo 3 líneas para consultas, sin introducciones. Los resúmenes de confirmación de acción son más detallados pero estructurados.

---

## 6. Transcripción de Audio (Whisper)

### Producción
- **faster-whisper** con modelo `medium` (~1.5 GB, mejor precisión)
- Soporte multiidioma: español de base, inglés en fase 2
- Sin internet, sin API keys, corre en el servidor central
- Endpoint: `POST /audio/transcribe`

### Flujo
```
Usuario graba audio en frontend (Web Audio API)
        ↓
POST /audio/transcribe → faster-whisper → texto
        ↓
Frontend muestra texto para revisión del usuario
        ↓
Usuario confirma → texto va al chatbot como mensaje normal
```

---

## 7. Integración con Spiga+

### MVP — Lectura SQL Server (recomendada, sin riesgo)
Conexión de solo lectura a la BD SQL Server de Spiga+. Stock sincronizado desde ahí. El chatbot guía al usuario con instrucciones exactas de navegación en Spiga+ para ejecutar acciones. Nada escribe en el ERP del cliente.

### Producción futura — Playwright local
Automatización del navegador 100% local. El chatbot rellena formularios de Spiga+ directamente tras ejecutar la acción en el sistema propio. Open source, Python nativo. Riesgo mantenimiento: actualizaciones de UI de Spiga+ requieren reajuste del script.

### Descartado definitivamente — Claude in Chrome
Requiere internet + envía datos a servidores de Anthropic. Incompatible con arquitectura local del proyecto.

---

## 8. Hardware Recomendado para el Servidor Central

### Opción A — Sin GPU (económica)
Respuestas LLM: ~8-15 seg. Hasta 5 usuarios simultáneos.

| Componente | Especificación | Precio aprox. |
|-----------|---------------|---------------|
| CPU | AMD Ryzen 7 7700X u Intel i7-13700 | $250-300 USD |
| RAM | **64 GB DDR5** | $150-180 USD |
| Almacenamiento | SSD NVMe 1 TB | $80-100 USD |
| Placa madre | B650 / Z790 | $120-150 USD |
| Fuente | 650W 80+ Bronze | $60-80 USD |
| Gabinete | Torre mediana ventilada | $50-80 USD |
| **Total** | | **~$710-890 USD** |

Modelo LLM: **Qwen3 8B Q4_K_M** (~4.5 GB RAM)

### Opción B — Con GPU (recomendada)
Respuestas LLM: ~1-3 seg. Hasta 15-20 usuarios simultáneos.

| Componente | Especificación | Precio aprox. |
|-----------|---------------|---------------|
| CPU | AMD Ryzen 7 7700X | $250-300 USD |
| RAM | 32 GB DDR5 | $80-100 USD |
| **GPU** | **NVIDIA RTX 4060 Ti 16 GB** | $380-420 USD |
| Almacenamiento | SSD NVMe 1 TB | $80-100 USD |
| Placa madre | PCIe 4.0 x16 | $130-160 USD |
| Fuente | 750W 80+ Gold | $80-100 USD |
| Gabinete | Torre con espacio GPU | $60-90 USD |
| **Total** | | **~$1,060-1,270 USD** |

Modelo LLM: **Qwen3 14B Q4_K_M** (~8.5 GB VRAM)

### Opción C — Alto rendimiento
Respuestas LLM: <1 seg. 30-50 usuarios simultáneos.

| Componente | Especificación | Precio aprox. |
|-----------|---------------|---------------|
| CPU | AMD Ryzen 9 7950X | $550-600 USD |
| RAM | 128 GB DDR5 | $300-350 USD |
| **GPU** | **NVIDIA RTX 4090 24 GB** | $1,600-1,800 USD |
| Almacenamiento | SSD NVMe 2 TB | $150-180 USD |
| Placa madre | X670E | $250-300 USD |
| Fuente | 1000W 80+ Gold | $120-150 USD |
| Gabinete | Full tower | $100-150 USD |
| **Total** | | **~$3,070-3,530 USD** |

Modelo LLM: **Qwen3 32B Q4_K_M** (~19 GB VRAM)

---

## 9. Esquema de Base de Datos (PostgreSQL)

```sql
-- Roles (jerárquía dinámica)
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    hierarchy_level INTEGER NOT NULL,
    system_prompt TEXT NOT NULL,
    allowed_tools JSONB NOT NULL,        -- tools disponibles para este rol
    permissions JSONB NOT NULL
);

-- Usuarios
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role_id INTEGER REFERENCES roles(id),
    warehouse_id INTEGER REFERENCES warehouses(id),
    is_active BOOLEAN DEFAULT true,
    is_locked BOOLEAN DEFAULT false,
    failed_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Almacenes
CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    agent_url TEXT,
    agent_token TEXT,
    is_online BOOLEAN DEFAULT false,
    last_seen TIMESTAMP
);

-- Stock cantidad
CREATE TABLE stock (
    id SERIAL PRIMARY KEY,
    warehouse_id INTEGER REFERENCES warehouses(id),
    product_code VARCHAR(50) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    quantity INTEGER NOT NULL DEFAULT 0,
    min_quantity INTEGER DEFAULT 0,
    unit VARCHAR(20) DEFAULT 'unidad',
    location_in_warehouse TEXT,
    status VARCHAR(30) DEFAULT 'disponible',
    last_synced TIMESTAMP,
    UNIQUE(warehouse_id, product_code)
);

-- Stock serie única
CREATE TABLE stock_serial (
    id SERIAL PRIMARY KEY,
    warehouse_id INTEGER REFERENCES warehouses(id),
    product_code VARCHAR(50) NOT NULL,
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    location_in_warehouse TEXT,
    status VARCHAR(30) DEFAULT 'disponible',
    last_synced TIMESTAMP
);

-- Historial de cambios (append-only)
CREATE TABLE stock_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER,
    product_type VARCHAR(20),
    warehouse_id INTEGER REFERENCES warehouses(id),
    changed_by INTEGER REFERENCES users(id),
    field_changed VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT NOW()
);

-- Log de acciones del chatbot (append-only)
CREATE TABLE action_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id INTEGER,
    action_detail JSONB NOT NULL,
    confirmed_at TIMESTAMP,
    executed_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'success'
);

-- Tokens de confirmación (UUID, un solo uso, TTL 60s)
CREATE TABLE action_tokens (
    id SERIAL PRIMARY KEY,
    token VARCHAR(36) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id),
    action_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    used BOOLEAN DEFAULT false
);

-- Sesiones activas
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    jti VARCHAR(36) UNIQUE NOT NULL,
    device_info TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    is_revoked BOOLEAN DEFAULT false
);

-- Historial de chat (CRM)
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id UUID NOT NULL,
    question TEXT NOT NULL,
    response TEXT NOT NULL,
    action_executed JSONB,               -- null si fue consulta
    input_type VARCHAR(10) DEFAULT 'text', -- 'text' | 'audio'
    timestamp TIMESTAMP DEFAULT NOW(),
    response_time_ms INTEGER
);

-- Notas CRM manuales
CREATE TABLE crm_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    content TEXT NOT NULL,
    related_to TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Notificaciones
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    recipient_user_id INTEGER REFERENCES users(id),
    type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    related_user_id INTEGER,
    action_log_id INTEGER REFERENCES action_log(id),
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Log de auditoría (append-only)
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    detail JSONB,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Documentos para RAG
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    role_access_levels INTEGER[],
    embedding vector(768),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- Log de sincronizaciones
CREATE TABLE sync_log (
    id SERIAL PRIMARY KEY,
    warehouse_id INTEGER REFERENCES warehouses(id),
    triggered_by VARCHAR(20) DEFAULT 'scheduler',
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status VARCHAR(20),
    records_updated INTEGER DEFAULT 0,
    error_message TEXT
);
```

---

## 10. Seguridad Completa

### Chatbot con acciones — brechas específicas

| Brecha | Mitigación |
|--------|-----------|
| Acción fuera del rol via chat | Tools asignadas dinámicamente por rol; el LLM no puede llamar tools que no tiene |
| Prompt injection para escalar privilegios | System prompt con instrucción explícita + tools limitadas por rol en el backend |
| Acción ejecutada sin confirmación | action_token obligatorio en endpoint de ejecución; sin token = 400 |
| Replay de confirmación | action_token UUID de un solo uso, TTL 60 segundos |
| LLM alucina datos en el resumen | Resumen construido con datos reales de BD, el LLM solo formatea el texto |
| Acción masiva destructiva | Límite de 1 ítem por acción; bulk solo admin con confirmación explícita del recuento |

### Autenticación y sesiones

| Brecha | Mitigación |
|--------|-----------|
| Fuerza bruta en login | Bloqueo tras 5 intentos, solo admin desbloquea |
| Tokens interceptados | HTTPS obligatorio (TLS 1.2+) |
| Sesiones zombi | Expiración 1h + invalidación forzada por admin |
| Contraseñas débiles | Política obligatoria validada en backend |
| Contraseñas en texto plano | bcrypt con salt |
| Replay attacks | jti único por token, lista negra en Redis |

### API y datos

| Brecha | Mitigación |
|--------|-----------|
| SQL Injection | SQLAlchemy queries parametrizadas |
| CORS abierto | Solo origen del frontend |
| Rate limiting | Nginx + FastAPI en endpoints críticos |
| Agentes sin autenticación | Token secreto en header de cada pull |
| Audit log manipulable | Append-only, sin endpoint de borrado |
| Disco sin cifrar | LUKS en Linux recomendado para el servidor |
| Backups sin cifrar | GPG antes de almacenar |

---

## 11. Fases de Desarrollo del Proyecto Completo

### MVP (completado en su mayoría — ver documento MVP)

### Producción Base (6-8 semanas)
- Migrar SQLite → PostgreSQL con Alembic
- Ollama + Qwen3 14B (reemplaza Groq)
- Celery + Redis para sync robusta
- Integración con sistema nacional (formato a definir)
- HTTPS con Nginx
- Docker Compose completo
- Backups automáticos cifrados

### Características Avanzadas (4-6 semanas)
- RAG sobre documentos (pgvector + nomic-embed-text)
- Fichas técnicas e imágenes por producto
- CRM completo con exportación PDF
- Reportes automáticos semanales
- Monitoreo con Grafana + Prometheus
- PWA móvil instalable
- 2FA (TOTP) para admin
- Soporte inglés en el chatbot
- Playwright para automatización de Spiga+ (integración real)

---

## 12. Recomendaciones Generales

### Red
- IP estática en red local para el servidor
- Ethernet para el servidor, WiFi para clientes
- Para acceso externo futuro: VPN WireGuard (gratuita, simple)
- Separar red de sync (internet) de la red interna

### LLM
- Actualizar Qwen3 cada 6-12 meses (mejoras significativas por versión)
- Siempre usar cuantización Q4_K_M
- Con más presupuesto de GPU, solo cambia la variable de entorno del modelo

### Lo que configura solo el programador
- URLs y credenciales del sistema nacional
- Configuración de red e internet del servidor
- Variables de entorno críticas (.env)
- Actualización del modelo LLM
- Migraciones de BD (Alembic)
- Scripts de Playwright para Spiga+
