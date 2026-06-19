"""Tests for InvenTree sync — verifies actions trigger the right sync calls."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def admin_token(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def gestor_token(client):
    r = client.post("/auth/login", json={"username": "gestor1", "password": "Gestor123!"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── inventree_service unit tests ──────────────────────────────────────────────

class TestInventreeServiceHelpers:

    def test_status_map_covers_all_backend_statuses(self):
        from backend.services.inventree_service import STATUS_MAP
        expected = {"disponible", "en_reparacion", "reservado", "dado_de_baja"}
        assert set(STATUS_MAP.keys()) == expected

    def test_warehouse_keyword_map(self):
        from backend.services.inventree_service import WAREHOUSE_KEYWORD
        assert WAREHOUSE_KEYWORD["ALM-A"] == "Norte"
        assert WAREHOUSE_KEYWORD["ALM-B"] == "Sur"

    def test_sync_skipped_when_no_token(self):
        from backend.services import inventree_service
        with patch("backend.services.inventree_service.settings") as mock_cfg:
            mock_cfg.inventree_token = ""
            with patch("backend.services.inventree_service._post") as mock_post:
                inventree_service.sync_transfer("Filtro de aceite", "ALM-A", "ALM-B", 5)
                mock_post.assert_not_called()

    def test_sync_transfer_error_does_not_raise(self):
        from backend.services import inventree_service
        with patch("backend.services.inventree_service.settings") as mock_cfg:
            mock_cfg.inventree_token = "fake-token"
            with patch("backend.services.inventree_service._get", side_effect=Exception("connection refused")):
                # Should not raise — errors are swallowed
                inventree_service.sync_transfer("Filtro de aceite", "ALM-A", "ALM-B", 5)

    def test_sync_status_change_error_does_not_raise(self):
        from backend.services import inventree_service
        with patch("backend.services.inventree_service.settings") as mock_cfg:
            mock_cfg.inventree_token = "fake-token"
            with patch("backend.services.inventree_service._get", side_effect=Exception("timeout")):
                inventree_service.sync_status_change("Filtro de aceite", "ALM-A", "reservado")

    def test_sync_create_product_error_does_not_raise(self):
        from backend.services import inventree_service
        with patch("backend.services.inventree_service.settings") as mock_cfg:
            mock_cfg.inventree_token = "fake-token"
            with patch("backend.services.inventree_service._get", side_effect=Exception("timeout")):
                inventree_service.sync_create_product("Nuevo producto", "ALM-A", "Filtros", 10)

    def test_sync_deactivate_product_error_does_not_raise(self):
        from backend.services import inventree_service
        with patch("backend.services.inventree_service.settings") as mock_cfg:
            mock_cfg.inventree_token = "fake-token"
            with patch("backend.services.inventree_service._get", side_effect=Exception("timeout")):
                inventree_service.sync_deactivate_product("Filtro de aceite")


class TestInventreeSyncCalledOnAction:
    """Verify that confirmed actions trigger the right inventree_service call."""

    def _confirm_action(self, client, token_str, auth_headers):
        r = client.post("/actions/confirm", json={"token": token_str}, headers=auth_headers)
        return r

    def test_transfer_calls_inventree_sync(self, client, gestor_token):
        from backend.services import inventree_service
        with patch.object(inventree_service, "sync_transfer") as mock_sync:
            db = SessionLocal()
            try:
                from backend.services.action_service import create_action_token
                from backend import models
                user = db.query(models.User).filter_by(username="gestor1").first()
                token = create_action_token(db, user.id, {
                    "action_type": "transfer",
                    "params": {
                        "from_warehouse": "ALM-A",
                        "to_warehouse": "ALM-B",
                        "product_code": "P001",
                        "quantity": 1,
                    }
                })
            finally:
                db.close()

            r = client.post("/actions/confirm", json={"action_token": token},
                            headers=_auth(gestor_token))
            assert r.status_code == 200
            mock_sync.assert_called_once()
            call_args = mock_sync.call_args[0]
            assert call_args[1] == "ALM-A"
            assert call_args[2] == "ALM-B"
            assert call_args[3] == 1

    def test_status_change_calls_inventree_sync(self, client, gestor_token):
        from backend.services import inventree_service
        with patch.object(inventree_service, "sync_status_change") as mock_sync:
            db = SessionLocal()
            try:
                from backend.services.action_service import create_action_token
                user = db.query(models.User).filter_by(username="gestor1").first()
                token = create_action_token(db, user.id, {
                    "action_type": "status_change",
                    "params": {
                        "product_identifier": "P001",
                        "warehouse_code": "ALM-A",
                        "new_status": "reservado",
                    }
                })
            finally:
                db.close()

            r = client.post("/actions/confirm", json={"action_token": token},
                            headers=_auth(gestor_token))
            assert r.status_code == 200
            mock_sync.assert_called_once()
            call_args = mock_sync.call_args[0]
            assert call_args[2] == "reservado"

    def test_delete_product_calls_inventree_sync(self, client, gestor_token):
        from backend.services import inventree_service
        with patch.object(inventree_service, "sync_deactivate_product") as mock_sync:
            db = SessionLocal()
            try:
                from backend.services.action_service import create_action_token
                user = db.query(models.User).filter_by(username="gestor1").first()
                token = create_action_token(db, user.id, {
                    "action_type": "delete_product",
                    "params": {
                        "warehouse_code": "ALM-A",
                        "product_code": "P001",
                    }
                })
            finally:
                db.close()

            r = client.post("/actions/confirm", json={"action_token": token},
                            headers=_auth(gestor_token))
            assert r.status_code == 200
            mock_sync.assert_called_once()

    def test_create_product_calls_inventree_sync(self, client, gestor_token):
        from backend.services import inventree_service
        with patch.object(inventree_service, "sync_create_product") as mock_sync:
            db = SessionLocal()
            try:
                from backend.services.action_service import create_action_token
                user = db.query(models.User).filter_by(username="gestor1").first()
                token = create_action_token(db, user.id, {
                    "action_type": "create_product",
                    "params": {
                        "warehouse_code": "ALM-A",
                        "product_code": "P999",
                        "product_name": "Producto test sync",
                        "category": "Filtros",
                        "quantity": 5,
                        "min_quantity": 1,
                        "unit": "unidad",
                        "location": "Estante X",
                    }
                })
            finally:
                db.close()

            r = client.post("/actions/confirm", json={"action_token": token},
                            headers=_auth(gestor_token))
            assert r.status_code == 200
            mock_sync.assert_called_once()

    def test_user_actions_do_not_call_stock_sync(self):
        """User deactivate should NOT call stock sync functions — direct unit test."""
        from backend.services import inventree_service, action_service
        db = SessionLocal()
        try:
            admin = db.query(models.User).filter_by(username="admin").first()
            # Ensure operador_b1 is active so deactivate can run
            operador = db.query(models.User).filter_by(username="operador_b1").first()
            if operador and not operador.is_active:
                operador.is_active = True
                db.commit()

            with patch.object(inventree_service, "sync_transfer") as mock_transfer, \
                 patch.object(inventree_service, "sync_status_change") as mock_status, \
                 patch.object(inventree_service, "sync_deactivate_user"):
                action_service.execute_action(db, admin, {
                    "action_type": "deactivate_user",
                    "params": {"username": "operador_b1"},
                })
                mock_transfer.assert_not_called()
                mock_status.assert_not_called()
        finally:
            db.close()


# ── CRM related_to filter test ────────────────────────────────────────────────

class TestCrmRelatedToFilter:

    def test_filter_notes_by_related_to(self, client, admin_token):
        headers = _auth(admin_token)
        # Create two notes with different related_to
        client.post("/crm/notes", json={"content": "Nota proveedor Bosch", "related_to": "PROV:Bosch"},
                    headers=headers)
        client.post("/crm/notes", json={"content": "Nota vehículo", "related_to": "MAT:1234-ABC"},
                    headers=headers)

        r = client.get("/crm/notes?related_to=PROV:Bosch", headers=headers)
        assert r.status_code == 200
        notes = r.json()
        assert all(n["related_to"] == "PROV:Bosch" for n in notes)
        assert any("Bosch" in n["content"] for n in notes)

    def test_filter_by_related_to_returns_empty_if_no_match(self, client, admin_token):
        r = client.get("/crm/notes?related_to=PROV:Inexistente", headers=_auth(admin_token))
        assert r.status_code == 200
        assert r.json() == []
