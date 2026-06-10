"""Integration tests for chatbot API endpoints (no real LLM calls)."""
import json
import pytest
from unittest.mock import patch, AsyncMock


async def _mock_ask_stream_query(db, user, question, session_id=None):
    """Fake ask_stream that returns a simple query response."""
    yield f"data: {json.dumps({'type': 'query', 'response': 'Hay 10 laptops.', 'session_id': session_id or 'sess-1', 'response_time_ms': 42})}\n\n"


async def _mock_ask_stream_action(db, user, question, session_id=None):
    """Fake ask_stream that returns an action_pending response."""
    yield f"data: {json.dumps({'type': 'action_pending', 'summary': 'Transferir 5 P001 de ALM-A a ALM-B', 'action_token': 'tok-123', 'session_id': session_id or 'sess-1', 'response_time_ms': 99})}\n\n"


async def _mock_ask_stream_delta(db, user, question, session_id=None):
    """Fake ask_stream that yields deltas then done."""
    yield f"data: {json.dumps({'type': 'delta', 'delta': 'Hay '})}\n\n"
    yield f"data: {json.dumps({'type': 'delta', 'delta': '10 laptops.'})}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'session_id': session_id or 'sess-1', 'response_time_ms': 120})}\n\n"


class TestChatbotHealth:
    def test_health_returns_200(self, client, admin_headers):
        resp = client.get("/chatbot/health", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "provider" in data
        assert "status" in data

    def test_health_no_auth_still_works(self, client):
        # /chatbot/health is a public diagnostic endpoint
        resp = client.get("/chatbot/health")
        assert resp.status_code == 200


class TestChatbotMessage:
    def test_message_returns_sse_stream(self, client, admin_headers):
        with patch("backend.routers.chatbot.chatbot_service.ask_stream", _mock_ask_stream_query):
            resp = client.post(
                "/chatbot/message",
                json={"message": "¿Cuántas laptops hay?"},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        assert "Hay 10 laptops" in resp.text

    def test_message_unauthenticated_returns_403(self, client):
        resp = client.post("/chatbot/message", json={"message": "hola"})
        assert resp.status_code in (401, 403)

    def test_message_action_pending_in_stream(self, client, admin_headers):
        with patch("backend.routers.chatbot.chatbot_service.ask_stream", _mock_ask_stream_action):
            resp = client.post(
                "/chatbot/message",
                json={"message": "Transfiere 5 P001 de ALM-A a ALM-B"},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        assert "action_pending" in resp.text
        assert "tok-123" in resp.text

    def test_message_delta_streaming(self, client, admin_headers):
        with patch("backend.routers.chatbot.chatbot_service.ask_stream", _mock_ask_stream_delta):
            resp = client.post(
                "/chatbot/message",
                json={"message": "¿Cuántas laptops?"},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        # Both delta chunks and done event should be in the response body
        assert '"type": "delta"' in resp.text
        assert '"type": "done"' in resp.text
        assert "Hay " in resp.text

    def test_empty_message_still_processes(self, client, admin_headers):
        with patch("backend.routers.chatbot.chatbot_service.ask_stream", _mock_ask_stream_query):
            resp = client.post(
                "/chatbot/message",
                json={"message": ""},
                headers=admin_headers,
            )
        # Empty string is valid — chatbot service handles it
        assert resp.status_code == 200


class TestChatbotHistory:
    def test_history_empty_for_new_user(self, client, admin_headers):
        resp = client.get("/chatbot/history", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_history_unauthenticated_returns_403(self, client):
        resp = client.get("/chatbot/history")
        assert resp.status_code in (401, 403)
