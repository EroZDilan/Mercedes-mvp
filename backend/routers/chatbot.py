from typing import Optional
import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend import models, schemas
from backend.services import chatbot_service

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


class MessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.get("/health")
async def chatbot_health():
    """Diagnóstico: verifica si Ollama está disponible y el modelo cargado."""
    if not settings.ollama_base_url:
        return {"provider": "openrouter", "status": "configured", "model": "moonshotai/kimi-k2.6:free"}

    base = settings.ollama_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/api/tags")
            if r.status_code != 200:
                return {"provider": "ollama", "status": "error", "detail": f"HTTP {r.status_code}"}
            models_list = [m["name"] for m in r.json().get("models", [])]
            model_ready = settings.ollama_model in models_list
            return {
                "provider": "ollama",
                "status": "ok" if model_ready else "model_not_found",
                "model": settings.ollama_model,
                "available_models": models_list,
                "base_url": base,
            }
    except httpx.ConnectError:
        return {"provider": "ollama", "status": "unreachable", "base_url": base,
                "detail": "No se puede conectar a Ollama. ¿Está corriendo?"}
    except Exception as exc:
        return {"provider": "ollama", "status": "error", "detail": str(exc)}


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
