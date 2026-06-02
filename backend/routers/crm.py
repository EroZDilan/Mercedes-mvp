"""CRM router — notes, history, metrics."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend import models, schemas
from backend.services import crm_service, metrics_service

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/notes", response_model=list[schemas.CrmNoteOut])
def list_notes(
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crm_service.get_notes(db, current_user, user_id)


@router.post("/notes", response_model=schemas.CrmNoteOut, status_code=201)
def create_note(
    body: schemas.CrmNoteCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crm_service.create_note(db, current_user, body.content, body.related_to)


@router.put("/notes/{note_id}", response_model=schemas.CrmNoteOut)
def update_note(
    note_id: int,
    body: schemas.CrmNoteUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crm_service.update_note(db, current_user, note_id, body.content)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    crm_service.delete_note(db, current_user, note_id)


@router.get("/history")
def get_history(
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crm_service.get_history(db, current_user, user_id)


# /metrics/global MUST be registered before /metrics to avoid any future path conflicts
@router.get("/metrics/global")
def get_global_metrics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role.hierarchy_level != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo admin puede ver métricas globales",
        )
    return metrics_service.get_global_metrics(db)


@router.get("/metrics")
def get_metrics(
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    target = user_id if user_id else current_user.id
    if target != current_user.id:
        crm_service._check_crm_view_access(db, current_user, target)
    return metrics_service.get_user_metrics(db, target)
