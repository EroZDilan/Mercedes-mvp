# InvenTree — Guía Completa para Demo MVP

**Versión:** 1.0 | **Última actualización:** Junio 2026

---

## 1. Qué es InvenTree en este proyecto

InvenTree cumple **dos roles** en el MVP:

**Rol 1 — Simulador offline de Spiga+**
Para la demo con el cliente, InvenTree simula los flujos de almacén de Spiga+: traspasos entre ubicaciones, cambios de estado, gestión de series únicas, stock mínimo. El chatbot aprende la estructura de navegación de InvenTree y guía al usuario exactamente como lo haría con Spiga+ real. Cuando llegue la integración real, solo se adapta el JSON de navegación.

**Rol 2 — Fuente de datos real para el MVP**
En lugar de los agentes JSON en las laptops, InvenTree puede actuar como el sistema de almacén real del que el servidor central sincroniza stock via su API REST. Esto hace la demo más realista y elimina la necesidad de mantener JSONs estáticos.

---

## 2. Instalación con Docker

### Requisitos previos

- Docker Desktop instalado en Windows (https://www.docker.com/products/docker-desktop)
- Al menos 4 GB RAM libres para InvenTree
- Puerto 8080 libre en la laptop

### docker-compose.yml para InvenTree

Crea una carpeta `inventree-demo/` y dentro el archivo `docker-compose.yml`:

```yaml
version: "3.8"

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
      INVENTREE_DEBUG: False
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
```

### Comandos esenciales

```bash
# Levantar InvenTree (primera vez o después de parar)
cd inventree-demo
docker compose up -d

# Ver logs si algo falla
docker compose logs -f inventree-server

# Parar InvenTree
docker compose down

# Parar y borrar TODOS los datos (reset completo)
docker compose down -v

# Reiniciar solo el servidor
docker compose restart inventree-server

# Ver estado de los contenedores
docker compose ps
```

### Acceder desde el navegador

Una vez levantado (espera ~60 segundos la primera vez):

```
URL:      http://localhost:8080
Usuario:  admin
Password: admin1234
```

Desde otros dispositivos en la red WiFi:

```
URL: http://[IP_DE_TU_LAPTOP]:8080
```

Para saber tu IP en Windows: `ipconfig` en la terminal → busca "Dirección IPv4"

### Arranque automático con el sistema

En Docker Desktop → Settings → General → activa **"Start Docker Desktop when you log in"**. Con `restart: unless-stopped` en el compose, InvenTree arranca solo cuando Docker arranca.

---

## 3. Configuración inicial para simular Spiga+

### 3.1 Crear ubicaciones (almacenes)

En InvenTree las ubicaciones son jerárquicas. Crea esta estructura:

```
Almacén Norte (ALM-A)
  ├── Zona A — Repuestos generales
  ├── Zona B — Lubricantes y filtros
  └── Zona C — Herramientas y equipos

Almacén Sur (ALM-B)
  ├── Zona A — Repuestos generales
  ├── Zona B — Lubricantes y filtros
  └── Zona C — Herramientas y equipos
```

**Cómo hacerlo:**

1. Menú izquierdo → **Stock** → **Ubicaciones**
2. Clic en **Nueva Ubicación**
3. Nombre: `Almacén Norte`, código: `ALM-A`, descripción: `Almacén principal norte`
4. Guardar → dentro de esa ubicación, crear las zonas como sub-ubicaciones

### 3.2 Crear categorías de productos

1. Menú izquierdo → **Piezas** → **Categorías**
2. Crear estas categorías:

| Categoría           | Descripción                            |
| ------------------- | -------------------------------------- |
| Repuestos mecánicos | Filtros, correas, pastillas de freno   |
| Lubricantes         | Aceites, grasas, líquidos              |
| Herramientas        | Equipos y herramientas de taller       |
| Electricidad        | Componentes eléctricos y electrónicos  |
| Carrocería          | Piezas de carrocería y pintura         |
| Serie única         | Equipos con número de serie individual |

### 3.3 Crear productos de prueba

**Productos por cantidad (mínimo 8-10 para la demo):**

| Nombre                        | Categoría           | Stock inicial | Stock mínimo | Ubicación      |
| ----------------------------- | ------------------- | :-----------: | :----------: | -------------- |
| Filtro de aceite              | Repuestos mecánicos |      45       |      10      | ALM-A / Zona B |
| Filtro de aire                | Repuestos mecánicos |      30       |      8       | ALM-A / Zona B |
| Aceite motor 5W-30 (1L)       | Lubricantes         |      120      |      20      | ALM-A / Zona B |
| Pastillas de freno delanteras | Repuestos mecánicos |      18       |      5       | ALM-A / Zona A |
| Correa de distribución        | Repuestos mecánicos |      12       |      3       | ALM-B / Zona A |
| Líquido de frenos DOT4        | Lubricantes         |      55       |      10      | ALM-B / Zona B |
| Bujías (pack 4)               | Electricidad        |      25       |      6       | ALM-B / Zona A |
| Lámpara H7                    | Electricidad        |      40       |      8       | ALM-A / Zona A |
| Llave de impacto              | Herramientas        |       3       |      1       | ALM-A / Zona C |
| Gato hidráulico 2T            | Herramientas        |       2       |      1       | ALM-B / Zona C |

**Cómo añadir stock a un producto:**

1. Abre el producto → pestaña **Stock**
2. Clic en **Añadir Stock**
3. Introduce cantidad, selecciona ubicación
4. Guardar

**Productos de serie única (mínimo 3-4):**

| Nombre               | Número de serie | Estado        | Ubicación      |
| -------------------- | --------------- | ------------- | -------------- |
| Motor eléctrico 5HP  | SN-2041         | disponible    | ALM-A / Zona C |
| Compresor industrial | SN-1887         | en_reparacion | ALM-B / Zona C |
| Elevador hidráulico  | SN-3302         | disponible    | ALM-B / Zona C |
| Soldadora MIG        | SN-0994         | reservado     | ALM-A / Zona C |

Para productos de serie única en InvenTree:

1. Crear la pieza normalmente
2. En la pestaña **Stock** → **Añadir Stock** → cantidad 1
3. En el campo **Número de serie** → introducir el número
4. InvenTree trata cada unidad serializada como un ítem individual

### 3.4 Crear usuarios con roles equivalentes

1. Menú superior derecho → **Administración** → **Usuarios**
2. Crear estos usuarios de prueba:

| Usuario      | Contraseña | Rol InvenTree              | Equivalente en tu sistema |
| ------------ | ---------- | -------------------------- | ------------------------- |
| admin_demo   | Admin1234! | Superusuario               | Admin                     |
| gestor_norte | Gestor123! | Staff                      | Gestor                    |
| supervisor_a | Super123!  | Staff (permisos limitados) | Supervisor                |
| operador_a1  | Oper123!   | Solo lectura               | Operador                  |

### 3.5 Configurar stock mínimo

InvenTree llama a esto **"Minimum Stock"** en cada pieza:

1. Abrir producto → pestaña **Detalles**
2. Campo **Minimum Stock** → introducir el valor mínimo
3. InvenTree marcará visualmente los productos por debajo del mínimo

---

## 4. Flujos documentados para el chatbot

Este es el JSON de navegación que se carga en el system prompt del chatbot. Define cómo guiar al usuario paso a paso en InvenTree (y por analogía en Spiga+).

```json
{
  "transferencia_stock": {
    "descripcion": "Mover unidades de un almacén/ubicación a otro",
    "ruta_ui": "Stock → Ítems de Stock → seleccionar ítem → Transferir",
    "pasos": [
      "Ir a Stock en el menú lateral",
      "Buscar el producto por nombre o código",
      "Hacer clic en el ítem de stock de la ubicación origen",
      "Clic en el botón 'Transferir' (icono de flechas)",
      "Seleccionar la ubicación destino",
      "Introducir la cantidad a transferir",
      "Añadir nota opcional",
      "Confirmar con el botón 'Enviar'"
    ],
    "campos": {
      "ubicacion_destino": "obligatorio",
      "cantidad": "obligatorio — no puede superar el stock disponible",
      "nota": "opcional — recomendado para auditoría"
    },
    "resultado": "El stock aparece en la nueva ubicación. El movimiento queda registrado en el historial."
  },

  "ajuste_stock": {
    "descripcion": "Modificar la cantidad de un producto (entrada o salida manual)",
    "ruta_ui": "Stock → Ítems de Stock → seleccionar ítem → Contar / Añadir / Retirar",
    "pasos": [
      "Ir a Stock → Ítems de Stock",
      "Buscar el producto",
      "Clic en el ítem",
      "Elegir la acción: 'Añadir Stock' (entrada) o 'Retirar Stock' (salida) o 'Contar Stock' (inventario)",
      "Introducir la cantidad",
      "Añadir nota del motivo",
      "Confirmar"
    ],
    "campos": {
      "cantidad": "obligatorio",
      "motivo": "opcional pero recomendado"
    }
  },

  "crear_producto_cantidad": {
    "descripcion": "Crear un nuevo producto que se gestiona por cantidad",
    "ruta_ui": "Piezas → Nueva Pieza",
    "pasos": [
      "Ir a Piezas en el menú lateral",
      "Clic en el botón verde '+ Nueva Pieza'",
      "Introducir el nombre del producto",
      "Seleccionar la categoría correspondiente",
      "Añadir descripción (opcional pero recomendado)",
      "En el campo 'Minimum Stock' introducir el mínimo deseado",
      "Desactivar 'Serializable' (es producto por cantidad)",
      "Guardar con el botón 'Guardar'",
      "Ir a la pestaña 'Stock' del producto → 'Añadir Stock'",
      "Introducir cantidad inicial y seleccionar ubicación"
    ]
  },

  "crear_producto_serie": {
    "descripcion": "Crear un producto de serie única (un ítem = un número de serie)",
    "ruta_ui": "Piezas → Nueva Pieza (con Serializable activado)",
    "pasos": [
      "Ir a Piezas → Nueva Pieza",
      "Introducir nombre y categoría",
      "Activar la casilla 'Serializable'",
      "Guardar",
      "Ir a pestaña 'Stock' → 'Añadir Stock'",
      "Cantidad: 1",
      "En el campo 'Números de serie' introducir el número (ej: SN-2041)",
      "Seleccionar ubicación",
      "Confirmar"
    ]
  },

  "editar_producto": {
    "descripcion": "Modificar datos de un producto existente",
    "ruta_ui": "Piezas → buscar producto → Editar",
    "pasos": [
      "Ir a Piezas",
      "Buscar el producto por nombre o código",
      "Clic en el producto",
      "Clic en el botón 'Editar' (icono lápiz)",
      "Modificar los campos necesarios",
      "Guardar"
    ],
    "campos_editables": [
      "nombre",
      "descripción",
      "categoría",
      "stock_mínimo",
      "notas"
    ]
  },

  "cambiar_estado_item": {
    "descripcion": "Marcar un ítem como en reparación, reservado, etc.",
    "ruta_ui": "Stock → Ítems de Stock → seleccionar ítem → Estado",
    "pasos": [
      "Ir a Stock → Ítems de Stock",
      "Localizar el ítem (buscar por número de serie o producto)",
      "Clic en el ítem",
      "Clic en 'Editar'",
      "Cambiar el campo 'Estado' al valor deseado",
      "Guardar"
    ],
    "estados_disponibles": {
      "OK": "Disponible y en buen estado",
      "Attention": "Requiere atención o revisión",
      "Damaged": "Dañado",
      "Destroyed": "Dado de baja",
      "Rejected": "Rechazado/No apto"
    },
    "nota": "InvenTree usa sus propios nombres de estado. El chatbot los mapea a los estados del sistema interno."
  },

  "consultar_stock_ubicacion": {
    "descripcion": "Ver todo el stock de una ubicación o almacén",
    "ruta_ui": "Stock → Ubicaciones → seleccionar ubicación",
    "pasos": [
      "Ir a Stock → Ubicaciones",
      "Seleccionar el almacén o zona deseada",
      "Ver la tabla de ítems con cantidades y estados"
    ]
  },

  "ver_historial_movimientos": {
    "descripcion": "Consultar el historial de movimientos de un producto",
    "ruta_ui": "Stock → Ítems de Stock → seleccionar ítem → Historial",
    "pasos": [
      "Localizar el ítem de stock",
      "Clic en el ítem",
      "Ir a la pestaña 'Historial' o 'Seguimiento'",
      "Ver todos los movimientos con fecha, usuario y cantidad"
    ]
  }
}
```

### Mapeo de estados InvenTree → Sistema interno

| Estado InvenTree        | Estado sistema interno |
| ----------------------- | ---------------------- |
| OK                      | disponible             |
| Attention               | en_reparacion          |
| Damaged                 | en_reparacion          |
| Destroyed               | dado_de_baja           |
| Rejected                | dado_de_baja           |
| (ítem asignado a orden) | reservado              |

---

## 5. Conectar el chatbot a InvenTree via API REST

InvenTree expone una API REST completa. El backend FastAPI puede usarla para sincronizar stock en tiempo real, reemplazando los agentes JSON de las laptops.

### Obtener token de API

```bash
# Obtener token (una sola vez, guardarlo en .env)
curl -X POST http://localhost:8080/api/user/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin_demo", "password": "Admin1234!"}'

# Respuesta:
# {"token": "abc123xyz..."}
```

Guardar en `.env`:

```env
INVENTREE_API_URL=http://localhost:8080/api/
INVENTREE_API_TOKEN=abc123xyz...
```

### Endpoints útiles para el MVP

```python
import httpx

HEADERS = {
    "Authorization": f"Token {INVENTREE_API_TOKEN}",
    "Content-Type": "application/json"
}
BASE = "http://localhost:8080/api/"

# ─── CONSULTAS ───────────────────────────────────────────────

# Listar todo el stock
GET /stock/item/

# Stock filtrado por ubicación (almacén)
GET /stock/item/?location=2          # 2 = ID de la ubicación

# Stock de un producto específico
GET /stock/item/?part=5              # 5 = ID del producto

# Buscar producto por nombre
GET /part/?search=filtro+de+aceite

# Ver ubicaciones (almacenes)
GET /stock/location/

# Ver historial de movimientos de un ítem
GET /stock/tracking/?item=12         # 12 = ID del ítem de stock

# ─── ACCIONES ────────────────────────────────────────────────

# Transferir stock entre ubicaciones
POST /stock/transfer/
{
  "items": [{"pk": 12, "quantity": 5}],
  "location": 3,                     # ID de la ubicación destino
  "notes": "Transferencia solicitada por chatbot"
}

# Añadir stock (entrada)
POST /stock/add/
{
  "items": [{"pk": 12, "quantity": 10, "notes": "Reposición"}]
}

# Retirar stock (salida)
POST /stock/remove/
{
  "items": [{"pk": 12, "quantity": 3, "notes": "Consumo taller"}]
}

# Cambiar estado de un ítem
PATCH /stock/item/12/
{
  "status": 50                       # 10=OK, 50=Attention, 55=Damaged, 60=Destroyed
}

# Crear producto nuevo
POST /part/
{
  "name": "Filtro de combustible",
  "category": 1,
  "description": "Filtro de combustible universal",
  "minimum_stock": 5,
  "trackable": false                 # true = serie única
}

# Añadir stock inicial a un producto nuevo
POST /stock/item/
{
  "part": 15,                        # ID del producto recién creado
  "quantity": 20,
  "location": 2,
  "notes": "Stock inicial"
}
```

### Cliente Python para el backend FastAPI

```python
# services/inventree_service.py
import httpx
from config import settings

class InvenTreeService:
    def __init__(self):
        self.base_url = settings.INVENTREE_API_URL
        self.headers = {
            "Authorization": f"Token {settings.INVENTREE_API_TOKEN}",
            "Content-Type": "application/json"
        }

    async def get_stock_by_location(self, location_id: int) -> list:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}stock/item/",
                headers=self.headers,
                params={"location": location_id, "in_stock": True}
            )
            return r.json()["results"]

    async def transfer_stock(self, item_id: int, quantity: int,
                              destination_id: int, notes: str = "") -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}stock/transfer/",
                headers=self.headers,
                json={
                    "items": [{"pk": item_id, "quantity": quantity}],
                    "location": destination_id,
                    "notes": notes
                }
            )
            return r.json()

    async def search_product(self, name: str) -> list:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}part/",
                headers=self.headers,
                params={"search": name, "active": True}
            )
            return r.json()["results"]

    async def get_low_stock(self) -> list:
        """Productos por debajo del stock mínimo"""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}part/",
                headers=self.headers,
                params={"low_stock": True}
            )
            return r.json()["results"]

    async def create_product(self, name: str, category_id: int,
                              description: str, min_stock: int,
                              serializable: bool = False) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}part/",
                headers=self.headers,
                json={
                    "name": name,
                    "category": category_id,
                    "description": description,
                    "minimum_stock": min_stock,
                    "trackable": serializable,
                    "active": True
                }
            )
            return r.json()
```

### Integrar InvenTree en la sync del servidor

En lugar de (o además de) los agentes JSON de las laptops, añadir InvenTree como fuente de sync:

```python
# sync_service.py — añadir al job existente
async def sync_inventree():
    """Sincroniza stock desde InvenTree a SQLite local"""
    service = InvenTreeService()

    for warehouse in WAREHOUSES:
        items = await service.get_stock_by_location(warehouse["inventree_location_id"])
        for item in items:
            # actualizar SQLite con los datos de InvenTree
            db.upsert_stock(
                warehouse_id=warehouse["id"],
                product_code=str(item["part"]),
                product_name=item["part_detail"]["name"],
                quantity=item["quantity"],
                location=item["location_detail"]["name"],
                status=map_status(item["status"])
            )
```

---

## 6. Script de población automática de datos

Ejecutar una sola vez para cargar todos los datos de prueba sin hacerlo manualmente:

```python
# scripts/populate_inventree.py
import httpx
import time

BASE = "http://localhost:8080/api/"
HEADERS = {
    "Authorization": "Token TU_TOKEN_AQUI",
    "Content-Type": "application/json"
}

def post(endpoint, data):
    r = httpx.post(f"{BASE}{endpoint}", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()

def get(endpoint, params=None):
    r = httpx.get(f"{BASE}{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

# ── 1. Crear categorías ──────────────────────────────────────
print("Creando categorías...")
categorias = [
    {"name": "Repuestos mecánicos", "description": "Filtros, correas, frenos"},
    {"name": "Lubricantes", "description": "Aceites, grasas, líquidos"},
    {"name": "Herramientas", "description": "Equipos de taller"},
    {"name": "Electricidad", "description": "Componentes eléctricos"},
    {"name": "Serie única", "description": "Equipos serializados"},
]
cat_ids = {}
for cat in categorias:
    result = post("part/category/", cat)
    cat_ids[cat["name"]] = result["pk"]
    print(f"  ✓ {cat['name']} (ID: {result['pk']})")

# ── 2. Crear ubicaciones ─────────────────────────────────────
print("\nCreando ubicaciones...")
alm_a = post("stock/location/", {
    "name": "Almacén Norte",
    "description": "ALM-A — Almacén principal norte"
})
alm_b = post("stock/location/", {
    "name": "Almacén Sur",
    "description": "ALM-B — Almacén secundario sur"
})

zonas = {}
for alm_id, alm_name in [(alm_a["pk"], "Norte"), (alm_b["pk"], "Sur")]:
    for zona in ["Zona A - Repuestos", "Zona B - Lubricantes", "Zona C - Herramientas"]:
        z = post("stock/location/", {
            "name": zona,
            "parent": alm_id,
            "description": f"{zona} del Almacén {alm_name}"
        })
        zonas[f"{alm_name}_{zona}"] = z["pk"]
        print(f"  ✓ Almacén {alm_name} / {zona} (ID: {z['pk']})")

# ── 3. Crear productos por cantidad ──────────────────────────
print("\nCreando productos por cantidad...")
productos = [
    {"name": "Filtro de aceite", "cat": "Repuestos mecánicos",
     "min": 10, "qty": 45, "loc": "Norte_Zona B - Lubricantes"},
    {"name": "Filtro de aire", "cat": "Repuestos mecánicos",
     "min": 8, "qty": 30, "loc": "Norte_Zona B - Lubricantes"},
    {"name": "Aceite motor 5W-30 (1L)", "cat": "Lubricantes",
     "min": 20, "qty": 120, "loc": "Norte_Zona B - Lubricantes"},
    {"name": "Pastillas de freno delanteras", "cat": "Repuestos mecánicos",
     "min": 5, "qty": 18, "loc": "Norte_Zona A - Repuestos"},
    {"name": "Correa de distribución", "cat": "Repuestos mecánicos",
     "min": 3, "qty": 12, "loc": "Sur_Zona A - Repuestos"},
    {"name": "Líquido de frenos DOT4", "cat": "Lubricantes",
     "min": 10, "qty": 55, "loc": "Sur_Zona B - Lubricantes"},
    {"name": "Bujías (pack 4)", "cat": "Electricidad",
     "min": 6, "qty": 25, "loc": "Sur_Zona A - Repuestos"},
    {"name": "Lámpara H7", "cat": "Electricidad",
     "min": 8, "qty": 40, "loc": "Norte_Zona A - Repuestos"},
    {"name": "Llave de impacto", "cat": "Herramientas",
     "min": 1, "qty": 3, "loc": "Norte_Zona C - Herramientas"},
    {"name": "Gato hidráulico 2T", "cat": "Herramientas",
     "min": 1, "qty": 2, "loc": "Sur_Zona C - Herramientas"},
]

for p in productos:
    part = post("part/", {
        "name": p["name"],
        "category": cat_ids[p["cat"]],
        "minimum_stock": p["min"],
        "trackable": False,
        "active": True
    })
    post("stock/item/", {
        "part": part["pk"],
        "quantity": p["qty"],
        "location": zonas[p["loc"]]
    })
    print(f"  ✓ {p['name']} — {p['qty']} uds.")
    time.sleep(0.3)  # evitar rate limiting

# ── 4. Crear productos de serie única ────────────────────────
print("\nCreando productos de serie única...")
series = [
    {"name": "Motor eléctrico 5HP", "sn": "SN-2041",
     "status": 10, "loc": "Norte_Zona C - Herramientas"},
    {"name": "Compresor industrial", "sn": "SN-1887",
     "status": 50, "loc": "Sur_Zona C - Herramientas"},
    {"name": "Elevador hidráulico", "sn": "SN-3302",
     "status": 10, "loc": "Sur_Zona C - Herramientas"},
    {"name": "Soldadora MIG", "sn": "SN-0994",
     "status": 10, "loc": "Norte_Zona C - Herramientas"},
]

for s in series:
    part = post("part/", {
        "name": s["name"],
        "category": cat_ids["Serie única"],
        "trackable": True,
        "active": True
    })
    post("stock/item/", {
        "part": part["pk"],
        "quantity": 1,
        "location": zonas[s["loc"]],
        "serial": s["sn"],
        "status": s["status"]
    })
    print(f"  ✓ {s['name']} — Serie: {s['sn']}")
    time.sleep(0.3)

print("\n✅ Datos de prueba cargados correctamente.")
print(f"   Categorías: {len(cat_ids)}")
print(f"   Productos cantidad: {len(productos)}")
print(f"   Productos serie única: {len(series)}")
print(f"\nAccede a InvenTree en: http://localhost:8080")
```

**Cómo ejecutar el script:**

```bash
# Instalar dependencia
pip install httpx

# Obtener tu token primero (ver sección 5)
# Editar el script y reemplazar "TU_TOKEN_AQUI" con tu token real

# Ejecutar
python scripts/populate_inventree.py
```

---

## 7. Procedimiento para la demo offline

### Checklist pre-demo (hacer en casa con internet)

```
□ Docker Desktop instalado y funcionando
□ Imagen de InvenTree descargada: docker pull inventree/inventree:stable
□ docker compose up -d ejecutado al menos una vez (crea la BD)
□ Script populate_inventree.py ejecutado (datos de prueba cargados)
□ Verificar acceso en http://localhost:8080 con admin/admin1234
□ Token de API obtenido y guardado en .env
□ Backend FastAPI conectado a InvenTree (probar sync manual)
□ Chatbot probado con preguntas de stock: responde con datos de InvenTree
□ Probar flujo completo: audio → transcripción → consulta → acción → confirmación
□ docker compose down (apagar limpiamente antes de ir)
□ Verificar que Docker Desktop arranca con Windows
```

### El día de la demo (sin internet)

```bash
# 1. Encender la laptop → Docker Desktop arranca solo

# 2. Verificar que InvenTree está corriendo
docker compose ps
# Deben aparecer: inventree_db ✓  inventree_server ✓  inventree_worker ✓

# 3. Si no arrancó automáticamente
cd inventree-demo
docker compose up -d

# 4. Esperar ~30 segundos y verificar en el navegador
# http://localhost:8080 → debe cargar el login

# 5. Levantar el backend del chatbot
cd stock-chatbot-mvp/backend
uvicorn main:app --host 0.0.0.0 --port 8000

# 6. Levantar el frontend
cd ../frontend
npm run dev -- --host

# 7. Verificar acceso desde otro dispositivo (móvil del cliente):
# http://[TU_IP]:3000
```

### Orden de arranque recomendado

```
1. Docker Desktop (automático)
2. InvenTree (automático via Docker)
3. Backend FastAPI (manual o script)
4. Frontend React (manual o script)
5. Agentes de laptop-almacén si los usas (opcional en demo con InvenTree)
```

### Script de arranque rápido para la demo

Crea `demo_start.bat` en el escritorio:

```batch
@echo off
echo Iniciando sistema de demo...

echo [1/3] Verificando InvenTree...
docker compose -f C:\inventree-demo\docker-compose.yml up -d

echo [2/3] Iniciando backend...
start cmd /k "cd C:\stock-chatbot-mvp\backend && uvicorn main:app --host 0.0.0.0 --port 8000"

echo [3/3] Iniciando frontend...
start cmd /k "cd C:\stock-chatbot-mvp\frontend && npm run dev -- --host"

echo.
echo Sistema iniciado. Espera 30 segundos y abre:
echo   InvenTree:  http://localhost:8080
echo   Chatbot:    http://localhost:3000
echo.
pause
```

### Qué hacer si algo falla durante la demo

| Problema                  | Solución rápida                                                      |
| ------------------------- | -------------------------------------------------------------------- |
| InvenTree no carga        | `docker compose restart inventree-server` → esperar 30s              |
| Backend da error 500      | Revisar terminal del backend, probable error de conexión a InvenTree |
| Chatbot no responde       | Verificar que Ollama/Groq está activo: `ollama list`                 |
| Frontend no carga         | `npm run dev -- --host` de nuevo en la carpeta frontend              |
| No hay datos en InvenTree | Ejecutar `python scripts/populate_inventree.py` de nuevo             |
| No hay IP del servidor    | `ipconfig` en terminal → buscar "Dirección IPv4"                     |

---

## 8. Limitaciones conocidas de InvenTree vs Spiga+

Es importante conocerlas para manejarlas bien si el cliente pregunta durante la demo.

| Característica                   |   InvenTree   |     Spiga+      |
| -------------------------------- | :-----------: | :-------------: |
| Gestión de stock y almacenes     |  ✅ Completo  |   ✅ Completo   |
| Productos por cantidad           |      ✅       |       ✅        |
| Productos de serie única         |      ✅       |       ✅        |
| Transferencias entre ubicaciones |      ✅       |       ✅        |
| Historial de movimientos         |      ✅       |       ✅        |
| Stock mínimo y alertas           |      ✅       |       ✅        |
| API REST documentada             |      ✅       | ❌ (no pública) |
| Órdenes de trabajo / reparación  |      ❌       |       ✅        |
| Gestión de vehículos             |      ❌       |       ✅        |
| Integración con marcas (OEM)     |      ❌       |       ✅        |
| Recepción activa de vehículos    |      ❌       |       ✅        |
| App móvil de técnicos            |      ❌       |       ✅        |
| Facturación y contabilidad       |      ❌       |       ✅        |
| Específico para automoción       | ❌ (genérico) |       ✅        |

### Cómo manejar estas diferencias en la demo

El foco de la demo es el **chatbot y la gestión de stock**, no el ERP completo. Si el cliente pregunta por órdenes de trabajo o fichas de vehículos, la respuesta correcta es:

_"InvenTree lo usamos como simulador de los flujos de almacén para esta demo. En producción, el chatbot se conecta directamente a Spiga+, que ya tiene toda esa información. Lo que estamos demostrando hoy es cómo el chatbot consulta y gestiona el stock en lenguaje natural, con los mismos datos y la misma lógica que usaría sobre Spiga+."_

---

## 9. Variables de entorno adicionales para InvenTree

Añadir al `.env` del backend:

```env
# InvenTree
INVENTREE_API_URL=http://localhost:8080/api/
INVENTREE_API_TOKEN=tu_token_aqui
INVENTREE_LOCATION_ALM_A=1          # ID de ubicación Almacén Norte en InvenTree
INVENTREE_LOCATION_ALM_B=2          # ID de ubicación Almacén Sur en InvenTree
INVENTREE_SYNC_AS_SOURCE=true       # usar InvenTree como fuente de sync
```
