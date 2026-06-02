"""Tests FASE 4 — Gestión de usuarios (admin only)."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models

client = TestClient(app)

_ORIGINAL_USERS = {"admin", "gestor1", "supervisor_a", "supervisor_b", "operador_a1", "operador_b1"}


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def get_token(username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(autouse=True)
def restore_users():
    yield
    db = SessionLocal()
    # Delete test-created users
    db.query(models.User).filter(
        ~models.User.username.in_(_ORIGINAL_USERS)
    ).delete(synchronize_session=False)
    # Restore state for original users
    for username in _ORIGINAL_USERS:
        user = db.query(models.User).filter_by(username=username).first()
        if user:
            user.is_active = True
            user.is_locked = False
            user.failed_attempts = 0
    db.commit()
    db.close()


# ---- Tests: GET /users ----

def test_admin_can_list_users():
    token = get_token("admin", "Admin123!")
    r = client.get("/users", headers=auth_header(token))
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "admin" in usernames
    assert "operador_a1" in usernames


def test_gestor_cannot_list_users():
    token = get_token("gestor1", "Gestor123!")
    r = client.get("/users", headers=auth_header(token))
    assert r.status_code == 403


def test_operador_cannot_list_users():
    token = get_token("operador_a1", "Oper123!")
    r = client.get("/users", headers=auth_header(token))
    assert r.status_code == 403


def test_users_requires_auth():
    assert client.get("/users").status_code == 401


# ---- Tests: POST /users ----

def test_admin_can_create_user():
    db = SessionLocal()
    role = db.query(models.Role).filter_by(name="operador").first()
    wh = db.query(models.Warehouse).filter_by(code="ALM-A").first()
    role_id, wh_id = role.id, wh.id
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.post("/users", headers=auth_header(token), json={
        "username": "nuevo_operador",
        "password": "NuevoPass1!",
        "full_name": "Nuevo Operador",
        "role_id": role_id,
        "warehouse_id": wh_id,
    })
    assert r.status_code == 201
    assert r.json()["username"] == "nuevo_operador"
    assert r.json()["role"] == "operador"


def test_create_user_weak_password():
    db = SessionLocal()
    role_id = db.query(models.Role).filter_by(name="operador").first().id
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.post("/users", headers=auth_header(token), json={
        "username": "weakuser",
        "password": "simple",
        "role_id": role_id,
    })
    assert r.status_code == 422


def test_create_user_duplicate_username():
    db = SessionLocal()
    role_id = db.query(models.Role).filter_by(name="operador").first().id
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.post("/users", headers=auth_header(token), json={
        "username": "operador_a1",
        "password": "OtroPass1!",
        "role_id": role_id,
    })
    assert r.status_code == 409


def test_non_admin_cannot_create_user():
    db = SessionLocal()
    role_id = db.query(models.Role).filter_by(name="operador").first().id
    db.close()

    token = get_token("gestor1", "Gestor123!")
    r = client.post("/users", headers=auth_header(token), json={
        "username": "nuevo_user",
        "password": "NuevoPass1!",
        "role_id": role_id,
    })
    assert r.status_code == 403


# ---- Tests: GET /users/{id} ----

def test_admin_can_get_user_by_id():
    db = SessionLocal()
    operador = db.query(models.User).filter_by(username="operador_a1").first()
    uid = operador.id
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.get(f"/users/{uid}", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["username"] == "operador_a1"


# ---- Tests: POST /users/{id}/unlock ----

def test_admin_can_unlock_user():
    db = SessionLocal()
    user = db.query(models.User).filter_by(username="operador_b1").first()
    user.is_locked = True
    user.failed_attempts = 5
    uid = user.id
    db.commit()
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.post(f"/users/{uid}/unlock", headers=auth_header(token))
    assert r.status_code == 200

    db = SessionLocal()
    user = db.query(models.User).filter_by(id=uid).first()
    assert user.is_locked == False
    assert user.failed_attempts == 0
    db.close()


def test_non_admin_cannot_unlock():
    db = SessionLocal()
    uid = db.query(models.User).filter_by(username="operador_b1").first().id
    db.close()

    token = get_token("gestor1", "Gestor123!")
    assert client.post(f"/users/{uid}/unlock", headers=auth_header(token)).status_code == 403


# ---- Tests: POST /users/{id}/reset-password ----

def test_admin_can_reset_password():
    import bcrypt
    db = SessionLocal()
    operador = db.query(models.User).filter_by(username="operador_b1").first()
    uid = operador.id
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.post(f"/users/{uid}/reset-password", headers=auth_header(token),
                    json={"new_password": "NuevaPass9!"})
    assert r.status_code == 200

    # Restaurar contraseña original para no romper otros tests
    db = SessionLocal()
    operador = db.query(models.User).filter_by(username="operador_b1").first()
    operador.password_hash = bcrypt.hashpw(b"Oper123!", bcrypt.gensalt()).decode()
    db.commit()
    db.close()


def test_reset_password_validates_strength():
    db = SessionLocal()
    uid = db.query(models.User).filter_by(username="operador_b1").first().id
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.post(f"/users/{uid}/reset-password", headers=auth_header(token),
                    json={"new_password": "weak"})
    assert r.status_code == 422


# ---- Tests: POST /users/{id}/deactivate ----

def test_admin_can_deactivate_user():
    db = SessionLocal()
    uid = db.query(models.User).filter_by(username="operador_b1").first().id
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.post(f"/users/{uid}/deactivate", headers=auth_header(token))
    assert r.status_code == 200

    db = SessionLocal()
    user = db.query(models.User).filter_by(id=uid).first()
    assert user.is_active == False
    db.close()


# ---- Tests: POST /users/{id}/force-logout ----

def test_admin_can_force_logout_user():
    # Create active sessions for operador_a1
    oper_token = get_token("operador_a1", "Oper123!")

    db = SessionLocal()
    uid = db.query(models.User).filter_by(username="operador_a1").first().id
    db.close()

    admin_token = get_token("admin", "Admin123!")
    r = client.post(f"/users/{uid}/force-logout", headers=auth_header(admin_token))
    assert r.status_code == 200

    # operador_a1's token should be revoked now
    r2 = client.get("/auth/me", headers=auth_header(oper_token))
    assert r2.status_code == 401
