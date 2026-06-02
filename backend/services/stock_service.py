"""Stock service — role-based access, updates, history, notifications."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend import models

VALID_STATUSES = {"disponible", "reservado", "en_reparacion", "dado_de_baja"}


def get_accessible_warehouse_ids(db: Session, user: models.User) -> list[int]:
    if user.role.hierarchy_level <= 2:
        return [w.id for w in db.query(models.Warehouse).all()]
    return [user.warehouse_id] if user.warehouse_id else []


def _check_warehouse_access(accessible: list[int], warehouse_id: int):
    if warehouse_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a ese almacén",
        )


def get_stock(
    db: Session, user: models.User, warehouse_id: int | None = None
) -> list[models.Stock]:
    accessible = get_accessible_warehouse_ids(db, user)
    q = db.query(models.Stock).filter(models.Stock.warehouse_id.in_(accessible))
    if warehouse_id is not None:
        _check_warehouse_access(accessible, warehouse_id)
        q = q.filter(models.Stock.warehouse_id == warehouse_id)
    return q.all()


def get_serial_stock(
    db: Session, user: models.User, warehouse_id: int | None = None
) -> list[models.StockSerial]:
    accessible = get_accessible_warehouse_ids(db, user)
    q = db.query(models.StockSerial).filter(
        models.StockSerial.warehouse_id.in_(accessible)
    )
    if warehouse_id is not None:
        _check_warehouse_access(accessible, warehouse_id)
        q = q.filter(models.StockSerial.warehouse_id == warehouse_id)
    return q.all()


def _get_stock_item_or_403(
    db: Session, user: models.User, item_id: int
) -> models.Stock:
    accessible = get_accessible_warehouse_ids(db, user)
    item = db.query(models.Stock).filter(models.Stock.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")
    _check_warehouse_access(accessible, item.warehouse_id)
    return item


def _get_serial_item_or_403(
    db: Session, user: models.User, item_id: int
) -> models.StockSerial:
    accessible = get_accessible_warehouse_ids(db, user)
    item = db.query(models.StockSerial).filter(models.StockSerial.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")
    _check_warehouse_access(accessible, item.warehouse_id)
    return item


def update_stock_item(
    db: Session, user: models.User, item_id: int, data: dict
) -> models.Stock:
    item = _get_stock_item_or_403(db, user, item_id)
    updatable = {"quantity", "status", "location_in_warehouse", "min_quantity"}
    changes = []

    for field in updatable:
        if field in data and data[field] is not None:
            if field == "status" and data[field] not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Estado inválido: {data[field]}",
                )
            old_val = str(getattr(item, field))
            new_val = str(data[field])
            if old_val != new_val:
                changes.append((field, old_val, new_val))
                setattr(item, field, data[field])

    if changes:
        for field, old_val, new_val in changes:
            db.add(models.StockHistory(
                product_id=item.id,
                product_type="cantidad",
                warehouse_id=item.warehouse_id,
                changed_by=user.id,
                field_changed=field,
                old_value=old_val,
                new_value=new_val,
            ))
        db.commit()
        _notify_stock_modification(db, user, item, changes)
        db.commit()

    return item


def update_serial_item(
    db: Session, user: models.User, item_id: int, data: dict
) -> models.StockSerial:
    item = _get_serial_item_or_403(db, user, item_id)
    updatable = {"status", "location_in_warehouse"}
    changes = []

    for field in updatable:
        if field in data and data[field] is not None:
            if field == "status" and data[field] not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Estado inválido: {data[field]}",
                )
            old_val = str(getattr(item, field))
            new_val = str(data[field])
            if old_val != new_val:
                changes.append((field, old_val, new_val))
                setattr(item, field, data[field])

    if changes:
        for field, old_val, new_val in changes:
            db.add(models.StockHistory(
                product_id=item.id,
                product_type="serie_unica",
                warehouse_id=item.warehouse_id,
                changed_by=user.id,
                field_changed=field,
                old_value=old_val,
                new_value=new_val,
            ))
        db.commit()
        _notify_stock_modification(db, user, item, changes)
        db.commit()

    return item


def _find_superior(db: Session, user: models.User) -> models.User | None:
    level = user.role.hierarchy_level
    if level == 4:
        return (
            db.query(models.User).join(models.Role)
            .filter(
                models.Role.hierarchy_level == 3,
                models.User.warehouse_id == user.warehouse_id,
                models.User.is_active == True,
            ).first()
        )
    if level == 3:
        return (
            db.query(models.User).join(models.Role)
            .filter(models.Role.hierarchy_level == 2, models.User.is_active == True)
            .first()
        )
    if level == 2:
        return (
            db.query(models.User).join(models.Role)
            .filter(models.Role.hierarchy_level == 1, models.User.is_active == True)
            .first()
        )
    return None


def _notify_stock_modification(db: Session, user: models.User, item, changes: list):
    change_desc = ", ".join(f"{f}: {o}→{n}" for f, o, n in changes)
    message = (
        f"Modificación en '{item.product_name}' ({item.product_code}): "
        f"{change_desc}. Realizado por: {user.username}"
    )
    notified_ids: set[int] = set()

    if user.role.hierarchy_level > 1:
        admin = (
            db.query(models.User).join(models.Role)
            .filter(models.Role.hierarchy_level == 1, models.User.is_active == True)
            .first()
        )
        if admin:
            db.add(models.Notification(
                recipient_user_id=admin.id,
                type="stock_modification",
                message=message,
                related_user_id=user.id,
            ))
            notified_ids.add(admin.id)

    superior = _find_superior(db, user)
    if superior and superior.id not in notified_ids:
        db.add(models.Notification(
            recipient_user_id=superior.id,
            type="stock_modification",
            message=message,
            related_user_id=user.id,
        ))
