"""Tests FASE 3 — Chatbot con LangChain + Groq (LLM mockeado)."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models

client = TestClient(app)

MOCK_ANSWER = "Respuesta mockeada del chatbot."
UNRESOLVED_ANSWER = "No tengo información disponible sobre eso en este momento."


# ---- Fixtures ----

def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def get_token(username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def mock_llm():
    with patch("backend.services.chatbot_service.ChatGroq") as MockGroq:
        instance = MockGroq.return_value
        instance.invoke.return_value.content = MOCK_ANSWER
        yield instance


@pytest.fixture(autouse=True)
def clean_chat_history():
    yield
    db = SessionLocal()
    db.query(models.ChatHistory).delete()
    db.query(models.Notification).filter(
        models.Notification.type == "chat_unresolved"
    ).delete()
    db.commit()
    db.close()


# ---- Helpers ----

def send_message(token, message, session_id=None):
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    return client.post("/chatbot/message", headers=auth_header(token), json=body)


def get_invoke_system_prompt(mock_instance):
    """Extrae el contenido del SystemMessage que recibió el LLM."""
    messages = mock_instance.invoke.call_args[0][0]
    return messages[0].content


# ---- Tests de filtrado de contexto por rol ----

def test_admin_context_includes_both_warehouses(mock_llm):
    token = get_token("admin", "Admin123!")
    send_message(token, "¿qué hay en stock?")
    system = get_invoke_system_prompt(mock_llm)
    assert "Almacén Norte" in system
    assert "Almacén Sur" in system


def test_gestor_context_includes_both_warehouses(mock_llm):
    token = get_token("gestor1", "Gestor123!")
    send_message(token, "¿qué hay en stock?")
    system = get_invoke_system_prompt(mock_llm)
    assert "Almacén Norte" in system
    assert "Almacén Sur" in system


def test_supervisor_context_only_own_warehouse(mock_llm):
    token = get_token("supervisor_a", "Super123!")
    send_message(token, "¿qué tenemos?")
    system = get_invoke_system_prompt(mock_llm)
    assert "Almacén Norte" in system
    assert "Almacén Sur" not in system


def test_operador_context_only_own_warehouse(mock_llm):
    token = get_token("operador_a1", "Oper123!")
    send_message(token, "¿qué tenemos?")
    system = get_invoke_system_prompt(mock_llm)
    assert "Almacén Norte" in system
    assert "Almacén Sur" not in system


def test_supervisor_cannot_see_other_warehouse_products(mock_llm):
    """supervisor_a (Norte) no debe ver P005 (Pastillas de freno, solo en Sur)."""
    token = get_token("supervisor_a", "Super123!")
    send_message(token, "¿tenemos pastillas de freno?")
    system = get_invoke_system_prompt(mock_llm)
    assert "Pastillas de freno" not in system


def test_admin_context_includes_products_from_both(mock_llm):
    """admin ve productos de ambos almacenes: P006 (Amortiguador) solo existe en Sur."""
    token = get_token("admin", "Admin123!")
    send_message(token, "dame el inventario completo")
    system = get_invoke_system_prompt(mock_llm)
    # P006 Amortiguador solo está en ALM-B → prueba que admin recibe contexto de Sur
    assert "Amortiguador" in system or "P006" in system


# ---- Tests de persistencia ----

def test_message_saved_to_chat_history(mock_llm):
    token = get_token("admin", "Admin123!")
    r = send_message(token, "¿cuántos filtros hay?")
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    db = SessionLocal()
    admin = db.query(models.User).join(models.Role).filter(models.Role.name == "admin").first()
    entry = db.query(models.ChatHistory).filter_by(
        user_id=admin.id, session_id=session_id
    ).first()
    assert entry is not None
    assert entry.question == "¿cuántos filtros hay?"
    assert entry.response == MOCK_ANSWER
    db.close()


def test_response_format(mock_llm):
    token = get_token("admin", "Admin123!")
    r = send_message(token, "test")
    assert r.status_code == 200
    d = r.json()
    assert "response" in d
    assert "session_id" in d
    assert "response_time_ms" in d
    assert d["response"] == MOCK_ANSWER
    assert isinstance(d["response_time_ms"], int)


def test_session_id_returned_and_reusable(mock_llm):
    token = get_token("admin", "Admin123!")
    r1 = send_message(token, "primera pregunta")
    sid = r1.json()["session_id"]
    assert sid is not None

    r2 = send_message(token, "segunda pregunta", session_id=sid)
    assert r2.json()["session_id"] == sid


def test_warehouses_context_stored_in_history(mock_llm):
    """El campo warehouses_context se guarda como JSON."""
    import json
    token = get_token("supervisor_a", "Super123!")
    r = send_message(token, "test")
    session_id = r.json()["session_id"]

    db = SessionLocal()
    sup = db.query(models.User).filter_by(username="supervisor_a").first()
    entry = db.query(models.ChatHistory).filter_by(
        user_id=sup.id, session_id=session_id
    ).first()
    ctx = json.loads(entry.warehouses_context)
    assert "ALM-A" in ctx
    assert "ALM-B" not in ctx
    db.close()


# ---- Tests de memoria conversacional ----

def test_conversation_history_included_in_second_message(mock_llm):
    """Segundo mensaje recibe historial de la conversación en el prompt."""
    token = get_token("admin", "Admin123!")

    r1 = send_message(token, "primera pregunta")
    session_id = r1.json()["session_id"]

    mock_llm.invoke.reset_mock()
    mock_llm.invoke.return_value.content = "segunda respuesta"

    send_message(token, "segunda pregunta", session_id=session_id)

    messages = mock_llm.invoke.call_args[0][0]
    # SystemMessage + HumanMessage(q1) + AIMessage(a1) + HumanMessage(q2)
    assert len(messages) >= 4
    from langchain_core.messages import HumanMessage, AIMessage
    human_msgs = [m.content for m in messages if isinstance(m, HumanMessage)]
    ai_msgs = [m.content for m in messages if isinstance(m, AIMessage)]
    assert "primera pregunta" in human_msgs
    assert MOCK_ANSWER in ai_msgs
    assert "segunda pregunta" in human_msgs


# ---- Tests del endpoint /chatbot/history ----

def test_history_endpoint_returns_own_messages(mock_llm):
    token = get_token("admin", "Admin123!")
    send_message(token, "pregunta del admin")

    r = client.get("/chatbot/history", headers=auth_header(token))
    assert r.status_code == 200
    history = r.json()
    assert len(history) >= 1
    assert history[0]["question"] == "pregunta del admin"


def test_history_isolated_between_users(mock_llm):
    """El historial de admin no es visible para operador."""
    admin_token = get_token("admin", "Admin123!")
    oper_token = get_token("operador_a1", "Oper123!")

    send_message(admin_token, "mensaje secreto del admin")

    r = client.get("/chatbot/history", headers=auth_header(oper_token))
    assert r.status_code == 200
    history = r.json()
    assert all("mensaje secreto" not in h["question"] for h in history)


def test_history_filter_by_session(mock_llm):
    token = get_token("admin", "Admin123!")
    r1 = send_message(token, "sesión uno")
    sid1 = r1.json()["session_id"]

    send_message(token, "sesión dos")

    r = client.get(f"/chatbot/history?session_id={sid1}", headers=auth_header(token))
    history = r.json()
    assert all(h["session_id"] == sid1 for h in history)
    assert any("sesión uno" in h["question"] for h in history)


# ---- Tests de autenticación y seguridad ----

def test_message_requires_auth():
    r = client.post("/chatbot/message", json={"message": "test"})
    assert r.status_code == 401


def test_history_requires_auth():
    r = client.get("/chatbot/history")
    assert r.status_code == 401


# ---- Test de notificación por pregunta no resuelta ----

def test_unresolved_question_notifies_superior(mock_llm):
    """Cuando el LLM responde que no tiene información, notifica al superior."""
    mock_llm.invoke.return_value.content = UNRESOLVED_ANSWER

    # operador_a1 (superior = supervisor_a)
    token = get_token("operador_a1", "Oper123!")
    send_message(token, "¿tienes el artículo XYZ-9999?")

    db = SessionLocal()
    sup = db.query(models.User).filter_by(username="supervisor_a").first()
    # Reset supervisor_a por si está bloqueado
    if sup.is_locked:
        sup.is_locked = False
        sup.failed_attempts = 0
        db.commit()
        db.refresh(sup)

    notif = db.query(models.Notification).filter_by(
        recipient_user_id=sup.id, type="chat_unresolved"
    ).first()
    assert notif is not None
    assert "XYZ-9999" in notif.message or "operador" in notif.message.lower()
    db.close()
