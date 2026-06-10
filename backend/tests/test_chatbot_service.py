"""Tests for chatbot_service helpers (no LLM calls)."""
import pytest
from unittest.mock import MagicMock, patch
from backend.services import chatbot_service
from backend import models


class TestGetSessionHistory:
    def test_returns_empty_for_unknown_session(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        history = chatbot_service.get_session_history(seeded_db, user.id, "nonexistent-session")
        assert history == []

    def test_returns_saved_history(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        seeded_db.add(models.ChatHistory(
            user_id=user.id, session_id="sess-abc",
            question="¿Cuántas laptops hay?", response="Hay 10.",
            warehouses_context="[]", response_time_ms=500,
        ))
        seeded_db.commit()
        history = chatbot_service.get_session_history(seeded_db, user.id, "sess-abc")
        assert len(history) == 1
        assert history[0].question == "¿Cuántas laptops hay?"

    def test_respects_limit(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        for i in range(10):
            seeded_db.add(models.ChatHistory(
                user_id=user.id, session_id="sess-many",
                question=f"Q{i}", response=f"A{i}",
                warehouses_context="[]", response_time_ms=100,
            ))
        seeded_db.commit()
        history = chatbot_service.get_session_history(seeded_db, user.id, "sess-many", limit=6)
        assert len(history) == 6


class TestBuildSystemPrompt:
    def test_includes_role_name(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="operador_u").first()
        prompt = chatbot_service._build_system_prompt(user, seeded_db)
        assert "operador" in prompt.lower()

    def test_includes_warehouse_for_assigned_user(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="operador_u").first()
        prompt = chatbot_service._build_system_prompt(user, seeded_db)
        assert "ALM-A" in prompt or "Almacén Norte" in prompt

    def test_no_warehouse_context_for_admin(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        prompt = chatbot_service._build_system_prompt(user, seeded_db)
        # Admin has no assigned warehouse, so no warehouse-specific line
        assert "Tu almacén asignado" not in prompt


class TestRunAgent:
    def test_returns_content_when_no_tool_calls(self):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "Hay 10 laptops disponibles."
        mock_llm.invoke.return_value = mock_response

        result = chatbot_service._run_agent(mock_llm, [], [MagicMock()], {})
        assert result == "Hay 10 laptops disponibles."

    def test_calls_tool_and_returns_second_response(self):
        holder = {}
        mock_tool = MagicMock()
        mock_tool.name = "query_stock"
        mock_tool.invoke.return_value = "P001 | Laptop | cant: 10"

        first_response = MagicMock()
        first_response.tool_calls = [{"name": "query_stock", "args": {}, "id": "call-1"}]
        first_response.content = ""

        second_response = MagicMock()
        second_response.tool_calls = []
        second_response.content = "Tienes 10 laptops."

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [first_response, second_response]

        result = chatbot_service._run_agent(mock_llm, [mock_tool], [MagicMock()], holder)
        assert result == "Tienes 10 laptops."
        assert mock_llm.invoke.call_count == 2

    def test_returns_pending_action_when_action_set(self):
        holder = {}

        def tool_fn(args):
            holder["action"] = {"action_type": "transfer", "params": {}}
            return "ACCION_PROPUESTA"

        mock_tool = MagicMock()
        mock_tool.name = "propose_transfer"
        mock_tool.invoke.side_effect = tool_fn

        first_response = MagicMock()
        first_response.tool_calls = [{"name": "propose_transfer", "args": {}, "id": "call-1"}]

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = first_response

        result = chatbot_service._run_agent(mock_llm, [mock_tool], [MagicMock()], holder)
        assert result == "__PENDING_ACTION__"

    def test_max_iters_returns_fallback(self):
        mock_response = MagicMock()
        mock_response.tool_calls = [{"name": "unknown", "args": {}, "id": "c1"}]
        mock_response.content = ""

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        result = chatbot_service._run_agent(mock_llm, [], [MagicMock()], {}, max_iters=2)
        assert "no pude" in result.lower()
        assert mock_llm.invoke.call_count == 2


class TestSaveHistory:
    def test_saves_to_db(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        chatbot_service._save_history(seeded_db, user.id, "sess-save", "pregunta", "respuesta", 300)
        record = seeded_db.query(models.ChatHistory).filter_by(session_id="sess-save").first()
        assert record is not None
        assert record.question == "pregunta"
        assert record.response_time_ms == 300
