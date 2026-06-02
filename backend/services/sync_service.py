"""Sync service — pulls stock from warehouse agents, updates SQLite."""
import httpx
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from backend import models
from backend.database import SessionLocal


def _notify_admin_sync_error(db: Session, warehouse: models.Warehouse, error: str):
    admin = (
        db.query(models.User)
        .join(models.Role)
        .filter(models.Role.name == "admin", models.User.is_active == True)
        .first()
    )
    if admin:
        db.add(models.Notification(
            recipient_user_id=admin.id,
            type="sync_error",
            message=f"Error de sincronización en {warehouse.name}: {error[:200]}",
        ))


def _notify_low_stock(db: Session, warehouse: models.Warehouse, stock: models.Stock):
    recipients = (
        db.query(models.User)
        .join(models.Role)
        .filter(
            models.Role.hierarchy_level <= 2,
            models.User.is_active == True,
        )
        .all()
    )
    for user in recipients:
        db.add(models.Notification(
            recipient_user_id=user.id,
            type="stock_low",
            message=(
                f"Stock bajo en {warehouse.name}: {stock.product_name} "
                f"({stock.quantity} {stock.unit}, mínimo {stock.min_quantity})"
            ),
        ))


def _upsert_stock(db: Session, warehouse: models.Warehouse, item: dict) -> int:
    existing = (
        db.query(models.Stock)
        .filter_by(warehouse_id=warehouse.id, product_code=item["product_code"])
        .first()
    )
    now = datetime.now(UTC)

    if not existing:
        new_stock = models.Stock(
            warehouse_id=warehouse.id,
            product_code=item["product_code"],
            product_name=item["product_name"],
            category=item.get("category"),
            quantity=item.get("quantity", 0),
            min_quantity=item.get("min_quantity", 0),
            unit=item.get("unit", "unidad"),
            location_in_warehouse=item.get("location"),
            status=item.get("status", "disponible"),
            last_synced=now,
        )
        db.add(new_stock)
        db.flush()
        if new_stock.quantity <= new_stock.min_quantity and new_stock.min_quantity > 0:
            _notify_low_stock(db, warehouse, new_stock)
        return 1

    field_map = [
        ("product_name", "product_name"),
        ("quantity", "quantity"),
        ("min_quantity", "min_quantity"),
        ("unit", "unit"),
        ("location", "location_in_warehouse"),
        ("status", "status"),
    ]
    changed = False
    for item_key, db_attr in field_map:
        new_val = item.get(item_key)
        if new_val is None:
            continue
        old_val = getattr(existing, db_attr)
        if str(new_val) != str(old_val if old_val is not None else ""):
            db.add(models.StockHistory(
                product_id=existing.id,
                product_type="cantidad",
                warehouse_id=warehouse.id,
                changed_by=None,
                field_changed=db_attr,
                old_value=str(old_val),
                new_value=str(new_val),
            ))
            setattr(existing, db_attr, new_val)
            changed = True

    existing.last_synced = now

    if changed and existing.quantity <= existing.min_quantity and existing.min_quantity > 0:
        _notify_low_stock(db, warehouse, existing)

    return 1 if changed else 0


def _upsert_serial(db: Session, warehouse: models.Warehouse, item: dict) -> int:
    existing = (
        db.query(models.StockSerial)
        .filter_by(serial_number=item["serial_number"])
        .first()
    )
    now = datetime.now(UTC)

    if not existing:
        db.add(models.StockSerial(
            warehouse_id=warehouse.id,
            product_code=item["product_code"],
            serial_number=item["serial_number"],
            product_name=item["product_name"],
            category=item.get("category"),
            location_in_warehouse=item.get("location"),
            status=item.get("status", "disponible"),
            last_synced=now,
        ))
        return 1

    field_map = [
        ("product_name", "product_name"),
        ("location", "location_in_warehouse"),
        ("status", "status"),
    ]
    changed = False
    for item_key, db_attr in field_map:
        new_val = item.get(item_key)
        if new_val is None:
            continue
        old_val = getattr(existing, db_attr)
        if str(new_val) != str(old_val if old_val is not None else ""):
            db.add(models.StockHistory(
                product_id=existing.id,
                product_type="serie_unica",
                warehouse_id=warehouse.id,
                changed_by=None,
                field_changed=db_attr,
                old_value=str(old_val),
                new_value=str(new_val),
            ))
            setattr(existing, db_attr, new_val)
            changed = True

    existing.last_synced = now
    return 1 if changed else 0


def sync_warehouse(
    db: Session,
    warehouse: models.Warehouse,
    triggered_by: str = "scheduler",
) -> models.SyncLog:
    log = models.SyncLog(
        warehouse_id=warehouse.id,
        triggered_by=triggered_by,
        started_at=datetime.now(UTC),
        status="running",
        records_updated=0,
    )
    db.add(log)
    db.commit()

    try:
        resp = httpx.get(
            warehouse.agent_url,
            headers={"Authorization": f"Bearer {warehouse.agent_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])

        warehouse.is_online = True
        warehouse.last_seen = datetime.now(UTC)

        records_updated = 0
        for item in items:
            if item.get("type") == "cantidad":
                records_updated += _upsert_stock(db, warehouse, item)
            elif item.get("type") == "serie_unica":
                records_updated += _upsert_serial(db, warehouse, item)

        log.finished_at = datetime.now(UTC)
        log.status = "success"
        log.records_updated = records_updated
        db.commit()

    except Exception as exc:
        db.rollback()
        warehouse.is_online = False
        log.finished_at = datetime.now(UTC)
        log.status = "error"
        log.error_message = str(exc)[:500]
        db.commit()
        _notify_admin_sync_error(db, warehouse, str(exc))
        db.commit()

    return log


def sync_all(
    db: Session, triggered_by: str = "scheduler"
) -> list[models.SyncLog]:
    warehouses = db.query(models.Warehouse).all()
    return [sync_warehouse(db, wh, triggered_by) for wh in warehouses]


def run_scheduled_sync():
    """Entry point for APScheduler background thread."""
    db = SessionLocal()
    try:
        sync_all(db, triggered_by="scheduler")
    finally:
        db.close()
