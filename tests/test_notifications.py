"""Tests FASE 4 — Notificaciones en-app."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models

client = TestClient(app)


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def get_token(username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(autouse=True)
def clean_notifications():
    yield
    db = SessionLocal()
    db.query(models.Notification).delete()
    db.commit()
    db.close()


def _create_notification(recipient_username: str, notif_type: str = "stock_modification") -> int:
    db = SessionLocal()
    user = db.query(models.User).filter_by(username=recipient_username).first()
    n = models.Notification(
        recipient_user_id=user.id,
        type=notif_type,
        message="Test notification",
        is_read=False,
    )
    db.add(n)
    db.commit()
    nid = n.id
    db.close()
    return nid


# ---- Tests: GET /notifications ----

def test_user_gets_own_notifications():
    _create_notification("admin")
    token = get_token("admin", "Admin123!")
    r = client.get("/notifications", headers=auth_header(token))
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_user_does_not_see_other_users_notifications():
    _create_notification("admin")
    token = get_token("operador_a1", "Oper123!")
    r = client.get("/notifications", headers=auth_header(token))
    assert r.status_code == 200
    assert len(r.json()) == 0


def test_notifications_filter_unread_only():
    nid = _create_notification("admin")
    # Mark one as read directly
    db = SessionLocal()
    notif = db.query(models.Notification).filter_by(id=nid).first()
    notif.is_read = True
    db.commit()
    db.close()
    # Create another unread
    _create_notification("admin")

    token = get_token("admin", "Admin123!")
    r = client.get("/notifications?unread_only=true", headers=auth_header(token))
    assert r.status_code == 200
    assert all(not n["is_read"] for n in r.json())
    assert len(r.json()) == 1


def test_notifications_requires_auth():
    assert client.get("/notifications").status_code == 401


# ---- Tests: GET /notifications/unread-count ----

def test_unread_count():
    _create_notification("admin")
    _create_notification("admin")
    token = get_token("admin", "Admin123!")
    r = client.get("/notifications/unread-count", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["unread_count"] == 2


def test_unread_count_zero_when_no_notifications():
    token = get_token("operador_a1", "Oper123!")
    r = client.get("/notifications/unread-count", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["unread_count"] == 0


# ---- Tests: PATCH /notifications/{id}/read ----

def test_mark_notification_as_read():
    nid = _create_notification("admin")
    token = get_token("admin", "Admin123!")
    r = client.patch(f"/notifications/{nid}/read", headers=auth_header(token))
    assert r.status_code == 200

    db = SessionLocal()
    notif = db.query(models.Notification).filter_by(id=nid).first()
    assert notif.is_read == True
    db.close()


def test_cannot_mark_other_users_notification_as_read():
    nid = _create_notification("admin")
    token = get_token("operador_a1", "Oper123!")
    r = client.patch(f"/notifications/{nid}/read", headers=auth_header(token))
    assert r.status_code == 403


# ---- Tests: PATCH /notifications/read-all ----

def test_mark_all_notifications_as_read():
    _create_notification("admin")
    _create_notification("admin")
    token = get_token("admin", "Admin123!")
    r = client.patch("/notifications/read-all", headers=auth_header(token))
    assert r.status_code == 200

    db = SessionLocal()
    admin = db.query(models.User).filter_by(username="admin").first()
    unread = db.query(models.Notification).filter(
        models.Notification.recipient_user_id == admin.id,
        models.Notification.is_read == False,
    ).count()
    assert unread == 0
    db.close()


def test_mark_all_read_only_affects_own_notifications():
    _create_notification("admin")
    _create_notification("gestor1")

    token = get_token("admin", "Admin123!")
    client.patch("/notifications/read-all", headers=auth_header(token))

    db = SessionLocal()
    gestor = db.query(models.User).filter_by(username="gestor1").first()
    unread_gestor = db.query(models.Notification).filter(
        models.Notification.recipient_user_id == gestor.id,
        models.Notification.is_read == False,
    ).count()
    assert unread_gestor == 1
    db.close()
