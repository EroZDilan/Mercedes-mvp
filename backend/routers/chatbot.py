from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend import models, schemas
from backend.services import chatbot_service

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


class MessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.post("/message")
def send_message(
    body: MessageRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Returns {"type": "query", "response": ...}
    # or      {"type": "action_pending", "summary": ..., "action_token": ...}
    return chatbot_service.ask(db, current_user, body.message, body.session_id)


@router.get("/history", response_model=list[schemas.ChatHistoryOut])
def get_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    query = db.query(models.ChatHistory).filter_by(user_id=current_user.id)
    if session_id:
        query = query.filter_by(session_id=session_id)
    return query.order_by(models.ChatHistory.timestamp.desc()).limit(limit).all()
