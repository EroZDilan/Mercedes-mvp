"""CRM service — notes CRUD with notifications and history view."""
from datetime import datetime, UTC
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend import models


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


def _notify_crm_action(db: Session, user: models.User, action: str, note_id: int):
    message = f"Nota CRM: {user.username} {action} (nota #{note_id})"
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
                type="crm_note",
                message=message,
                related_user_id=user.id,
            ))
            notified_ids.add(admin.id)

    superior = _find_superior(db, user)
    if superior and superior.id not in notified_ids:
        db.add(models.Notification(
            recipient_user_id=superior.id,
            type="crm_note",
            message=message,
            related_user_id=user.id,
        ))


def _check_crm_view_access(db: Session, requester: models.User, target_user_id: int):
    """Raises 403 if requester cannot view target user's CRM."""
    if requester.id == target_user_id:
        return
    level = requester.role.hierarchy_level
    if level <= 2:
        return
    if level == 3:
        target = db.query(models.User).filter_by(id=target_user_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if (target.role.hierarchy_level == 4
                and target.warehouse_id == requester.warehouse_id):
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Sin acceso al CRM de ese usuario",
    )


def get_notes(
    db: Session, user: models.User,
    target_user_id: int | None = None,
    related_to: str | None = None,
) -> list[models.CrmNote]:
    uid = target_user_id if target_user_id else user.id
    if uid != user.id:
        _check_crm_view_access(db, user, uid)
    q = db.query(models.CrmNote).filter_by(user_id=uid)
    if related_to:
        q = q.filter(models.CrmNote.related_to == related_to)
    return q.order_by(models.CrmNote.created_at.desc()).all()


def create_note(
    db: Session, user: models.User, content: str, related_to: str | None = None
) -> models.CrmNote:
    note = models.CrmNote(user_id=user.id, content=content, related_to=related_to)
    db.add(note)
    db.commit()
    db.refresh(note)
    _notify_crm_action(db, user, "creó una nota", note.id)
    db.commit()
    return note


def update_note(
    db: Session, user: models.User, note_id: int, content: str
) -> models.CrmNote:
    note = db.query(models.CrmNote).filter_by(id=note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    if note.user_id != user.id and user.role.hierarchy_level != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a esta nota",
        )
    note.content = content
    note.modified_at = datetime.now(UTC)
    db.commit()
    db.refresh(note)
    _notify_crm_action(db, user, "editó una nota", note.id)
    db.commit()
    return note


def delete_note(db: Session, user: models.User, note_id: int):
    note = db.query(models.CrmNote).filter_by(id=note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    if note.user_id != user.id and user.role.hierarchy_level != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a esta nota",
        )
    db.delete(note)
    db.commit()


def get_history(
    db: Session, user: models.User, target_user_id: int | None = None
) -> list[dict]:
    uid = target_user_id if target_user_id else user.id
    if uid != user.id:
        _check_crm_view_access(db, user, uid)

    items: list[dict] = []

    for ch in db.query(models.ChatHistory).filter_by(user_id=uid).all():
        q = ch.question
        items.append({
            "type": "chat",
            "timestamp": ch.timestamp,
            "summary": q[:80] + ("..." if len(q) > 80 else ""),
            "detail": {
                "id": ch.id,
                "session_id": ch.session_id,
                "question": ch.question,
                "response": ch.response,
                "response_time_ms": ch.response_time_ms,
            },
        })

    for sh in db.query(models.StockHistory).filter_by(changed_by=uid).all():
        items.append({
            "type": "stock_change",
            "timestamp": sh.changed_at,
            "summary": f"Stock: {sh.field_changed} {sh.old_value}→{sh.new_value}",
            "detail": {
                "id": sh.id,
                "product_id": sh.product_id,
                "product_type": sh.product_type,
                "warehouse_id": sh.warehouse_id,
                "field_changed": sh.field_changed,
                "old_value": sh.old_value,
                "new_value": sh.new_value,
            },
        })

    for note in db.query(models.CrmNote).filter_by(user_id=uid).all():
        c = note.content
        items.append({
            "type": "crm_note",
            "timestamp": note.created_at,
            "summary": c[:80] + ("..." if len(c) > 80 else ""),
            "detail": {
                "id": note.id,
                "content": note.content,
                "related_to": note.related_to,
                "modified_at": note.modified_at,
            },
        })

    items.sort(key=lambda x: x["timestamp"] or datetime.min, reverse=True)
    return items
