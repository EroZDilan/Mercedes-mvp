"""Chatbot service — LangChain + DeepSeek, filtrado por rol."""
import json
import time
import uuid
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from backend import models
from backend.config import settings

UNRESOLVED_PHRASES = ["no tengo información", "no dispongo de información", "no puedo responder"]


def _find_superior(db: Session, user: models.User) -> models.User | None:
    level = user.role.hierarchy_level
    if level == 4:  # operador → supervisor mismo almacén
        return (
            db.query(models.User).join(models.Role)
            .filter(
                models.Role.hierarchy_level == 3,
                models.User.warehouse_id == user.warehouse_id,
                models.User.is_active == True,
            ).first()
        )
    if level == 3:  # supervisor → gestor
        return (
            db.query(models.User).join(models.Role)
            .filter(models.Role.hierarchy_level == 2, models.User.is_active == True)
            .first()
        )
    if level == 2:  # gestor → admin
        return (
            db.query(models.User).join(models.Role)
            .filter(models.Role.hierarchy_level == 1, models.User.is_active == True)
            .first()
        )
    return None


def _notify_unresolved(db: Session, user: models.User, question: str):
    superior = _find_superior(db, user)
    if superior:
        db.add(models.Notification(
            recipient_user_id=superior.id,
            type="chat_unresolved",
            message=(
                f"{user.full_name or user.username} preguntó algo que el chatbot "
                f"no pudo resolver: '{question[:150]}'"
            ),
            related_user_id=user.id,
        ))
        db.commit()


def build_stock_context(db: Session, user: models.User) -> tuple[str, list[str]]:
    """Returns (context_text, list_of_warehouse_codes)."""
    if user.role.hierarchy_level <= 2:
        warehouses = db.query(models.Warehouse).all()
    else:
        warehouses = db.query(models.Warehouse).filter_by(id=user.warehouse_id).all()

    wh_codes = [w.code for w in warehouses]
    parts = []

    for wh in warehouses:
        lines = [f"\n=== {wh.name} ==="]

        stocks = (
            db.query(models.Stock)
            .filter(
                models.Stock.warehouse_id == wh.id,
                models.Stock.status != "dado_de_baja",
            ).all()
        )
        if stocks:
            lines.append("Productos por cantidad:")
            for s in stocks:
                lines.append(
                    f"  - {s.product_code} | {s.product_name} | "
                    f"cantidad: {s.quantity} | mínimo: {s.min_quantity} | "
                    f"ubicación: {s.location_in_warehouse or 'N/A'} | estado: {s.status}"
                )

        serials = (
            db.query(models.StockSerial)
            .filter(
                models.StockSerial.warehouse_id == wh.id,
                models.StockSerial.status != "dado_de_baja",
            ).all()
        )
        if serials:
            lines.append("Productos de serie única:")
            for s in serials:
                lines.append(
                    f"  - {s.serial_number} | {s.product_name} | "
                    f"estado: {s.status} | ubicación: {s.location_in_warehouse or 'N/A'}"
                )

        parts.append("\n".join(lines))

    context = "\n".join(parts) if parts else "No hay stock disponible."
    return context, wh_codes


def build_system_prompt(user: models.User, stock_context: str) -> str:
    base = user.role.system_prompt
    if "{warehouse_name}" in base and user.warehouse:
        base = base.replace("{warehouse_name}", user.warehouse.name)

    return (
        f"{base}\n\n"
        f"INVENTARIO ACTUAL:\n{stock_context}\n\n"
        "Si no tienes información suficiente sobre lo que te preguntan, responde exactamente: "
        "'No tengo información disponible sobre eso en este momento.'\n"
        "Responde siempre en español de forma concisa y clara."
    )


def get_session_history(
    db: Session, user_id: int, session_id: str, limit: int = 10
) -> list[models.ChatHistory]:
    return (
        db.query(models.ChatHistory)
        .filter_by(user_id=user_id, session_id=session_id)
        .order_by(models.ChatHistory.timestamp.asc())
        .limit(limit)
        .all()
    )


def ask(
    db: Session,
    user: models.User,
    question: str,
    session_id: str | None = None,
) -> dict:
    if not session_id:
        session_id = str(uuid.uuid4())

    start = time.time()

    # Build context and history
    context, wh_codes = build_stock_context(db, user)
    history = get_session_history(db, user.id, session_id)
    system_prompt = build_system_prompt(user, context)

    # Build messages list for LLM
    messages = [SystemMessage(content=system_prompt)]
    for h in history:
        messages.append(HumanMessage(content=h.question))
        messages.append(AIMessage(content=h.response))
    messages.append(HumanMessage(content=question))

    # Call LLM — Ollama (local) tiene prioridad si OLLAMA_BASE_URL está configurado
    try:
        if settings.ollama_base_url:
            llm = ChatOpenAI(
                model=settings.ollama_model,
                api_key="ollama",
                base_url=settings.ollama_base_url.rstrip("/") + "/v1",
                temperature=0.1,
                max_tokens=1024,
            )
        else:
            llm = ChatOpenAI(
                model="moonshotai/kimi-k2.6:free",
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.1,
                max_tokens=1024,
            )
        llm_response = llm.invoke(messages)
        answer = llm_response.content
    except Exception:
        answer = "El servicio de IA no está disponible en este momento. Por favor intenta de nuevo más tarde."

    elapsed_ms = int((time.time() - start) * 1000)

    # Persist to chat_history
    db.add(models.ChatHistory(
        user_id=user.id,
        session_id=session_id,
        question=question,
        response=answer,
        warehouses_context=json.dumps(wh_codes),
        response_time_ms=elapsed_ms,
    ))
    db.commit()

    # Notify superior if chatbot couldn't resolve the question
    if any(phrase in answer.lower() for phrase in UNRESOLVED_PHRASES):
        _notify_unresolved(db, user, question)

    return {"response": answer, "session_id": session_id, "response_time_ms": elapsed_ms}
