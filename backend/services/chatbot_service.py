"""Chatbot service — hybrid: context injection for reads, tool calling for writes."""
import json
import logging
import time
import uuid
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from backend import models
from backend.config import settings
from backend.services.action_service import build_confirmation_summary, create_action_token
from backend.tools.tool_registry import get_tools_for_user

logger = logging.getLogger(__name__)

UNRESOLVED_PHRASES = [
    "no tengo información",
    "no dispongo de información",
    "no puedo responder",
]

# Keywords that signal the user wants to WRITE/ACT, not just read
_WRITE_KEYWORDS = {
    "transf", "mover", "mueve",
    "crea", "crear", "añade", "añadir", "agrega", "agregar", "nuevo", "nueva",
    "elimin", "borrar", "borra", "dar de baja",
    "edita", "editar", "modifica", "modificar", "cambia", "cambiar", "actualiz",
    "desactiv", "activ", "bloquea", "bloquear",
    "resetea", "resetear", "contraseña", "password",
    "crea usuario", "nuevo usuario",
    "reserva", "reservar", "en reparacion", "en reparación", "dado de baja",
    "propone", "proponer", "ejecuta", "confirma",
}


def _is_write_query(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _WRITE_KEYWORDS)


# ── Stock context builder ─────────────────────────────────────────────────────

def _build_stock_context(db: Session, user: models.User) -> str:
    """Fetch all accessible stock directly from DB and return as plain text."""
    from backend.tools.query_tools import _accessible_wh_ids
    accessible_ids = _accessible_wh_ids(db, user)

    wh_cache: dict[int, str] = {}

    def _wh_label(wh_id: int) -> str:
        if wh_id not in wh_cache:
            wh = db.query(models.Warehouse).filter_by(id=wh_id).first()
            wh_cache[wh_id] = f"{wh.name} ({wh.code})" if wh else str(wh_id)
        return wh_cache[wh_id]

    lines: list[str] = []

    for s in (
        db.query(models.Stock)
        .filter(
            models.Stock.warehouse_id.in_(accessible_ids),
            models.Stock.status != "dado_de_baja",
        )
        .all()
    ):
        lines.append(
            f"[{_wh_label(s.warehouse_id)}] {s.product_code} | {s.product_name} | "
            f"cant: {s.quantity} | mín: {s.min_quantity} | estado: {s.status} | "
            f"ubic: {s.location_in_warehouse or 'N/A'}"
        )

    for s in (
        db.query(models.StockSerial)
        .filter(
            models.StockSerial.warehouse_id.in_(accessible_ids),
            models.StockSerial.status != "dado_de_baja",
        )
        .all()
    ):
        lines.append(
            f"[{_wh_label(s.warehouse_id)}] SN: {s.serial_number} | "
            f"{s.product_name} ({s.product_code}) | estado: {s.status} | "
            f"ubic: {s.location_in_warehouse or 'N/A'}"
        )

    return "\n".join(lines) if lines else "No hay productos en el inventario accesible."


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

def _build_system_prompt(user: models.User, db: Session, stock_context: str | None = None) -> str:
    wh_context = ""
    if user.warehouse:
        wh_context = f"Tu almacén asignado: {user.warehouse.name} ({user.warehouse.code})."

    warehouses = db.query(models.Warehouse).all()
    wh_list = ", ".join(f"{w.name} ({w.code})" for w in warehouses)

    base = (
        f"Eres un asistente de gestión de inventario. Rol: {user.role.name}. {wh_context}\n"
        f"Almacenes disponibles: {wh_list}.\n"
        "Responde en español. Sé conciso.\n"
        "Si el usuario pide algo fuera de sus permisos de rol, indícalo claramente.\n"
    )

    if stock_context:
        return (
            base +
            "Para consultas: responde SOLO con los datos de inventario proporcionados abajo. "
            "No inventes datos.\n\n"
            f"INVENTARIO ACTUAL:\n{stock_context}"
        )

    return (
        base +
        "Para acciones (transferencias, cambios de estado, crear/editar/eliminar productos, "
        "gestionar usuarios): usa las herramientas propose_*. "
        "Si el usuario no especifica el código exacto del producto, búscalo en el inventario "
        "usando el nombre parcial y pregunta si hay ambigüedad. "
        "Si falta información (cantidad, almacén destino, etc.), pregúntasela al usuario "
        "antes de llamar a la herramienta.\n\n"
        f"INVENTARIO ACTUAL:\n{stock_context if stock_context else ''}"
    )


# ── Agent loop ────────────────────────────────────────────────────────────────

def _run_agent(llm_with_tools, tools: list, messages: list, action_holder: dict, max_iters: int = 4) -> str:
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

def get_session_history(db: Session, user_id: int, session_id: str, limit: int = 6) -> list:
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
    history = get_session_history(db, user.id, session_id)

    try:
        if not _is_write_query(question):
            # ── READ PATH: context injection, single LLM call ──
            context = _build_stock_context(db, user)
            messages = [SystemMessage(content=_build_system_prompt(user, db, context))]
            for h in history:
                messages.append(HumanMessage(content=h.question))
                messages.append(AIMessage(content=h.response))
            messages.append(HumanMessage(content=question))
            answer = _build_llm().invoke(messages).content or "Lo siento, no pude responder."
        else:
            # ── WRITE PATH: tool calling agent with stock context ──
            action_holder: dict = {}
            tools = get_tools_for_user(db, user, action_holder)
            llm = _build_llm()
            llm_with_tools = llm.bind_tools(tools)
            context = _build_stock_context(db, user)
            messages = [SystemMessage(content=_build_system_prompt(user, db, context))]
            for h in history:
                messages.append(HumanMessage(content=h.question))
                messages.append(AIMessage(content=h.response))
            messages.append(HumanMessage(content=question))
            answer = _run_agent(llm_with_tools, tools, messages, action_holder)

            elapsed_ms = int((time.time() - start) * 1000)
            if answer == "__PENDING_ACTION__" and action_holder.get("action"):
                action_data = action_holder["action"]
                summary, is_valid = build_confirmation_summary(db, action_data)
                _save_history(db, user.id, session_id, question, summary, elapsed_ms)
                if not is_valid:
                    return {"type": "query", "response": summary, "session_id": session_id, "response_time_ms": elapsed_ms}
                token = create_action_token(db, user.id, action_data)
                return {"type": "action_pending", "summary": summary, "action_token": token,
                        "session_id": session_id, "response_time_ms": elapsed_ms}

    except Exception as exc:
        logger.error("LLM call failed (%s): %s", type(exc).__name__, exc)
        err_str = str(exc).lower()
        if "memory" in err_str or "oom" in err_str or "out of memory" in err_str:
            answer = "⚠️ Sin memoria RAM suficiente. Cierra otras apps e intenta de nuevo."
        elif "connection" in err_str or "refused" in err_str or "connect" in err_str:
            answer = "⚠️ No se puede conectar con Ollama. Verifica que esté corriendo (ollama serve)."
        else:
            answer = f"⚠️ Error de IA: {type(exc).__name__}. Revisa los logs del backend."

    elapsed_ms = int((time.time() - start) * 1000)
    _save_history(db, user.id, session_id, question, answer, elapsed_ms)
    if any(phrase in answer.lower() for phrase in UNRESOLVED_PHRASES):
        _notify_unresolved(db, user, question)
    return {"type": "query", "response": answer, "session_id": session_id, "response_time_ms": elapsed_ms}


# ── Streaming public API ──────────────────────────────────────────────────────

async def ask_stream(
    db: Session, user: models.User, question: str, session_id: str | None = None
) -> AsyncGenerator[str, None]:
    """Yield SSE lines.
    Read queries: context injection → single streamed LLM call.
    Write queries: tool calling agent → streamed final answer.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    start = time.time()
    history = get_session_history(db, user.id, session_id)

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _build_base_messages(sys_prompt: str) -> list:
        msgs = [SystemMessage(content=sys_prompt)]
        for h in history:
            msgs.append(HumanMessage(content=h.question))
            msgs.append(AIMessage(content=h.response))
        msgs.append(HumanMessage(content=question))
        return msgs

    try:
        if not _is_write_query(question):
            # ── READ PATH: context injection, single streamed LLM call ──
            context = _build_stock_context(db, user)
            messages = _build_base_messages(_build_system_prompt(user, db, context))
            llm = _build_llm()

            full_answer = ""
            for chunk in llm.stream(messages):
                delta = chunk.content or ""
                if delta:
                    full_answer += delta
                    yield _sse({"type": "delta", "delta": delta})

            if not full_answer:
                full_answer = "Lo siento, no pude completar la consulta. Intenta de nuevo."
                yield _sse({"type": "delta", "delta": full_answer})

            elapsed_ms = int((time.time() - start) * 1000)
            logger.info("READ query answered in %dms", elapsed_ms)
            _save_history(db, user.id, session_id, question, full_answer, elapsed_ms)
            if any(p in full_answer.lower() for p in UNRESOLVED_PHRASES):
                _notify_unresolved(db, user, question)
            yield _sse({"type": "done", "session_id": session_id, "response_time_ms": elapsed_ms})

        else:
            # ── WRITE PATH: tool calling agent with stock context ──
            action_holder: dict = {}
            tools = get_tools_for_user(db, user, action_holder)
            llm = _build_llm()
            llm_with_tools = llm.bind_tools(tools)
            tools_by_name = {t.name: t for t in tools}
            context = _build_stock_context(db, user)
            msgs = _build_base_messages(_build_system_prompt(user, db, context))

            # Phase 1: tool-call iterations
            for _ in range(3):
                response = llm_with_tools.invoke(msgs)
                msgs.append(response)

                if not response.tool_calls:
                    answer = response.content
                    elapsed_ms = int((time.time() - start) * 1000)
                    logger.info("WRITE query (direct) answered in %dms", elapsed_ms)
                    _save_history(db, user.id, session_id, question, answer, elapsed_ms)
                    if any(p in answer.lower() for p in UNRESOLVED_PHRASES):
                        _notify_unresolved(db, user, question)
                    yield _sse({"type": "query", "response": answer,
                                 "session_id": session_id, "response_time_ms": elapsed_ms})
                    return

                tool_results: list[ToolMessage] = []
                for call in response.tool_calls:
                    tool = tools_by_name.get(call["name"])
                    try:
                        content = str(tool.invoke(call["args"])) if tool else f"Herramienta '{call['name']}' no disponible."
                    except Exception as exc:
                        content = f"Error: {exc}"
                    tool_results.append(ToolMessage(content=content, tool_call_id=call["id"]))
                    if action_holder.get("action"):
                        break

                if action_holder.get("action"):
                    action_data = action_holder["action"]
                    summary, is_valid = build_confirmation_summary(db, action_data)
                    elapsed_ms = int((time.time() - start) * 1000)
                    logger.info("WRITE query (action) answered in %dms", elapsed_ms)
                    _save_history(db, user.id, session_id, question, summary, elapsed_ms)
                    if not is_valid:
                        yield _sse({"type": "query", "response": summary,
                                     "session_id": session_id, "response_time_ms": elapsed_ms})
                        return
                    token = create_action_token(db, user.id, action_data)
                    yield _sse({"type": "action_pending", "summary": summary,
                                 "action_token": token, "session_id": session_id,
                                 "response_time_ms": elapsed_ms})
                    return

                msgs.extend(tool_results)

            # Phase 2: stream final answer
            full_answer = ""
            for chunk in llm.stream(msgs):
                delta = chunk.content or ""
                if delta:
                    full_answer += delta
                    yield _sse({"type": "delta", "delta": delta})

            if not full_answer:
                full_answer = "Lo siento, no pude completar la consulta. Intenta de nuevo."
                yield _sse({"type": "delta", "delta": full_answer})

            elapsed_ms = int((time.time() - start) * 1000)
            logger.info("WRITE query (streamed) answered in %dms", elapsed_ms)
            _save_history(db, user.id, session_id, question, full_answer, elapsed_ms)
            if any(p in full_answer.lower() for p in UNRESOLVED_PHRASES):
                _notify_unresolved(db, user, question)
            yield _sse({"type": "done", "session_id": session_id, "response_time_ms": elapsed_ms})

    except Exception as exc:
        logger.error("LLM stream failed (%s): %s", type(exc).__name__, exc)
        err_str = str(exc).lower()
        if "memory" in err_str or "oom" in err_str or "out of memory" in err_str:
            msg = "⚠️ Sin memoria RAM suficiente. Cierra otras apps e intenta de nuevo."
        elif "connection" in err_str or "refused" in err_str or "connect" in err_str:
            msg = "⚠️ No se puede conectar con Ollama. Verifica que esté corriendo (ollama serve)."
        else:
            msg = f"⚠️ Error de IA: {type(exc).__name__}. Revisa los logs del backend."
        yield _sse({"type": "error", "response": msg, "session_id": session_id or ""})
