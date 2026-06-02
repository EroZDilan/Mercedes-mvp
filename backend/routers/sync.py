from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.middleware.auth import require_role
from backend.services import sync_service
from backend import models, schemas

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/trigger")
def trigger_sync(
    current_user: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    logs = sync_service.sync_all(db, triggered_by="admin")
    return {
        "detail": f"Sync completado — {len(logs)} almacén(es)",
        "logs": [schemas.SyncLogOut.model_validate(log) for log in logs],
    }


@router.get("/status", response_model=list[schemas.WarehouseStatusOut])
def warehouse_status(
    current_user: models.User = Depends(require_role("admin", "gestor")),
    db: Session = Depends(get_db),
):
    return db.query(models.Warehouse).all()


@router.get("/logs", response_model=list[schemas.SyncLogOut])
def sync_logs(
    current_user: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
):
    return (
        db.query(models.SyncLog)
        .order_by(models.SyncLog.started_at.desc())
        .limit(limit)
        .all()
    )
