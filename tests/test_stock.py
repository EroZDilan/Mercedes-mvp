"""Tests FASE 4 — Stock API con control de acceso por rol."""
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
def warehouse_ids():
    db = SessionLocal()
    wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
    wh_b = db.query(models.Warehouse).filter_by(code="ALM-B").first()
    db.close()
    return wh_a.id, wh_b.id


@pytest.fixture(scope="module")
def item_ids():
    """Returns (item_a_id, item_b_id, serial_a_id, serial_b_id)."""
    db = SessionLocal()
    wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
    wh_b = db.query(models.Warehouse).filter_by(code="ALM-B").first()
    item_a = db.query(models.Stock).filter(
        models.Stock.warehouse_id == wh_a.id,
        models.Stock.status != "dado_de_baja",
    ).first()
    item_b = db.query(models.Stock).filter(
        models.Stock.warehouse_id == wh_b.id,
        models.Stock.status != "dado_de_baja",
    ).first()
    serial_a = db.query(models.StockSerial).filter_by(warehouse_id=wh_a.id).first()
    serial_b = db.query(models.StockSerial).filter_by(warehouse_id=wh_b.id).first()
    result = (item_a.id, item_b.id, serial_a.id, serial_b.id)
    db.close()
    return result


def _reset_stock_to_seed(db):
    """Reset stock quantities/statuses to seed values and clear related test artifacts."""
    wh_a = db.query(models.Warehouse).filter_by(code="ALM-A").first()
    wh_b = db.query(models.Warehouse).filter_by(code="ALM-B").first()
    seed_a = {"P001": (45, "disponible"), "P002": (8, "disponible"),
               "P003": (3, "disponible"), "P004": (22, "disponible")}
    seed_b = {"P001": (12, "disponible"), "P006": (6, "disponible")}
    for code, (qty, st) in seed_a.items():
        s = db.query(models.Stock).filter_by(warehouse_id=wh_a.id, product_code=code).first()
        if s:
            s.quantity, s.status = qty, st
    for code, (qty, st) in seed_b.items():
        s = db.query(models.Stock).filter_by(warehouse_id=wh_b.id, product_code=code).first()
        if s:
            s.quantity, s.status = qty, st
    sn2042 = db.query(models.StockSerial).filter_by(serial_number="SN-2042").first()
    if sn2042:
        sn2042.status = "en_reparacion"
    sn3002 = db.query(models.StockSerial).filter_by(serial_number="SN-3002").first()
    if sn3002:
        sn3002.status = "reservado"
    p007 = db.query(models.Stock).filter_by(warehouse_id=wh_a.id, product_code="P007").first()
    if p007:
        db.delete(p007)
    db.query(models.StockHistory).delete(synchronize_session=False)
    db.query(models.Notification).filter(
        models.Notification.type == "stock_modification"
    ).delete(synchronize_session=False)


@pytest.fixture(autouse=True)
def restore_stock():
    """Reset to seed before each test, restore again after."""
    db = SessionLocal()
    _reset_stock_to_seed(db)
    db.commit()
    db.close()

    yield

    db = SessionLocal()
    _reset_stock_to_seed(db)
    db.commit()
    db.close()


# ---- Tests: GET /stock — filtrado por rol ----

def test_admin_list_stock_sees_both_warehouses(warehouse_ids):
    wh_a_id, wh_b_id = warehouse_ids
    token = get_token("admin", "Admin123!")
    r = client.get("/stock", headers=auth_header(token))
    assert r.status_code == 200
    wh_ids_in_resp = {item["warehouse_id"] for item in r.json()}
    assert wh_a_id in wh_ids_in_resp
    assert wh_b_id in wh_ids_in_resp


def test_gestor_list_stock_sees_both_warehouses(warehouse_ids):
    wh_a_id, wh_b_id = warehouse_ids
    token = get_token("gestor1", "Gestor123!")
    r = client.get("/stock", headers=auth_header(token))
    assert r.status_code == 200
    wh_ids_in_resp = {item["warehouse_id"] for item in r.json()}
    assert wh_a_id in wh_ids_in_resp
    assert wh_b_id in wh_ids_in_resp


def test_supervisor_list_stock_only_own_warehouse(warehouse_ids):
    wh_a_id, wh_b_id = warehouse_ids
    token = get_token("supervisor_a", "Super123!")
    r = client.get("/stock", headers=auth_header(token))
    assert r.status_code == 200
    wh_ids_in_resp = {item["warehouse_id"] for item in r.json()}
    assert wh_a_id in wh_ids_in_resp
    assert wh_b_id not in wh_ids_in_resp


def test_operador_list_stock_only_own_warehouse(warehouse_ids):
    wh_a_id, wh_b_id = warehouse_ids
    token = get_token("operador_a1", "Oper123!")
    r = client.get("/stock", headers=auth_header(token))
    assert r.status_code == 200
    wh_ids_in_resp = {item["warehouse_id"] for item in r.json()}
    assert wh_a_id in wh_ids_in_resp
    assert wh_b_id not in wh_ids_in_resp


def test_operador_cannot_filter_by_other_warehouse(warehouse_ids):
    _wh_a_id, wh_b_id = warehouse_ids
    token = get_token("operador_a1", "Oper123!")
    r = client.get(f"/stock?warehouse_id={wh_b_id}", headers=auth_header(token))
    assert r.status_code == 403


def test_admin_can_filter_by_specific_warehouse(warehouse_ids):
    wh_a_id, _ = warehouse_ids
    token = get_token("admin", "Admin123!")
    r = client.get(f"/stock?warehouse_id={wh_a_id}", headers=auth_header(token))
    assert r.status_code == 200
    for item in r.json():
        assert item["warehouse_id"] == wh_a_id


# ---- Tests: GET /stock/{id} — acceso a item individual ----

def test_admin_can_get_item_from_any_warehouse(item_ids):
    item_a_id, item_b_id, _, _ = item_ids
    token = get_token("admin", "Admin123!")
    assert client.get(f"/stock/{item_a_id}", headers=auth_header(token)).status_code == 200
    assert client.get(f"/stock/{item_b_id}", headers=auth_header(token)).status_code == 200


def test_operador_cannot_get_item_from_other_warehouse(item_ids):
    _, item_b_id, _, _ = item_ids
    token = get_token("operador_a1", "Oper123!")
    r = client.get(f"/stock/{item_b_id}", headers=auth_header(token))
    assert r.status_code == 403


def test_supervisor_can_get_own_warehouse_item(item_ids):
    item_a_id, _, _, _ = item_ids
    token = get_token("supervisor_a", "Super123!")
    r = client.get(f"/stock/{item_a_id}", headers=auth_header(token))
    assert r.status_code == 200


# ---- Tests: GET /stock/serial — filtrado por rol ----

def test_supervisor_sees_only_own_serial_items(warehouse_ids):
    wh_a_id, wh_b_id = warehouse_ids
    token = get_token("supervisor_a", "Super123!")
    r = client.get("/stock/serial", headers=auth_header(token))
    assert r.status_code == 200
    wh_ids_in_resp = {item["warehouse_id"] for item in r.json()}
    assert wh_a_id in wh_ids_in_resp
    assert wh_b_id not in wh_ids_in_resp


def test_operador_cannot_get_serial_from_other_warehouse(item_ids):
    _, _, _, serial_b_id = item_ids
    token = get_token("operador_a1", "Oper123!")
    r = client.get(f"/stock/serial/{serial_b_id}", headers=auth_header(token))
    assert r.status_code == 403


# ---- Tests: PUT /stock/{id} — actualizar item ----

def test_supervisor_can_update_own_warehouse_item(item_ids):
    item_a_id, _, _, _ = item_ids
    token = get_token("supervisor_a", "Super123!")
    r = client.put(
        f"/stock/{item_a_id}",
        headers=auth_header(token),
        json={"location_in_warehouse": "Zona NUEVA"},
    )
    assert r.status_code == 200
    assert r.json()["location_in_warehouse"] == "Zona NUEVA"


def test_operador_can_update_own_warehouse_item(item_ids):
    item_a_id, _, _, _ = item_ids
    token = get_token("operador_a1", "Oper123!")
    r = client.put(
        f"/stock/{item_a_id}",
        headers=auth_header(token),
        json={"status": "reservado"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "reservado"


def test_operador_cannot_update_other_warehouse_item(item_ids):
    _, item_b_id, _, _ = item_ids
    token = get_token("operador_a1", "Oper123!")
    r = client.put(
        f"/stock/{item_b_id}",
        headers=auth_header(token),
        json={"quantity": 99},
    )
    assert r.status_code == 403


def test_stock_update_writes_history(item_ids):
    item_a_id, _, _, _ = item_ids
    db = SessionLocal()
    item = db.query(models.Stock).filter_by(id=item_a_id).first()
    original_qty = item.quantity
    admin_user = db.query(models.User).filter_by(username="admin").first()
    admin_id = admin_user.id
    db.close()

    token = get_token("admin", "Admin123!")
    new_qty = original_qty + 5
    r = client.put(
        f"/stock/{item_a_id}",
        headers=auth_header(token),
        json={"quantity": new_qty},
    )
    assert r.status_code == 200

    db = SessionLocal()
    history = db.query(models.StockHistory).filter(
        models.StockHistory.product_id == item_a_id,
        models.StockHistory.field_changed == "quantity",
        models.StockHistory.changed_by == admin_id,
    ).order_by(models.StockHistory.id.desc()).first()
    assert history is not None
    assert history.old_value == str(original_qty)
    assert history.new_value == str(new_qty)
    db.close()


def test_stock_update_notifies_superior_and_admin(item_ids):
    item_a_id, _, _, _ = item_ids
    token = get_token("operador_a1", "Oper123!")
    client.put(
        f"/stock/{item_a_id}",
        headers=auth_header(token),
        json={"status": "reservado"},
    )

    db = SessionLocal()
    admin = db.query(models.User).join(models.Role).filter(
        models.Role.hierarchy_level == 1
    ).first()
    supervisor = db.query(models.User).filter_by(username="supervisor_a").first()

    admin_notif = db.query(models.Notification).filter(
        models.Notification.recipient_user_id == admin.id,
        models.Notification.type == "stock_modification",
    ).first()
    sup_notif = db.query(models.Notification).filter(
        models.Notification.recipient_user_id == supervisor.id,
        models.Notification.type == "stock_modification",
    ).first()
    assert admin_notif is not None
    assert sup_notif is not None
    db.close()


def test_invalid_status_returns_422(item_ids):
    item_a_id, _, _, _ = item_ids
    token = get_token("admin", "Admin123!")
    r = client.put(
        f"/stock/{item_a_id}",
        headers=auth_header(token),
        json={"status": "estado_inventado"},
    )
    assert r.status_code == 422


# ---- Tests: PUT /stock/serial/{id} ----

def test_supervisor_can_update_serial_item(item_ids):
    _, _, serial_a_id, _ = item_ids
    token = get_token("supervisor_a", "Super123!")
    r = client.put(
        f"/stock/serial/{serial_a_id}",
        headers=auth_header(token),
        json={"status": "reservado"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "reservado"


def test_operador_cannot_update_serial_from_other_warehouse(item_ids):
    _, _, _, serial_b_id = item_ids
    token = get_token("operador_a1", "Oper123!")
    r = client.put(
        f"/stock/serial/{serial_b_id}",
        headers=auth_header(token),
        json={"status": "disponible"},
    )
    assert r.status_code == 403


# ---- Tests: autenticación ----

def test_stock_requires_auth():
    assert client.get("/stock").status_code == 401


def test_stock_serial_requires_auth():
    assert client.get("/stock/serial").status_code == 401
