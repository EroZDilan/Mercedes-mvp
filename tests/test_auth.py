"""Tests FASE 1 — Autenticación."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models

client = TestClient(app)


def login(username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    return r


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Tests de login ----

def test_login_valid_admin():
    r = login("admin", "Admin123!")
    assert r.status_code == 200
    d = r.json()
    assert "access_token" in d
    assert "refresh_token" in d
    assert d["user"]["role"] == "admin"


def test_me_with_valid_token():
    token = login("admin", "Admin123!").json()["access_token"]
    r = client.get("/auth/me", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_me_without_token():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_fake_token():
    r = client.get("/auth/me", headers=auth_header("tokenbasura"))
    assert r.status_code == 401


def test_refresh_valid():
    refresh = login("admin", "Admin123!").json()["refresh_token"]
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_invalid():
    r = client.post("/auth/refresh", json={"refresh_token": "basura"})
    assert r.status_code == 401


def test_access_token_as_refresh_rejected():
    access = login("admin", "Admin123!").json()["access_token"]
    r = client.post("/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401


def test_wrong_password():
    r = login("gestor1", "wrong")
    assert r.status_code == 401
    assert "Credenciales inválidas" in r.json()["detail"]


def test_message_generic_no_user_hint():
    r = login("gestor1", "wrong")
    assert r.status_code == 401
    assert "Credenciales inválidas" in r.json()["detail"]


def test_nonexistent_user():
    r = login("noexiste", "Admin123!")
    assert r.status_code == 401
    assert "Credenciales inválidas" in r.json()["detail"]


def test_lockout_after_five_attempts():
    # Reset supervisor_a antes del test
    db = SessionLocal()
    user = db.query(models.User).filter_by(username="supervisor_a").first()
    user.failed_attempts = 0
    user.is_locked = False
    db.commit()
    db.close()

    for i in range(1, 6):
        r = login("supervisor_a", "wrong")
        assert r.status_code == 401, f"intento {i}: expected 401 got {r.status_code}"

    r = login("supervisor_a", "Super123!")
    assert r.status_code == 403
    assert "bloqueada" in r.json()["detail"].lower()


def test_locked_account_correct_password_still_403():
    db = SessionLocal()
    user = db.query(models.User).filter_by(username="supervisor_b").first()
    user.is_locked = True
    user.failed_attempts = 5
    db.commit()
    db.close()

    r = login("supervisor_b", "Super123!")
    assert r.status_code == 403

    # Desbloquear para no contaminar otros tests
    db = SessionLocal()
    user = db.query(models.User).filter_by(username="supervisor_b").first()
    user.is_locked = False
    user.failed_attempts = 0
    db.commit()
    db.close()


def test_logout_revokes_token():
    token = login("admin", "Admin123!").json()["access_token"]
    r = client.post("/auth/logout", headers=auth_header(token))
    assert r.status_code == 200

    r2 = client.get("/auth/me", headers=auth_header(token))
    assert r2.status_code == 401


def test_multiple_roles_login():
    cases = [
        ("gestor1", "Gestor123!", "gestor", False),
        ("supervisor_b", "Super123!", "supervisor", True),
        ("operador_a1", "Oper123!", "operador", True),
    ]
    for username, pwd, expected_role, has_warehouse in cases:
        r = login(username, pwd)
        assert r.status_code == 200, f"{username}: {r.text}"
        d = r.json()
        assert d["user"]["role"] == expected_role
        if has_warehouse:
            assert d["user"]["warehouse_id"] is not None


def test_supervisor_and_operador_have_warehouse_id():
    r = login("supervisor_a", "Super123!")
    # supervisor_a might be locked from test_lockout — reset first
    if r.status_code == 403:
        db = SessionLocal()
        u = db.query(models.User).filter_by(username="supervisor_a").first()
        u.is_locked = False
        u.failed_attempts = 0
        db.commit()
        db.close()
        r = login("supervisor_a", "Super123!")
    assert r.status_code == 200
    assert r.json()["user"]["warehouse_id"] is not None

    r2 = login("operador_a1", "Oper123!")
    assert r2.status_code == 200
    assert r2.json()["user"]["warehouse_id"] is not None


def test_audit_log_has_all_event_types():
    # Forzar que existan los tres tipos en el log
    login("admin", "Admin123!")  # SUCCESS

    # Crear LOGIN_FAILED
    db = SessionLocal()
    u = db.query(models.User).filter_by(username="gestor1").first()
    u.failed_attempts = 0
    u.is_locked = False
    db.commit()
    db.close()
    login("gestor1", "wrongpassword")  # FAILED

    # Crear ACCOUNT_LOCKED
    db = SessionLocal()
    u = db.query(models.User).filter_by(username="operador_b1").first()
    u.failed_attempts = 0
    u.is_locked = False
    db.commit()
    db.close()
    for _ in range(5):
        login("operador_b1", "wrong")  # 5 intentos → LOCKED

    db = SessionLocal()
    logs = db.query(models.AuditLog).all()
    actions = {l.action for l in logs}
    db.close()

    assert "LOGIN_SUCCESS" in actions
    assert "LOGIN_FAILED" in actions
    assert "ACCOUNT_LOCKED" in actions

    # Limpiar operador_b1 bloqueado
    db = SessionLocal()
    u = db.query(models.User).filter_by(username="operador_b1").first()
    u.is_locked = False
    u.failed_attempts = 0
    db.commit()
    db.close()


def test_lockout_sends_notification_to_admin():
    db = SessionLocal()
    u = db.query(models.User).filter_by(username="operador_a1").first()
    u.failed_attempts = 0
    u.is_locked = False
    db.commit()
    db.close()

    for _ in range(5):
        login("operador_a1", "wrong")

    db = SessionLocal()
    admin = db.query(models.User).join(models.Role).filter(models.Role.name == "admin").first()
    notif = db.query(models.Notification).filter_by(
        recipient_user_id=admin.id, type="account_locked"
    ).order_by(models.Notification.id.desc()).first()
    db.close()

    assert notif is not None

    # Limpiar
    db = SessionLocal()
    u = db.query(models.User).filter_by(username="operador_a1").first()
    u.is_locked = False
    u.failed_attempts = 0
    db.commit()
    db.close()
