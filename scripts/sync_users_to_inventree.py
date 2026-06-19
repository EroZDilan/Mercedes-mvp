"""Create chatbot MVP users in InvenTree so both systems stay in sync.

Chatbot users:
  admin        / Admin123!   → superuser
  gestor1      / Gestor123!  → staff
  supervisor_a / Super123!   → staff
  supervisor_b / Super123!   → staff
  operador_a1  / Oper123!    → regular
  operador_b1  / Oper123!    → regular
"""
import httpx
import sys

BASE = "http://localhost:8080/api/"

def get_token():
    # Try env first, then hardcoded demo token
    import os
    return os.getenv(
        "INVENTREE_TOKEN",
        "inv-e314f1c59dd09df358ef1821034183d275d364b7-20260619",
    )

HEADERS = {
    "Authorization": f"Token {get_token()}",
    "Content-Type": "application/json",
}

USERS = [
    {"username": "admin",        "first_name": "Admin",       "last_name": "Sistema",
     "email": "admin@demo.com",       "password": "Admin123!",  "is_staff": True,  "is_superuser": True},
    {"username": "gestor1",      "first_name": "Gestor",      "last_name": "General",
     "email": "gestor1@demo.com",     "password": "Gestor123!", "is_staff": True,  "is_superuser": False},
    {"username": "supervisor_a", "first_name": "Supervisor",  "last_name": "Norte",
     "email": "sup_a@demo.com",       "password": "Super123!",  "is_staff": True,  "is_superuser": False},
    {"username": "supervisor_b", "first_name": "Supervisor",  "last_name": "Sur",
     "email": "sup_b@demo.com",       "password": "Super123!",  "is_staff": True,  "is_superuser": False},
    {"username": "operador_a1",  "first_name": "Operador",    "last_name": "Norte 1",
     "email": "op_a1@demo.com",       "password": "Oper123!",   "is_staff": False, "is_superuser": False},
    {"username": "operador_b1",  "first_name": "Operador",    "last_name": "Sur 1",
     "email": "op_b1@demo.com",       "password": "Oper123!",   "is_staff": False, "is_superuser": False},
]

def get_existing_usernames() -> set:
    r = httpx.get(f"{BASE}user/", headers=HEADERS, params={"limit": 100})
    r.raise_for_status()
    data = r.json()
    users = data.get("results", data) if isinstance(data, dict) else data
    return {u["username"] for u in users}

def create_user(u: dict) -> bool:
    r = httpx.post(f"{BASE}user/", headers=HEADERS, json=u)
    if r.status_code in (200, 201):
        return True
    print(f"    ERROR {r.status_code}: {r.text[:120]}")
    return False

def main():
    print("Conectando a InvenTree...")
    try:
        existing = get_existing_usernames()
    except Exception as e:
        print(f"Error: no se pudo conectar a InvenTree: {e}")
        sys.exit(1)

    print(f"Usuarios existentes en InvenTree: {existing}\n")

    created = 0
    skipped = 0
    for u in USERS:
        if u["username"] in existing:
            print(f"  >> {u['username']} ya existe - omitiendo")
            skipped += 1
        else:
            ok = create_user(u)
            if ok:
                print(f"  OK {u['username']} creado (staff={u['is_staff']}, super={u['is_superuser']})")
                created += 1
            else:
                print(f"  XX {u['username']} fallo")

    print(f"\nResumen: {created} creados, {skipped} ya existían")
    print("Accede a InvenTree en: http://localhost:8080")

if __name__ == "__main__":
    main()
