"""Tests FASE 2 — Sync service y endpoints."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models

client = TestClient(app)


# ---- Fixtures ----

def get_token(username="admin", password="Admin123!"):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def make_mock_response(data):
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    mock.status_code = 200
    return mock


STOCK_A = [
    {"product_code": "P001", "product_name": "Filtro de aceite", "type": "cantidad",
     "category": "Filtros", "quantity": 50, "min_quantity": 10, "unit": "unidad",
     "location": "Estante B-3", "status": "disponible"},
    {"product_code": "P002", "product_name": "Correa de distribución", "type": "cantidad",
     "category": "Motor", "quantity": 4, "min_quantity": 5, "unit": "unidad",
     "location": "Estante A-1", "status": "disponible"},
    {"product_code": "P003", "product_name": "Bujías NGK", "type": "cantidad",
     "category": "Encendido", "quantity": 3, "min_quantity": 10, "unit": "juego",
     "location": "Estante C-2", "status": "disponible"},
    {"product_code": "P004", "product_name": "Aceite motor 5W30", "type": "cantidad",
     "category": "Lubricantes", "quantity": 18, "min_quantity": 5, "unit": "litro",
     "location": "Zona D", "status": "disponible"},
    {"product_code": "P007", "product_name": "Filtro hidráulico", "type": "cantidad",
     "category": "Filtros", "quantity": 15, "min_quantity": 3, "unit": "unidad",
     "location": "Estante D-4", "status": "disponible"},
    {"product_code": "ME-5HP", "product_name": "Motor eléctrico 5HP", "type": "serie_unica",
     "serial_number": "SN-2041", "category": "Motores", "location": "Zona C",
     "status": "disponible"},
    {"product_code": "ME-5HP", "product_name": "Motor eléctrico 5HP", "type": "serie_unica",
     "serial_number": "SN-2042", "category": "Motores", "location": "Zona C",
     "status": "disponible"},
]

STOCK_B = [
    {"product_code": "P001", "product_name": "Filtro de aceite", "type": "cantidad",
     "category": "Filtros", "quantity": 14, "min_quantity": 10, "unit": "unidad",
     "location": "Rack 1-A", "status": "disponible"},
    {"product_code": "P005", "product_name": "Pastillas de freno", "type": "cantidad",
     "category": "Frenos", "quantity": 0, "min_quantity": 8, "unit": "juego",
     "location": "Rack 2-B", "status": "dado_de_baja"},
    {"product_code": "P006", "product_name": "Amortiguador delantero", "type": "cantidad",
     "category": "Suspensión", "quantity": 6, "min_quantity": 2, "unit": "unidad",
     "location": "Zona E", "status": "disponible"},
    {"product_code": "COMP-2T", "product_name": "Compresor 2 toneladas", "type": "serie_unica",
     "serial_number": "SN-3001", "category": "Compresores", "location": "Zona F",
     "status": "disponible"},
    {"product_code": "COMP-2T", "product_name": "Compresor 2 toneladas", "type": "serie_unica",
     "serial_number": "SN-3002", "category": "Compresores", "location": "Zona F",
     "status": "disponible"},
]


@pytest.fixture(autouse=True)
def reset_state():
    """Restaura estado de stock y limpia logs antes de cada test."""
    db = SessionLocal()
    wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
    wh_b = db.query(models.Warehouse).filter_by(code="ALM-B").first()

    # Reset cantidades a valores del seed
    seed_qty_a = {"P001": 45, "P002": 8, "P003": 3, "P004": 22}
    for code, qty in seed_qty_a.items():
        s = db.query(models.Stock).filter_by(warehouse_id=wh_a.id, product_code=code).first()
        if s:
            s.quantity = qty

    seed_qty_b = {"P001": 12}
    for code, qty in seed_qty_b.items():
        s = db.query(models.Stock).filter_by(warehouse_id=wh_b.id, product_code=code).first()
        if s:
            s.quantity = qty

    # Eliminar P007 si fue insertado
    p007 = db.query(models.Stock).filter_by(warehouse_id=wh_a.id, product_code="P007").first()
    if p007:
        db.delete(p007)

    # Reset seriales
    sn2042 = db.query(models.StockSerial).filter_by(serial_number="SN-2042").first()
    if sn2042:
        sn2042.status = "en_reparacion"
    sn3002 = db.query(models.StockSerial).filter_by(serial_number="SN-3002").first()
    if sn3002:
        sn3002.status = "reservado"

    # Reset warehouse online status
    for wh in [wh_a, wh_b]:
        if wh:
            wh.is_online = True

    # Limpiar logs y notificaciones de sync
    db.query(models.SyncLog).delete()
    db.query(models.StockHistory).delete()
    db.query(models.Notification).filter(
        models.Notification.type.in_(["sync_error", "stock_low"])
    ).delete()

    db.commit()
    db.close()
    yield
    # Teardown: same reset so the last test in this file doesn't leave DB dirty
    db = SessionLocal()
    wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
    wh_b = db.query(models.Warehouse).filter_by(code="ALM-B").first()
    seed_qty_a = {"P001": 45, "P002": 8, "P003": 3, "P004": 22}
    for code, qty in seed_qty_a.items():
        s = db.query(models.Stock).filter_by(warehouse_id=wh_a.id, product_code=code).first()
        if s:
            s.quantity = qty
    seed_qty_b = {"P001": 12}
    for code, qty in seed_qty_b.items():
        s = db.query(models.Stock).filter_by(warehouse_id=wh_b.id, product_code=code).first()
        if s:
            s.quantity = qty
    p007 = db.query(models.Stock).filter_by(warehouse_id=wh_a.id, product_code="P007").first()
    if p007:
        db.delete(p007)
    sn2042 = db.query(models.StockSerial).filter_by(serial_number="SN-2042").first()
    if sn2042:
        sn2042.status = "en_reparacion"
    sn3002 = db.query(models.StockSerial).filter_by(serial_number="SN-3002").first()
    if sn3002:
        sn3002.status = "reservado"
    for wh in [wh_a, wh_b]:
        if wh:
            wh.is_online = True
    db.query(models.SyncLog).delete()
    db.query(models.StockHistory).delete()
    db.query(models.Notification).filter(
        models.Notification.type.in_(["sync_error", "stock_low"])
    ).delete()
    db.commit()
    db.close()


def mock_get_by_url(url, **kwargs):
    if "8001" in url:
        return make_mock_response(STOCK_A)
    return make_mock_response(STOCK_B)


# ---- Tests de sync_service ----

def test_sync_updates_stock_quantity():
    """P001 ALM-A pasa de 45 a 50 tras sync."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        from backend.services import sync_service
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        p001 = db.query(models.Stock).filter_by(warehouse_id=wh_a.id, product_code="P001").first()
        assert p001.quantity == 50
        db.close()


def test_sync_inserts_new_product():
    """P007 no existe en seed — debe insertarse tras sync."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        from backend.services import sync_service
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        p007 = db.query(models.Stock).filter_by(warehouse_id=wh_a.id, product_code="P007").first()
        assert p007 is not None
        assert p007.product_name == "Filtro hidráulico"
        assert p007.quantity == 15
        db.close()


def test_sync_records_stock_history():
    """Cambio de cantidad genera entrada en stock_history."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        from backend.services import sync_service
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        # P001: 45→50, P002: 8→4, P004: 22→18
        history = db.query(models.StockHistory).filter_by(
            warehouse_id=wh_a.id, field_changed="quantity"
        ).all()
        codes = {
            db.query(models.Stock).get(h.product_id).product_code
            for h in history
        }
        assert "P001" in codes
        assert "P002" in codes
        assert "P004" in codes
        db.close()


def test_sync_updates_serial_status():
    """SN-2042 pasa de en_reparacion a disponible."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        from backend.services import sync_service
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        sn = db.query(models.StockSerial).filter_by(serial_number="SN-2042").first()
        assert sn.status == "disponible"
        db.close()


def test_sync_marks_warehouse_online():
    """Sync exitoso → warehouse.is_online=True, last_seen actualizado."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        from backend.services import sync_service
        from datetime import datetime, UTC
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        before = wh_a.last_seen
        sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        db.refresh(wh_a)
        assert wh_a.is_online is True
        assert wh_a.last_seen >= before
        db.close()


def test_sync_writes_success_log():
    """Sync exitoso → SyncLog con status=success."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        from backend.services import sync_service
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        log = sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        assert log.status == "success"
        assert log.records_updated > 0
        assert log.finished_at is not None
        db.close()


def test_sync_offline_warehouse():
    """Warehouse offline → status=error, is_online=False."""
    def raise_connection_error(url, **kwargs):
        raise Exception("Connection refused")

    with patch("backend.services.sync_service.httpx.get", side_effect=raise_connection_error):
        from backend.services import sync_service
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        log = sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        db.refresh(wh_a)
        assert log.status == "error"
        assert "Connection refused" in log.error_message
        assert wh_a.is_online is False
        db.close()


def test_sync_notifies_admin_on_error():
    """Error de sync genera notificación al admin."""
    def raise_connection_error(url, **kwargs):
        raise Exception("Host unreachable")

    with patch("backend.services.sync_service.httpx.get", side_effect=raise_connection_error):
        from backend.services import sync_service
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        admin = db.query(models.User).join(models.Role).filter(models.Role.name == "admin").first()
        notif = db.query(models.Notification).filter_by(
            recipient_user_id=admin.id, type="sync_error"
        ).first()
        assert notif is not None
        assert "Almacén Norte" in notif.message
        db.close()


def test_sync_notifies_low_stock():
    """P002 cae a 4 (min=5) → notificación stock_low a admin y gestor."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        from backend.services import sync_service
        db = SessionLocal()
        wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
        sync_service.sync_warehouse(db, wh_a, triggered_by="test")
        low_notifs = db.query(models.Notification).filter_by(type="stock_low").all()
        assert len(low_notifs) > 0
        messages = [n.message for n in low_notifs]
        assert any("Correa de distribución" in m for m in messages)
        db.close()


def test_sync_all_runs_both_warehouses():
    """sync_all procesa ambos almacenes y retorna 2 logs."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        from backend.services import sync_service
        db = SessionLocal()
        logs = sync_service.sync_all(db, triggered_by="test")
        assert len(logs) == 2
        statuses = {log.status for log in logs}
        assert statuses == {"success"}
        db.close()


# ---- Tests de endpoints ----

def test_trigger_as_admin():
    """POST /sync/trigger como admin → 200 con logs."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        token = get_token("admin", "Admin123!")
        r = client.post("/sync/trigger", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert len(data["logs"]) == 2


def test_trigger_as_gestor_forbidden():
    """POST /sync/trigger como gestor → 403."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        token = get_token("gestor1", "Gestor123!")
        r = client.post("/sync/trigger", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


def test_status_as_admin():
    """GET /sync/status como admin → lista de almacenes."""
    token = get_token("admin", "Admin123!")
    r = client.get("/sync/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    warehouses = r.json()
    assert len(warehouses) == 2
    codes = {w["code"] for w in warehouses}
    assert codes == {"ALM-A", "ALM-B"}


def test_status_as_gestor():
    """GET /sync/status como gestor → 200 (tiene permiso)."""
    token = get_token("gestor1", "Gestor123!")
    r = client.get("/sync/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_status_as_operador_forbidden():
    """GET /sync/status como operador → 403."""
    token = get_token("operador_a1", "Oper123!")
    r = client.get("/sync/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_logs_as_admin():
    """GET /sync/logs como admin → lista (puede estar vacía)."""
    token = get_token("admin", "Admin123!")
    r = client.get("/sync/logs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_logs_as_gestor_forbidden():
    """GET /sync/logs como gestor → 403."""
    token = get_token("gestor1", "Gestor123!")
    r = client.get("/sync/logs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_logs_after_trigger():
    """Después de trigger, GET /sync/logs devuelve 2 entradas."""
    with patch("backend.services.sync_service.httpx.get", side_effect=mock_get_by_url):
        token = get_token("admin", "Admin123!")
        client.post("/sync/trigger", headers={"Authorization": f"Bearer {token}"})
        r = client.get("/sync/logs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()) == 2
