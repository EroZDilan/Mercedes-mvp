"""Tests FASE 5 — CRM: notas, historial y métricas."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models

client = TestClient(app)


# ---- Helpers ----

def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def get_token(username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---- Fixtures ----

@pytest.fixture(scope="module")
def user_ids():
    """Returns dict mapping username → user_id."""
    db = SessionLocal()
    users = db.query(models.User).all()
    result = {u.username: u.id for u in users}
    db.close()
    return result


@pytest.fixture(autouse=True)
def clean_crm():
    yield
    db = SessionLocal()
    db.query(models.CrmNote).delete(synchronize_session=False)
    db.query(models.Notification).filter(
        models.Notification.type == "crm_note"
    ).delete(synchronize_session=False)
    db.query(models.ChatHistory).filter(
        models.ChatHistory.session_id.like("test-crm-%")
    ).delete(synchronize_session=False)
    db.commit()
    db.close()


# ---- Tests: POST /crm/notes ----

def test_create_note_returns_note():
    token = get_token("admin", "Admin123!")
    r = client.post("/crm/notes", headers=auth_header(token), json={"content": "Nota de prueba"})
    assert r.status_code == 201
    data = r.json()
    assert data["content"] == "Nota de prueba"
    assert "id" in data
    assert "user_id" in data


def test_create_note_with_related_to():
    token = get_token("admin", "Admin123!")
    r = client.post(
        "/crm/notes",
        headers=auth_header(token),
        json={"content": "Nota con referencia", "related_to": "P001"},
    )
    assert r.status_code == 201
    assert r.json()["related_to"] == "P001"


def test_create_note_notifies_admin_and_superior(user_ids):
    token = get_token("operador_a1", "Oper123!")
    client.post("/crm/notes", headers=auth_header(token), json={"content": "Nota del operador"})

    db = SessionLocal()
    admin_id = user_ids["admin"]
    supervisor_a_id = user_ids["supervisor_a"]

    admin_notif = db.query(models.Notification).filter(
        models.Notification.recipient_user_id == admin_id,
        models.Notification.type == "crm_note",
    ).first()
    sup_notif = db.query(models.Notification).filter(
        models.Notification.recipient_user_id == supervisor_a_id,
        models.Notification.type == "crm_note",
    ).first()
    db.close()

    assert admin_notif is not None
    assert sup_notif is not None


def test_admin_creates_note_no_crm_notification(user_ids):
    admin_id = user_ids["admin"]
    token = get_token("admin", "Admin123!")
    client.post("/crm/notes", headers=auth_header(token), json={"content": "Nota del admin"})

    db = SessionLocal()
    count = db.query(models.Notification).filter(
        models.Notification.type == "crm_note",
    ).count()
    db.close()
    assert count == 0


# ---- Tests: GET /crm/notes ----

def test_list_own_notes(user_ids):
    token = get_token("admin", "Admin123!")
    client.post("/crm/notes", headers=auth_header(token), json={"content": "Nota 1"})
    client.post("/crm/notes", headers=auth_header(token), json={"content": "Nota 2"})

    r = client.get("/crm/notes", headers=auth_header(token))
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_user_does_not_see_others_notes_by_default(user_ids):
    # operador creates a note
    token_op = get_token("operador_a1", "Oper123!")
    client.post("/crm/notes", headers=auth_header(token_op), json={"content": "Nota del operador"})

    # supervisor sees their own 0 notes (not operador's)
    token_sup = get_token("supervisor_a", "Super123!")
    r = client.get("/crm/notes", headers=auth_header(token_sup))
    assert r.status_code == 200
    assert all(item["content"] != "Nota del operador" for item in r.json())


def test_supervisor_can_see_subordinate_notes(user_ids):
    operador_id = user_ids["operador_a1"]
    token_op = get_token("operador_a1", "Oper123!")
    client.post("/crm/notes", headers=auth_header(token_op), json={"content": "Nota del operador"})

    token_sup = get_token("supervisor_a", "Super123!")
    r = client.get(f"/crm/notes?user_id={operador_id}", headers=auth_header(token_sup))
    assert r.status_code == 200
    assert any(n["content"] == "Nota del operador" for n in r.json())


def test_supervisor_cannot_see_other_warehouse_notes(user_ids):
    operador_b1_id = user_ids["operador_b1"]
    db = SessionLocal()
    db.add(models.CrmNote(user_id=operador_b1_id, content="Nota de ALM-B"))
    db.commit()
    db.close()

    token = get_token("supervisor_a", "Super123!")
    r = client.get(f"/crm/notes?user_id={operador_b1_id}", headers=auth_header(token))
    assert r.status_code == 403


def test_operador_cannot_see_supervisor_notes(user_ids):
    supervisor_id = user_ids["supervisor_a"]
    db = SessionLocal()
    db.add(models.CrmNote(user_id=supervisor_id, content="Nota del supervisor"))
    db.commit()
    db.close()

    token = get_token("operador_a1", "Oper123!")
    r = client.get(f"/crm/notes?user_id={supervisor_id}", headers=auth_header(token))
    assert r.status_code == 403


def test_gestor_can_see_any_user_notes(user_ids):
    operador_b1_id = user_ids["operador_b1"]
    db = SessionLocal()
    db.add(models.CrmNote(user_id=operador_b1_id, content="Nota operador B"))
    db.commit()
    db.close()

    token = get_token("gestor1", "Gestor123!")
    r = client.get(f"/crm/notes?user_id={operador_b1_id}", headers=auth_header(token))
    assert r.status_code == 200
    assert any(n["content"] == "Nota operador B" for n in r.json())


# ---- Tests: PUT /crm/notes/{id} ----

def test_update_own_note(user_ids):
    token = get_token("admin", "Admin123!")
    created = client.post(
        "/crm/notes", headers=auth_header(token), json={"content": "Original"}
    ).json()

    r = client.put(
        f"/crm/notes/{created['id']}",
        headers=auth_header(token),
        json={"content": "Editada"},
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Editada"
    assert r.json()["modified_at"] is not None


def test_cannot_update_others_note(user_ids):
    # supervisor_a creates a note
    db = SessionLocal()
    sup_id = user_ids["supervisor_a"]
    note = models.CrmNote(user_id=sup_id, content="Nota del supervisor")
    db.add(note)
    db.commit()
    note_id = note.id
    db.close()

    token = get_token("operador_a1", "Oper123!")
    r = client.put(
        f"/crm/notes/{note_id}",
        headers=auth_header(token),
        json={"content": "Intento de edición"},
    )
    assert r.status_code == 403


def test_admin_can_update_any_note(user_ids):
    db = SessionLocal()
    op_id = user_ids["operador_a1"]
    note = models.CrmNote(user_id=op_id, content="Nota original")
    db.add(note)
    db.commit()
    note_id = note.id
    db.close()

    token = get_token("admin", "Admin123!")
    r = client.put(
        f"/crm/notes/{note_id}",
        headers=auth_header(token),
        json={"content": "Modificada por admin"},
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Modificada por admin"


# ---- Tests: DELETE /crm/notes/{id} ----

def test_delete_own_note():
    token = get_token("admin", "Admin123!")
    created = client.post(
        "/crm/notes", headers=auth_header(token), json={"content": "Para borrar"}
    ).json()

    r = client.delete(f"/crm/notes/{created['id']}", headers=auth_header(token))
    assert r.status_code == 204

    r2 = client.get("/crm/notes", headers=auth_header(token))
    assert all(n["id"] != created["id"] for n in r2.json())


def test_cannot_delete_others_note(user_ids):
    db = SessionLocal()
    sup_id = user_ids["supervisor_a"]
    note = models.CrmNote(user_id=sup_id, content="No borrable")
    db.add(note)
    db.commit()
    note_id = note.id
    db.close()

    token = get_token("operador_a1", "Oper123!")
    r = client.delete(f"/crm/notes/{note_id}", headers=auth_header(token))
    assert r.status_code == 403


def test_crm_requires_auth():
    assert client.get("/crm/notes").status_code == 401
    assert client.post("/crm/notes", json={"content": "x"}).status_code == 401
    assert client.get("/crm/history").status_code == 401
    assert client.get("/crm/metrics").status_code == 401


# ---- Tests: GET /crm/history ----

def test_history_shows_chat_and_notes(user_ids):
    admin_id = user_ids["admin"]
    db = SessionLocal()
    db.add(models.ChatHistory(
        user_id=admin_id,
        session_id="test-crm-hist",
        question="¿Cuántos filtros hay?",
        response="Hay 45.",
        response_time_ms=100,
    ))
    db.commit()
    db.close()

    token = get_token("admin", "Admin123!")
    client.post("/crm/notes", headers=auth_header(token), json={"content": "Nota de historial"})

    r = client.get("/crm/history", headers=auth_header(token))
    assert r.status_code == 200
    types_in_response = {item["type"] for item in r.json()}
    assert "chat" in types_in_response
    assert "crm_note" in types_in_response


def test_supervisor_can_view_subordinate_history(user_ids):
    op_id = user_ids["operador_a1"]
    db = SessionLocal()
    db.add(models.CrmNote(user_id=op_id, content="Nota del operador para historial"))
    db.add(models.ChatHistory(
        user_id=op_id,
        session_id="test-crm-hist-op",
        question="¿Hay stock?",
        response="Sí.",
        response_time_ms=50,
    ))
    db.commit()
    db.close()

    token = get_token("supervisor_a", "Super123!")
    r = client.get(f"/crm/history?user_id={op_id}", headers=auth_header(token))
    assert r.status_code == 200
    types_in_response = {item["type"] for item in r.json()}
    assert "crm_note" in types_in_response
    assert "chat" in types_in_response


# ---- Tests: GET /crm/metrics ----

def test_metrics_returns_expected_keys():
    token = get_token("admin", "Admin123!")
    r = client.get("/crm/metrics", headers=auth_header(token))
    assert r.status_code == 200
    data = r.json()
    assert "user_id" in data
    assert "chatbot_queries_today" in data
    assert "chatbot_queries_week" in data
    assert "stock_modifications_month" in data
    assert "top_modified_products" in data
    assert "last_activity" in data


def test_metrics_chat_count_accurate(user_ids):
    sup_b_id = user_ids["supervisor_b"]
    db = SessionLocal()
    db.add(models.ChatHistory(
        user_id=sup_b_id, session_id="test-crm-metrics-1",
        question="Q1", response="R1", response_time_ms=10,
    ))
    db.add(models.ChatHistory(
        user_id=sup_b_id, session_id="test-crm-metrics-2",
        question="Q2", response="R2", response_time_ms=10,
    ))
    db.commit()
    db.close()

    token = get_token("supervisor_b", "Super123!")
    r = client.get("/crm/metrics", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["chatbot_queries_week"] >= 2


def test_supervisor_can_view_subordinate_metrics(user_ids):
    op_id = user_ids["operador_a1"]
    token = get_token("supervisor_a", "Super123!")
    r = client.get(f"/crm/metrics?user_id={op_id}", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["user_id"] == op_id


# ---- Tests: GET /crm/metrics/global ----

def test_global_metrics_admin_only():
    token = get_token("operador_a1", "Oper123!")
    r = client.get("/crm/metrics/global", headers=auth_header(token))
    assert r.status_code == 403

    token_sup = get_token("supervisor_a", "Super123!")
    r2 = client.get("/crm/metrics/global", headers=auth_header(token_sup))
    assert r2.status_code == 403


def test_global_metrics_returns_keys():
    token = get_token("admin", "Admin123!")
    r = client.get("/crm/metrics/global", headers=auth_header(token))
    assert r.status_code == 200
    data = r.json()
    assert "total_queries_today" in data
    assert "total_queries_week" in data
    assert "most_active_warehouse" in data
    assert "top_users" in data
