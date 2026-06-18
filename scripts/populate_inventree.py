import httpx
import time

client = httpx.Client()  # reutilizar para PATCH

BASE = "http://localhost:8080/api/"
HEADERS = {
    "Authorization": "Token inv-e314f1c59dd09df358ef1821034183d275d364b7-20260619",
    "Content-Type": "application/json"
}

def post(endpoint, data):
    r = httpx.post(f"{BASE}{endpoint}", headers=HEADERS, json=data)
    try:
        r.raise_for_status()
    except Exception:
        print(f"  ERROR en POST {endpoint}: {r.status_code} {r.text[:200]}")
        raise
    return r.json()

def get(endpoint, params=None):
    r = httpx.get(f"{BASE}{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

# ── 1. Crear categorías ──────────────────────────────────────
print("Creando categorías...")
categorias = [
    {"name": "Repuestos mecánicos", "description": "Filtros, correas, frenos"},
    {"name": "Lubricantes",         "description": "Aceites, grasas, líquidos"},
    {"name": "Herramientas",        "description": "Equipos de taller"},
    {"name": "Electricidad",        "description": "Componentes eléctricos"},
    {"name": "Carrocería",          "description": "Piezas de carrocería y pintura"},
    {"name": "Serie única",         "description": "Equipos serializados"},
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
    {"name": "Filtro de aceite",              "cat": "Repuestos mecánicos", "min": 10, "qty": 45,  "loc": "Norte_Zona B - Lubricantes"},
    {"name": "Filtro de aire",                "cat": "Repuestos mecánicos", "min": 8,  "qty": 30,  "loc": "Norte_Zona B - Lubricantes"},
    {"name": "Aceite motor 5W-30 (1L)",       "cat": "Lubricantes",         "min": 20, "qty": 120, "loc": "Norte_Zona B - Lubricantes"},
    {"name": "Pastillas de freno delanteras", "cat": "Repuestos mecánicos", "min": 5,  "qty": 18,  "loc": "Norte_Zona A - Repuestos"},
    {"name": "Correa de distribución",        "cat": "Repuestos mecánicos", "min": 3,  "qty": 12,  "loc": "Sur_Zona A - Repuestos"},
    {"name": "Líquido de frenos DOT4",        "cat": "Lubricantes",         "min": 10, "qty": 55,  "loc": "Sur_Zona B - Lubricantes"},
    {"name": "Bujías (pack 4)",               "cat": "Electricidad",        "min": 6,  "qty": 25,  "loc": "Sur_Zona A - Repuestos"},
    {"name": "Lámpara H7",                    "cat": "Electricidad",        "min": 8,  "qty": 40,  "loc": "Norte_Zona A - Repuestos"},
    {"name": "Llave de impacto",              "cat": "Herramientas",        "min": 1,  "qty": 3,   "loc": "Norte_Zona C - Herramientas"},
    {"name": "Gato hidráulico 2T",            "cat": "Herramientas",        "min": 1,  "qty": 2,   "loc": "Sur_Zona C - Herramientas"},
]

for p in productos:
    part = post("part/", {
        "name": p["name"],
        "category": cat_ids[p["cat"]],
        "minimum_stock": p["min"],
        "trackable": False,
        "active": True
    })
    post("stock/", {
        "part": part["pk"],
        "quantity": p["qty"],
        "location": zonas[p["loc"]]
    })
    print(f"  ✓ {p['name']} — {p['qty']} uds. (stock mín: {p['min']})")
    time.sleep(0.3)

# ── 4. Crear productos de serie única ────────────────────────
print("\nCreando productos de serie única...")
series = [
    {"name": "Motor eléctrico 5HP",  "sn": "SN-2041", "status": 10, "loc": "Norte_Zona C - Herramientas"},
    {"name": "Compresor industrial",  "sn": "SN-1887", "status": 50, "loc": "Sur_Zona C - Herramientas"},
    {"name": "Elevador hidráulico",   "sn": "SN-3302", "status": 10, "loc": "Sur_Zona C - Herramientas"},
    {"name": "Soldadora MIG",         "sn": "SN-0994", "status": 10, "loc": "Norte_Zona C - Herramientas"},
]

for s in series:
    part = post("part/", {
        "name": s["name"],
        "category": cat_ids["Serie única"],
        "trackable": True,
        "active": True
    })
    stock_item = post("stock/", {
        "part": part["pk"],
        "quantity": 1,
        "location": zonas[s["loc"]],
        "status": s["status"]
    })
    # InvenTree 1.3.5: serial se asigna vía PATCH después de crear el item
    r = httpx.patch(f"{BASE}stock/{stock_item[0]['pk'] if isinstance(stock_item, list) else stock_item['pk']}/", headers=HEADERS,
                    json={"serial": s["sn"]})
    if r.status_code == 200:
        print(f"  ✓ {s['name']} — Serie: {s['sn']}")
    else:
        print(f"  ⚠ {s['name']} creado pero serial no asignado: {r.status_code}")
    time.sleep(0.3)

# ── 5. Crear usuarios de prueba ──────────────────────────────
print("\nCreando usuarios de prueba...")
usuarios = [
    {"username": "admin_demo",   "email": "admin_demo@demo.com",   "password": "Admin1234!", "is_staff": True,  "is_superuser": True},
    {"username": "gestor_norte", "email": "gestor@demo.com",       "password": "Gestor123!", "is_staff": True,  "is_superuser": False},
    {"username": "supervisor_a", "email": "supervisor@demo.com",   "password": "Super123!",  "is_staff": True,  "is_superuser": False},
    {"username": "operador_a1",  "email": "operador@demo.com",     "password": "Oper123!",   "is_staff": False, "is_superuser": False},
]
for u in usuarios:
    try:
        result = post("user/", {
            "username": u["username"],
            "email": u["email"],
            "password": u["password"],
            "is_staff": u["is_staff"],
            "is_superuser": u["is_superuser"]
        })
        print(f"  ✓ Usuario: {u['username']}")
    except Exception:
        print(f"  ⚠ Usuario {u['username']} ya existe o no se pudo crear (normal si ya existe)")
    time.sleep(0.2)

print("\n✅ Datos de prueba cargados correctamente.")
print(f"   Categorías:              {len(cat_ids)}")
print(f"   Productos por cantidad:  {len(productos)}")
print(f"   Productos serie única:   {len(series)}")
print(f"\nAccede a InvenTree en: http://localhost:8080")
print("Usuario: admin | Contraseña: admin1234")
