from typing import Optional
import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
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
async def send_message(
    body: MessageRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SSE stream. Events: delta | query | action_pending | error | done."""
    return StreamingResponse(
        chatbot_service.ask_stream(db, current_user, body.message, body.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/slash-data")
def get_slash_data(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns inventory data needed to populate slash command forms."""
    from backend.tools.query_tools import _accessible_wh_ids

    accessible_ids = _accessible_wh_ids(db, current_user)
    role = current_user.role.name
    level = current_user.role.hierarchy_level

    warehouses = [
        {"id": w.id, "code": w.code, "name": w.name}
        for w in db.query(models.Warehouse).all()
        if w.id in accessible_ids
    ]

    stock = [
        {
            "id": s.id,
            "product_code": s.product_code,
            "product_name": s.product_name,
            "quantity": s.quantity,
            "status": s.status,
            "warehouse_id": s.warehouse_id,
            "warehouse_code": next((w["code"] for w in warehouses if w["id"] == s.warehouse_id), ""),
            "warehouse_name": next((w["name"] for w in warehouses if w["id"] == s.warehouse_id), ""),
            "type": "bulk",
        }
        for s in db.query(models.Stock).filter(
            models.Stock.warehouse_id.in_(accessible_ids),
            models.Stock.status != "dado_de_baja",
        ).all()
    ]

    serial = [
        {
            "id": s.id,
            "product_code": s.product_code,
            "product_name": s.product_name,
            "serial_number": s.serial_number,
            "status": s.status,
            "warehouse_id": s.warehouse_id,
            "warehouse_code": next((w["code"] for w in warehouses if w["id"] == s.warehouse_id), ""),
            "warehouse_name": next((w["name"] for w in warehouses if w["id"] == s.warehouse_id), ""),
            "type": "serial",
        }
        for s in db.query(models.StockSerial).filter(
            models.StockSerial.warehouse_id.in_(accessible_ids),
            models.StockSerial.status != "dado_de_baja",
        ).all()
    ]

    users = []
    if level <= 1:
        users = [
            {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role.name, "is_active": u.is_active}
            for u in db.query(models.User).filter(models.User.id != current_user.id).all()
        ]

    commands = ["mover", "estado"]
    if level <= 3:
        commands += ["crear", "editar"]
    if level <= 2:
        commands += ["eliminar"]
    if level <= 1:
        commands += ["usuario"]

    return {
        "role": role,
        "commands": commands,
        "warehouses": warehouses,
        "stock": stock + serial,
        "users": users,
    }


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
