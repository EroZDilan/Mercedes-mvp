"""Sales router — historial de ventas y sincronización de cola offline."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.middleware.auth import get_current_user, require_role
from backend import models
from backend.services import queue_service
from backend.config import settings

router = APIRouter(prefix="/sales", tags=["sales"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SaleOut(BaseModel):
    id: int
    node_id: str
    customer_name: Optional[str]
    product_code: str
    product_name: str
    serial_number: Optional[str]
    warehouse_code: str
    quantity: int
    unit_price: Optional[float]
    total_price: Optional[float]
    notes: Optional[str]
    status: str
    created_at: datetime
    seller_username: Optional[str] = None

    model_config = {"from_attributes": True}


class QueueOpIn(BaseModel):
    id: int
    node_id: str
    operation_type: str
    payload: dict
    op_timestamp: str


class QueuePushIn(BaseModel):
    operations: list[QueueOpIn]


class QueueStatusOut(BaseModel):
    pending: int
    node_role: str
    central_server: Optional[str]


# ── Endpoints de ventas ───────────────────────────────────────────────────────

@router.get("/", response_model=list[SaleOut])
def list_sales(
    limit: int = Query(default=50, le=200),
    warehouse: Optional[str] = None,
    customer: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Sale)

    # Operadores solo ven sus propias ventas
    if current_user.role.name in ("operador", "supervisor"):
        q = q.filter(models.Sale.seller_id == current_user.id)

    if warehouse:
        q = q.filter(models.Sale.warehouse_code == warehouse.upper())
    if customer:
        q = q.filter(models.Sale.customer_name.ilike(f"%{customer}%"))

    sales = q.order_by(models.Sale.created_at.desc()).limit(limit).all()

    result = []
    for s in sales:
        d = SaleOut.model_validate(s)
        if s.seller:
            d.seller_username = s.seller.username
        result.append(d)
    return result


@router.get("/stats")
def sales_stats(
    current_user: models.User = Depends(require_role("admin", "gestor")),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    total = db.query(func.count(models.Sale.id)).scalar()
    revenue = db.query(func.sum(models.Sale.total_price)).scalar() or 0
    by_warehouse = (
        db.query(models.Sale.warehouse_code, func.count(models.Sale.id))
        .group_by(models.Sale.warehouse_code)
        .all()
    )
    return {
        "total_sales": total,
        "total_revenue": round(float(revenue), 2),
        "by_warehouse": {wh: cnt for wh, cnt in by_warehouse},
    }


# ── Endpoints de cola offline ─────────────────────────────────────────────────

@router.get("/queue/status", response_model=QueueStatusOut)
def queue_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return QueueStatusOut(
        pending=queue_service.pending_count(db),
        node_role=settings.node_role,
        central_server=settings.central_server_url or None,
    )


@router.post("/queue/push")
def push_queue(
    current_user: models.User = Depends(require_role("admin", "gestor")),
    db: Session = Depends(get_db),
):
    """Dispara manualmente la sincronización de la cola offline con el servidor central."""
    result = queue_service.push_to_central(db)
    return result


@router.post("/queue/receive")
def receive_queue(
    body: QueuePushIn,
    current_user: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Endpoint del servidor central para recibir operaciones de nodos clientes."""
    ops = [op.model_dump() for op in body.operations]
    result = queue_service.receive_from_client(db, ops)
    return result
