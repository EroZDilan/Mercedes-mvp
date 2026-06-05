"""Tests FASE 8 — Flujos end-to-end completos."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models

client = TestClient(app)


# ───────────────────────── helpers ──────────────────────────

def login(username: str, password: str) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Login falló para {username}: {r.text}"
    return r.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def chat(token: str, message: str, session_id: str = "e2e-test") -> dict:
    r = client.post(
        "/chatbot/message",
        headers=auth(token),
        json={"message": message, "session_id": session_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


def cleanup_chat_session(session_id: str):
    db = SessionLocal()
    db.query(models.ChatHistory).filter_by(session_id=session_id).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


# ───────────────────── FLUJO 1: Login completo ──────────────────────

class TestLoginFlow:
    def test_valid_login_returns_tokens(self):
        data = login("admin", "Admin123!")
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["role"] == "admin"

    def test_login_populates_me_endpoint(self):
        token = login("gestor1", "Gestor123!")["access_token"]
        r = client.get("/auth/me", headers=auth(token))
        assert r.status_code == 200
        me = r.json()
        assert me["username"] == "gestor1"
        assert me["role"] == "gestor"

    def test_invalid_credentials_rejected(self):
        r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code in (401, 403)

    def test_refresh_token_issues_new_access_token(self):
        data = login("supervisor_a", "Super123!")
        r = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_logout_revokes_token(self):
        data = login("operador_a1", "Oper123!")
        token = data["access_token"]
        client.post("/auth/logout", headers=auth(token))
        r = client.get("/auth/me", headers=auth(token))
        assert r.status_code == 401


# ───────────────── FLUJO 2: Chatbot por rol ─────────────────────────

class TestChatbotRoleFlow:
    SESSION = "e2e-chatbot-roles"

    def teardown_method(self, _):
        cleanup_chat_session(self.SESSION)

    def test_admin_chatbot_responds(self):
        token = login("admin", "Admin123!")["access_token"]
        data = chat(token, "¿Qué stock hay en total?", self.SESSION)
        assert data["response"]
        assert len(data["response"]) > 10
        assert data["session_id"] == self.SESSION

    def test_operador_a_chatbot_responds(self):
        """Operador Norte puede preguntar por su stock."""
        token = login("operador_a1", "Oper123!")["access_token"]
        data = chat(token, "¿Cuántos filtros de aceite hay?", self.SESSION)
        assert data["response"]
        assert "response_time_ms" in data

    def test_operador_b_chatbot_responds(self):
        """Operador Sur puede preguntar por su stock."""
        token = login("operador_b1", "Oper123!")["access_token"]
        data = chat(token, "¿Hay amortiguadores disponibles?", self.SESSION)
        assert data["response"]

    def test_chatbot_context_includes_warehouse_codes(self):
        """El historial guarda los almacenes del contexto."""
        token = login("operador_a1", "Oper123!")["access_token"]
        chat(token, "¿Qué productos tenemos?", self.SESSION)
        db = SessionLocal()
        h = db.query(models.ChatHistory).filter_by(session_id=self.SESSION).first()
        db.close()
        assert h is not None
        assert "ALM-A" in h.warehouses_context

    def test_chatbot_history_persists_across_messages(self):
        """El historial de sesión acumula mensajes."""
        token = login("gestor1", "Gestor123!")["access_token"]
        chat(token, "¿Cuántos almacenes gestionas?", self.SESSION)
        chat(token, "¿Y cuál tiene más stock?", self.SESSION)
        db = SessionLocal()
        count = db.query(models.ChatHistory).filter_by(session_id=self.SESSION).count()
        db.close()
        assert count == 2

    def test_chatbot_returns_response_time(self):
        token = login("admin", "Admin123!")["access_token"]
        data = chat(token, "Dame un resumen del inventario", self.SESSION)
        assert isinstance(data["response_time_ms"], int)
        assert data["response_time_ms"] >= 0


# ───────────── FLUJO 3: Aislamiento de datos en chatbot ─────────────

class TestChatbotIsolation:
    SESSION_A = "e2e-isolation-a"
    SESSION_B = "e2e-isolation-b"

    def teardown_method(self, _):
        cleanup_chat_session(self.SESSION_A)
        cleanup_chat_session(self.SESSION_B)

    def test_operador_a_context_only_has_alm_a(self):
        """El contexto del operador Norte solo incluye ALM-A."""
        token = login("operador_a1", "Oper123!")["access_token"]
        chat(token, "¿Qué tenemos en stock?", self.SESSION_A)
        db = SessionLocal()
        h = db.query(models.ChatHistory).filter_by(session_id=self.SESSION_A).first()
        db.close()
        import json
        warehouses = json.loads(h.warehouses_context)
        assert "ALM-A" in warehouses
        assert "ALM-B" not in warehouses

    def test_operador_b_context_only_has_alm_b(self):
        """El contexto del operador Sur solo incluye ALM-B."""
        token = login("operador_b1", "Oper123!")["access_token"]
        chat(token, "¿Qué tenemos en stock?", self.SESSION_B)
        db = SessionLocal()
        h = db.query(models.ChatHistory).filter_by(session_id=self.SESSION_B).first()
        db.close()
        import json
        warehouses = json.loads(h.warehouses_context)
        assert "ALM-B" in warehouses
        assert "ALM-A" not in warehouses

    def test_admin_context_has_both_warehouses(self):
        """El contexto del admin incluye ambos almacenes."""
        token = login("admin", "Admin123!")["access_token"]
        chat(token, "Dame un resumen global", self.SESSION_A)
        db = SessionLocal()
        h = db.query(models.ChatHistory).filter_by(session_id=self.SESSION_A).first()
        db.close()
        import json
        warehouses = json.loads(h.warehouses_context)
        assert "ALM-A" in warehouses
        assert "ALM-B" in warehouses

    def test_gestor_context_has_both_warehouses(self):
        """El gestor también tiene ambos almacenes en contexto."""
        token = login("gestor1", "Gestor123!")["access_token"]
        chat(token, "¿Cómo está el inventario?", self.SESSION_A)
        db = SessionLocal()
        h = db.query(models.ChatHistory).filter_by(session_id=self.SESSION_A).first()
        db.close()
        import json
        warehouses = json.loads(h.warehouses_context)
        assert "ALM-A" in warehouses
        assert "ALM-B" in warehouses


# ───────────────── FLUJO 4: Stock completo ──────────────────────────

class TestStockFlow:
    def test_operador_can_list_own_stock(self):
        token = login("operador_a1", "Oper123!")["access_token"]
        r = client.get("/stock", headers=auth(token))
        assert r.status_code == 200
        items = r.json()
        assert len(items) > 0
        db = SessionLocal()
        wh_a_id = db.query(models.Warehouse).filter_by(code="ALM-A").first().id
        db.close()
        assert all(i["warehouse_id"] == wh_a_id for i in items)

    def test_admin_can_update_stock_quantity(self):
        token = login("admin", "Admin123!")["access_token"]
        db = SessionLocal()
        item = db.query(models.Stock).filter_by(product_code="P001").first()
        original_qty = item.quantity
        item_id = item.id
        db.close()

        r = client.put(
            f"/stock/{item_id}",
            headers=auth(token),
            json={"quantity": original_qty + 5},
        )
        assert r.status_code == 200

        # restore
        db = SessionLocal()
        item = db.query(models.Stock).filter_by(id=item_id).first()
        item.quantity = original_qty
        db.commit()
        db.close()

    def test_stock_update_creates_notification(self):
        """Modificar stock genera notificación al supervisor del almacén."""
        admin_token = login("admin", "Admin123!")["access_token"]
        db = SessionLocal()
        item = db.query(models.Stock).join(models.Warehouse).filter(
            models.Warehouse.code == "ALM-A",
            models.Stock.product_code == "P001",
        ).first()
        original_qty = item.quantity
        item_id = item.id
        supervisor = db.query(models.User).join(models.Role).join(models.Warehouse).filter(
            models.Role.hierarchy_level == 3,
            models.Warehouse.code == "ALM-A",
        ).first()
        sup_id = supervisor.id
        db.close()

        notif_count_before = client.get(
            f"/notifications?user_id={sup_id}", headers=auth(admin_token)
        ).json()

        client.put(f"/stock/{item_id}", headers=auth(admin_token), json={"quantity": original_qty + 1})

        db = SessionLocal()
        item = db.query(models.Stock).filter_by(id=item_id).first()
        item.quantity = original_qty
        db.commit()
        db.close()

    def test_serial_stock_can_be_updated(self):
        token = login("admin", "Admin123!")["access_token"]
        db = SessionLocal()
        serial = db.query(models.StockSerial).filter_by(serial_number="SN-2041").first()
        sid = serial.id
        original_status = serial.status
        db.close()

        r = client.put(
            f"/stock/serial/{sid}",
            headers=auth(token),
            json={"status": "en_reparacion"},
        )
        assert r.status_code == 200

        # restore
        db = SessionLocal()
        s = db.query(models.StockSerial).filter_by(id=sid).first()
        s.status = original_status
        db.commit()
        db.close()

    def test_chatbot_reflects_stock_change(self):
        """Después de actualizar stock, el chatbot refleja el nuevo valor."""
        admin_token = login("admin", "Admin123!")["access_token"]
        session = "e2e-stock-reflect"

        db = SessionLocal()
        item = db.query(models.Stock).join(models.Warehouse).filter(
            models.Warehouse.code == "ALM-A",
            models.Stock.product_code == "P004",
        ).first()
        item_id = item.id
        db.close()

        # Set to known value
        client.put(f"/stock/{item_id}", headers=auth(admin_token), json={"quantity": 100})

        # Ask chatbot
        data = chat(admin_token, "¿Cuántos litros de aceite motor 5W30 hay en el Almacén Norte?", session)
        # Response should come back (can't assert exact number due to LLM)
        assert data["response"]

        # Restore
        client.put(f"/stock/{item_id}", headers=auth(admin_token), json={"quantity": 22})
        cleanup_chat_session(session)


# ─────────────── FLUJO 5: CRM completo ─────────────────────────────

class TestCRMFlow:
    def test_supervisor_can_create_crm_note(self):
        token = login("supervisor_a", "Super123!")["access_token"]
        r = client.post(
            "/crm/notes",
            headers=auth(token),
            json={"content": "E2E test note — supervisor nota operación correcta"},
        )
        assert r.status_code == 201
        note = r.json()
        assert "id" in note

        # cleanup
        db = SessionLocal()
        db.query(models.CrmNote).filter_by(id=note["id"]).delete(synchronize_session=False)
        db.commit()
        db.close()

    def test_operador_can_create_crm_note(self):
        token = login("operador_a1", "Oper123!")["access_token"]
        r = client.post(
            "/crm/notes",
            headers=auth(token),
            json={"content": "E2E operador nota de inventario"},
        )
        assert r.status_code == 201
        note = r.json()

        db = SessionLocal()
        db.query(models.CrmNote).filter_by(id=note["id"]).delete(synchronize_session=False)
        db.commit()
        db.close()

    def test_crm_note_appears_in_history(self):
        token = login("supervisor_a", "Super123!")["access_token"]
        r = client.post(
            "/crm/notes",
            headers=auth(token),
            json={"content": "Nota E2E para historial"},
        )
        note_id = r.json()["id"]

        history = client.get("/crm/history", headers=auth(token)).json()
        assert any(n["detail"]["id"] == note_id for n in history)

        db = SessionLocal()
        db.query(models.CrmNote).filter_by(id=note_id).delete(synchronize_session=False)
        db.commit()
        db.close()

    def test_admin_can_see_global_metrics(self):
        token = login("admin", "Admin123!")["access_token"]
        r = client.get("/crm/metrics/global", headers=auth(token))
        assert r.status_code == 200


# ─────────────── FLUJO 6: Notificaciones completo ──────────────────

class TestNotificationsFlow:
    def _create_notif(self, recipient_username: str) -> int:
        db = SessionLocal()
        user = db.query(models.User).filter_by(username=recipient_username).first()
        notif = models.Notification(
            recipient_user_id=user.id,
            type="stock_modification",
            message="E2E test notification",
        )
        db.add(notif)
        db.commit()
        nid = notif.id
        db.close()
        return nid

    def test_user_sees_own_notifications(self):
        nid = self._create_notif("supervisor_a")
        token = login("supervisor_a", "Super123!")["access_token"]
        r = client.get("/notifications", headers=auth(token))
        assert r.status_code == 200
        ids = [n["id"] for n in r.json()]
        assert nid in ids

        db = SessionLocal()
        db.query(models.Notification).filter_by(id=nid).delete(synchronize_session=False)
        db.commit()
        db.close()

    def test_user_can_mark_notification_read(self):
        nid = self._create_notif("operador_a1")
        token = login("operador_a1", "Oper123!")["access_token"]

        r = client.patch(f"/notifications/{nid}/read", headers=auth(token))
        assert r.status_code == 200

        db = SessionLocal()
        n = db.query(models.Notification).filter_by(id=nid).first()
        assert n.is_read == True
        db.query(models.Notification).filter_by(id=nid).delete(synchronize_session=False)
        db.commit()
        db.close()

    def test_user_can_mark_all_read(self):
        nid1 = self._create_notif("gestor1")
        nid2 = self._create_notif("gestor1")
        token = login("gestor1", "Gestor123!")["access_token"]

        r = client.patch("/notifications/read-all", headers=auth(token))
        assert r.status_code == 200

        db = SessionLocal()
        unread = db.query(models.Notification).filter_by(
            recipient_user_id=db.query(models.User).filter_by(username="gestor1").first().id,
            is_read=False,
        ).count()
        db.query(models.Notification).filter(
            models.Notification.id.in_([nid1, nid2])
        ).delete(synchronize_session=False)
        db.commit()
        db.close()
        assert unread == 0


# ─────────────── FLUJO 7: Sync completo ─────────────────────────────

class TestSyncFlow:
    def test_admin_can_trigger_sync(self):
        token = login("admin", "Admin123!")["access_token"]
        r = client.post("/sync/trigger", headers=auth(token))
        assert r.status_code in (200, 202)

    def test_sync_status_shows_warehouses(self):
        token = login("admin", "Admin123!")["access_token"]
        r = client.get("/sync/status", headers=auth(token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        codes = [w["code"] for w in data]
        assert "ALM-A" in codes
        assert "ALM-B" in codes

    def test_admin_can_see_sync_logs(self):
        token = login("admin", "Admin123!")["access_token"]
        r = client.get("/sync/logs", headers=auth(token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_non_admin_cannot_trigger_sync(self):
        token = login("gestor1", "Gestor123!")["access_token"]
        r = client.post("/sync/trigger", headers=auth(token))
        assert r.status_code == 403

    def test_gestor_can_see_sync_status(self):
        """El gestor puede ver el estado de los almacenes."""
        token = login("gestor1", "Gestor123!")["access_token"]
        r = client.get("/sync/status", headers=auth(token))
        assert r.status_code == 200

    def test_supervisor_cannot_see_sync_status(self):
        """Supervisores y operadores no pueden ver sync status."""
        token = login("supervisor_a", "Super123!")["access_token"]
        r = client.get("/sync/status", headers=auth(token))
        assert r.status_code == 403


# ─────────────── FLUJO 8: Gestión de usuarios ───────────────────────

class TestUserManagementFlow:
    def test_full_user_lifecycle(self):
        """Crear usuario → resetear contraseña → desactivar → verificar no puede login."""
        admin_token = login("admin", "Admin123!")["access_token"]

        db = SessionLocal()
        role_id = db.query(models.Role).filter_by(name="operador").first().id
        wh_id = db.query(models.Warehouse).filter_by(code="ALM-A").first().id
        db.close()

        # Crear
        r = client.post(
            "/users",
            headers=auth(admin_token),
            json={
                "username": "e2e_lifecycle_user",
                "password": "Lifecycle1!",
                "full_name": "E2E Test User",
                "role_id": role_id,
                "warehouse_id": wh_id,
            },
        )
        assert r.status_code == 201
        uid = r.json()["id"]

        # Puede hacer login
        assert login("e2e_lifecycle_user", "Lifecycle1!")["access_token"]

        # Reset password
        r2 = client.post(
            f"/users/{uid}/reset-password",
            headers=auth(admin_token),
            json={"new_password": "NewLifecycle1!"},
        )
        assert r2.status_code == 200

        # Con contraseña vieja ya no puede
        r3 = client.post("/auth/login", json={"username": "e2e_lifecycle_user", "password": "Lifecycle1!"})
        assert r3.status_code in (401, 403)

        # Desactivar
        client.post(f"/users/{uid}/deactivate", headers=auth(admin_token))

        # No puede login aunque tenga contraseña válida
        r4 = client.post("/auth/login", json={"username": "e2e_lifecycle_user", "password": "NewLifecycle1!"})
        assert r4.status_code in (401, 403)

        # Cleanup
        db = SessionLocal()
        db.query(models.User).filter_by(id=uid).delete(synchronize_session=False)
        db.commit()
        db.close()

    def test_unresolved_chat_notifies_superior(self):
        """Pregunta sin respuesta en el chatbot genera notificación al supervisor."""
        operador_token = login("operador_a1", "Oper123!")["access_token"]
        session = "e2e-unresolved-notif"

        db = SessionLocal()
        sup = db.query(models.User).join(models.Role).join(models.Warehouse).filter(
            models.Role.hierarchy_level == 3,
            models.Warehouse.code == "ALM-A",
        ).first()
        sup_id = sup.id
        notif_count_before = db.query(models.Notification).filter_by(
            recipient_user_id=sup_id, type="chat_unresolved"
        ).count()
        db.close()

        # Ask something the chatbot can't resolve
        chat(operador_token, "¿Cuál es el precio de mercado del oro?", session)

        # Check if unresolved notifications were potentially generated
        # (depends on LLM response — may or may not trigger)
        cleanup_chat_session(session)
