"""Notifications router — in-app notifications per user."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend import models, schemas

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[schemas.NotificationOut])
def list_notifications(
    unread_only: Optional[bool] = Query(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Notification).filter(
        models.Notification.recipient_user_id == current_user.id
    )
    if unread_only:
        q = q.filter(models.Notification.is_read == False)
    return q.order_by(models.Notification.created_at.desc()).all()


@router.get("/unread-count")
def unread_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(models.Notification).filter(
        models.Notification.recipient_user_id == current_user.id,
        models.Notification.is_read == False,
    ).count()
    return {"unread_count": count}


@router.patch("/read-all")
def mark_all_read(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.Notification).filter(
        models.Notification.recipient_user_id == current_user.id,
        models.Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"detail": "Todas las notificaciones marcadas como leídas"}


@router.patch("/{notif_id}/read")
def mark_read(
    notif_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif = db.query(models.Notification).filter(
        models.Notification.id == notif_id
    ).first()
    if not notif:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notificación no encontrada")
    if notif.recipient_user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa notificación")
    notif.is_read = True
    db.commit()
    return {"detail": "Notificación marcada como leída"}
