"""Cola de operaciones offline.

Cada acción confirmada se registra aquí. Cuando el nodo es cliente
y recupera la conexión, envía la cola al servidor central para que
las aplique en orden cronológico y detecte conflictos.
"""
import json
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from backend import models
from backend.config import settings

logger = logging.getLogger(__name__)


def enqueue(db: Session, operation_type: str, payload: dict, user_id: int) -> models.OperationQueue:
    """Registra una operación en la cola local."""
    entry = models.OperationQueue(
        node_id=settings.node_id,
        operation_type=operation_type,
        payload=json.dumps(payload, ensure_ascii=False),
        op_timestamp=datetime.now(UTC),
    )
    db.add(entry)
    db.flush()
    return entry


def get_pending(db: Session) -> list[models.OperationQueue]:
    return (
        db.query(models.OperationQueue)
        .filter_by(status="pending")
        .order_by(models.OperationQueue.op_timestamp)
        .all()
    )


def pending_count(db: Session) -> int:
    return db.query(models.OperationQueue).filter_by(status="pending").count()


def push_to_central(db: Session) -> dict:
    """Envía las operaciones pendientes al servidor central.

    Solo ejecuta si NODE_ROLE=client y CENTRAL_SERVER_URL está configurada.
    Retorna un resumen: {sent, synced, conflicts, errors}.
    """
    if settings.node_role != "client" or not settings.central_server_url:
        return {"sent": 0, "synced": 0, "conflicts": 0, "errors": 0}

    pending = get_pending(db)
    if not pending:
        return {"sent": 0, "synced": 0, "conflicts": 0, "errors": 0}

    ops = [
        {
            "id": op.id,
            "node_id": op.node_id,
            "operation_type": op.operation_type,
            "payload": json.loads(op.payload),
            "op_timestamp": op.op_timestamp.isoformat(),
        }
        for op in pending
    ]

    try:
        resp = httpx.post(
            f"{settings.central_server_url.rstrip('/')}/sync/queue",
            json={"operations": ops},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()

        synced_ids = set(result.get("synced_ids", []))
        conflict_ids = set(result.get("conflict_ids", []))
        now = datetime.now(UTC)

        for op in pending:
            if op.id in synced_ids:
                op.status = "synced"
                op.synced_at = now
            elif op.id in conflict_ids:
                op.status = "conflict"
                details = result.get("conflict_details", {})
                op.conflict_detail = details.get(str(op.id), "Conflicto detectado en servidor")
        db.commit()

        logger.info(
            "[Queue] Sync completada: %d enviadas, %d sincronizadas, %d conflictos",
            len(ops), len(synced_ids), len(conflict_ids),
        )
        return {
            "sent": len(ops),
            "synced": len(synced_ids),
            "conflicts": len(conflict_ids),
            "errors": 0,
        }

    except httpx.ConnectError:
        logger.debug("[Queue] Servidor central no disponible — reintentará después")
        return {"sent": 0, "synced": 0, "conflicts": 0, "errors": 1}
    except Exception as exc:
        logger.warning("[Queue] Error al sincronizar con servidor central: %s", exc)
        return {"sent": 0, "synced": 0, "conflicts": 0, "errors": 1}


def receive_from_client(db: Session, operations: list[dict]) -> dict:
    """Procesa operaciones recibidas de un nodo cliente.

    Aplica las operaciones en orden de timestamp. Si hay conflicto
    (el recurso ya fue modificado por otro nodo con timestamp anterior),
    marca la operación como conflicto y lo registra.

    Returns dict con synced_ids, conflict_ids, conflict_details.
    """
    synced_ids: list[int] = []
    conflict_ids: list[int] = []
    conflict_details: dict[str, str] = {}

    for op in sorted(operations, key=lambda o: o["op_timestamp"]):
        op_id = op["id"]
        op_type = op["operation_type"]
        payload = op["payload"]
        op_ts = datetime.fromisoformat(op["op_timestamp"])

        conflict = _check_conflict(db, op_type, payload, op_ts)
        if conflict:
            conflict_ids.append(op_id)
            conflict_details[str(op_id)] = conflict
            logger.warning("[Queue] Conflicto en op %d (%s): %s", op_id, op_type, conflict)
            continue

        try:
            _apply_operation(db, op_type, payload, op["node_id"])
            synced_ids.append(op_id)
            db.commit()
        except Exception as exc:
            db.rollback()
            conflict_ids.append(op_id)
            conflict_details[str(op_id)] = f"Error al aplicar: {exc}"
            logger.warning("[Queue] Error aplicando op %d: %s", op_id, exc)

    return {
        "synced_ids": synced_ids,
        "conflict_ids": conflict_ids,
        "conflict_details": conflict_details,
    }


def _check_conflict(db: Session, op_type: str, payload: dict, op_ts: datetime) -> str | None:
    """Detecta si una operación entrante entra en conflicto con el estado actual.

    Regla: si el recurso fue modificado en el servidor DESPUÉS del timestamp
    de la operación del cliente, hay conflicto.
    Retorna None si no hay conflicto, o una descripción del conflicto.
    """
    if op_type == "transfer":
        wh = db.query(models.Warehouse).filter_by(code=payload.get("from_warehouse")).first()
        if not wh:
            return f"Almacén '{payload.get('from_warehouse')}' no encontrado."
        stock = db.query(models.Stock).filter_by(
            warehouse_id=wh.id, product_code=payload.get("product_code")
        ).first()
        if stock and stock.last_synced and stock.last_synced.replace(tzinfo=UTC) > op_ts:
            if stock.quantity < int(payload.get("quantity", 0)):
                return (
                    f"Conflicto de stock: {stock.product_name} fue modificado después de tu operación. "
                    f"Stock actual: {stock.quantity}, pedido: {payload.get('quantity')}. "
                    "Ten en cuenta que el producto puede no estar disponible."
                )

    elif op_type == "sale":
        serial = payload.get("serial_number", "")
        if serial:
            wh = db.query(models.Warehouse).filter_by(code=payload.get("warehouse_code")).first()
            if wh:
                item = db.query(models.StockSerial).filter_by(
                    warehouse_id=wh.id, serial_number=serial
                ).first()
                if item and item.status != "disponible":
                    return (
                        f"Conflicto: el ítem serializado {serial} ya no está disponible "
                        f"(estado actual: {item.status}). "
                        "Ten en cuenta que el producto puede no estar disponible."
                    )

    return None


def _apply_operation(db: Session, op_type: str, payload: dict, node_id: str):
    """Aplica una operación recibida de un cliente al servidor central."""
    if op_type == "transfer":
        from_wh = db.query(models.Warehouse).filter_by(code=payload["from_warehouse"]).first()
        to_wh = db.query(models.Warehouse).filter_by(code=payload["to_warehouse"]).first()
        if not from_wh or not to_wh:
            raise ValueError("Almacén no encontrado.")
        qty = int(payload["quantity"])
        src = db.query(models.Stock).filter_by(
            warehouse_id=from_wh.id, product_code=payload["product_code"]
        ).first()
        if not src or src.quantity < qty:
            raise ValueError("Stock insuficiente para aplicar la transferencia.")
        src.quantity -= qty
        dst = db.query(models.Stock).filter_by(
            warehouse_id=to_wh.id, product_code=payload["product_code"]
        ).first()
        if dst:
            dst.quantity += qty
        else:
            db.add(models.Stock(
                warehouse_id=to_wh.id,
                product_code=src.product_code,
                product_name=src.product_name,
                category=src.category,
                quantity=qty,
                min_quantity=src.min_quantity,
                unit=src.unit,
                status="disponible",
            ))

    elif op_type == "sale":
        wh = db.query(models.Warehouse).filter_by(code=payload["warehouse_code"]).first()
        if not wh:
            raise ValueError("Almacén no encontrado.")
        serial = payload.get("serial_number", "")
        qty = int(payload.get("quantity", 1))
        if serial:
            item = db.query(models.StockSerial).filter_by(
                warehouse_id=wh.id, serial_number=serial, status="disponible"
            ).first()
            if not item:
                raise ValueError(f"Ítem {serial} no disponible.")
            item.status = "dado_de_baja"
        else:
            stock = db.query(models.Stock).filter(
                models.Stock.warehouse_id == wh.id,
                (models.Stock.product_code == payload["product_identifier"]) |
                (models.Stock.product_name.ilike(f"%{payload['product_identifier']}%")),
            ).first()
            if not stock or stock.quantity < qty:
                raise ValueError("Stock insuficiente.")
            stock.quantity -= qty

        db.add(models.Sale(
            node_id=node_id,
            customer_name=payload.get("customer_name", ""),
            product_code=payload.get("product_identifier", ""),
            product_name=payload.get("product_identifier", ""),
            serial_number=serial or None,
            warehouse_code=payload["warehouse_code"],
            quantity=qty,
            unit_price=float(payload.get("unit_price", 0)) or None,
            synced_at=datetime.now(UTC),
        ))
