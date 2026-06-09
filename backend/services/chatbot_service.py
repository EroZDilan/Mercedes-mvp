"""Chatbot service — tool calling agent + action confirmation flow."""
import json
import time
import uuid
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from backend import models
from backend.config import settings
from backend.services.action_service import build_confirmation_summary, create_action_token
from backend.tools.tool_registry import get_tools_for_user

UNRESOLVED_PHRASES = [
    "no tengo información",
    "no dispongo de información",
    "no puedo responder",
]


# ── LLM factory ───────────────────────────────────────────────────────────────

def _build_llm() -> ChatOpenAI:
    if settings.ollama_base_url:
        return ChatOpenAI(
            model=settings.ollama_model,
            api_key="ollama",
            base_url=settings.ollama_base_url.rstrip("/") + "/v1",
            temperature=0.1,
            max_tokens=1024,
        )
    return ChatOpenAI(
        model="moonshotai/kimi-k2.6:free",
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0.1,
        max_tokens=1024,
    )


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(user: models.User, db: Session) -> str:
    wh_context = ""
    if user.warehouse:
        wh_context = f"Tu almacén asignado: {user.warehouse.name} ({user.warehouse.code})."

    warehouses = db.query(models.Warehouse).all()
    wh_list = ", ".join(f"{w.name} ({w.code})" for w in warehouses)

    return (
        f"Eres un asistente de gestión de inventario. Rol: {user.role.name}. {wh_context}\n"
        f"Almacenes disponibles: {wh_list}.\n\n"
        "REGLAS:\n"
        "1. Para consultas de stock: usa query_stock o query_serial_stock. No inventes datos.\n"
        "2. Para acciones (transferencias, cambios de estado, crear/editar/eliminar productos, "
        "gestionar usuarios): usa siempre las herramientas propose_*. Nunca confirmes ejecutar "
        "una acción sin llamar a la herramienta correspondiente.\n"
        "3. Responde en español. Sé conciso (máximo 3 líneas para consultas).\n"
        "4. Si el usuario pide algo fuera de tus permisos de rol, indícalo claramente."
    )


# ── Agent loop ────────────────────────────────────────────────────────────────

def _run_agent(llm_with_tools, tools: list, messages: list, action_holder: dict, max_iters: int = 8) -> str:
    tools_by_name = {t.name: t for t in tools}
    msgs = list(messages)

    for _ in range(max_iters):
        response = llm_with_tools.invoke(msgs)
        msgs.append(response)

        if not response.tool_calls:
            return response.content

        tool_results: list[ToolMessage] = []
        for call in response.tool_calls:
            tool = tools_by_name.get(call["name"])
            if not tool:
                content = f"Herramienta '{call['name']}' no disponible."
            else:
                try:
                    content = str(tool.invoke(call["args"]))
                except Exception as exc:
                    content = f"Error: {exc}"

            tool_results.append(ToolMessage(content=content, tool_call_id=call["id"]))

            if action_holder.get("action"):
                return "__PENDING_ACTION__"

        msgs.extend(tool_results)

    return "Lo siento, no pude completar la consulta. Intenta de nuevo."


# ── History helpers ───────────────────────────────────────────────────────────

def get_session_history(db: Session, user_id: int, session_id: str, limit: int = 10) -> list:
    return (
        db.query(models.ChatHistory)
        .filter_by(user_id=user_id, session_id=session_id)
        .order_by(models.ChatHistory.timestamp.asc())
        .limit(limit)
        .all()
    )


def _find_superior(db: Session, user: models.User) -> models.User | None:
    level = user.role.hierarchy_level
    if level == 4:
        return (
            db.query(models.User).join(models.Role)
            .filter(
                models.Role.hierarchy_level == 3,
                models.User.warehouse_id == user.warehouse_id,
                models.User.is_active == True,
            )
            .first()
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


def _save_history(db, user_id, session_id, question, response, elapsed_ms):
    db.add(models.ChatHistory(
        user_id=user_id,
        session_id=session_id,
        question=question,
        response=response,
        warehouses_context="[]",
        response_time_ms=elapsed_ms,
    ))
    db.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def ask(db: Session, user: models.User, question: str, session_id: str | None = None) -> dict:
    if not session_id:
        session_id = str(uuid.uuid4())

    start = time.time()
    action_holder: dict = {}

    tools = get_tools_for_user(db, user, action_holder)
    llm = _build_llm()
    llm_with_tools = llm.bind_tools(tools)

    history = get_session_history(db, user.id, session_id)
    messages = [SystemMessage(content=_build_system_prompt(user, db))]
    for h in history:
        messages.append(HumanMessage(content=h.question))
        messages.append(AIMessage(content=h.response))
    messages.append(HumanMessage(content=question))

    try:
        answer = _run_agent(llm_with_tools, tools, messages, action_holder)
    except Exception:
        answer = "El servicio de IA no está disponible en este momento. Intenta de nuevo más tarde."

    elapsed_ms = int((time.time() - start) * 1000)

    # ── Action pending flow ──
    if answer == "__PENDING_ACTION__" and action_holder.get("action"):
        action_data = action_holder["action"]
        summary, is_valid = build_confirmation_summary(db, action_data)

        _save_history(db, user.id, session_id, question, summary, elapsed_ms)

        if not is_valid:
            return {"type": "query", "response": summary, "session_id": session_id, "response_time_ms": elapsed_ms}

        token = create_action_token(db, user.id, action_data)
        return {
            "type": "action_pending",
            "summary": summary,
            "action_token": token,
            "session_id": session_id,
            "response_time_ms": elapsed_ms,
        }

    # ── Normal query response ──
    _save_history(db, user.id, session_id, question, answer, elapsed_ms)

    if any(phrase in answer.lower() for phrase in UNRESOLVED_PHRASES):
        _notify_unresolved(db, user, question)

    return {"type": "query", "response": answer, "session_id": session_id, "response_time_ms": elapsed_ms}
