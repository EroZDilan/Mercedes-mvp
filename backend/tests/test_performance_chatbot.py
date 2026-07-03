"""
Tests de rendimiento — Chatbot (LLM via Ollama / OpenRouter).

Pipeline del chatbot y dónde puede estar el cuello de botella:

  Etapa 1 — Construcción de contexto (_build_stock_context): query a SQLite
  Etapa 2 — Construcción del system prompt (_build_system_prompt): solo strings
  Etapa 3 — Inicialización del cliente LLM (_build_llm): objeto Python, no red
  Etapa 4 — Llamada al LLM: aquí está el 99% de la latencia
    └── Tiempo al primer token (TTFT): cuándo el usuario ve algo
    └── Tiempo total: hasta que termina la respuesta completa

Cómo correrlos:

  # Solo tests rápidos (sin LLM real):
  pytest backend/tests/test_performance_chatbot.py -v -s -m "not integration"

  # Todos (con Ollama real — requiere 'ollama serve' corriendo):
  pytest backend/tests/test_performance_chatbot.py -v -s

  # Solo medir el LLM real (TTFT y total):
  pytest backend/tests/test_performance_chatbot.py::TestLLMRealPerformance -v -s
"""
import asyncio
import json
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

from backend.services import chatbot_service
from backend import models


# ── Umbrales configurables ────────────────────────────────────────────────────

THRESHOLDS = {
    # Construir contexto desde SQLite — pura query local
    "context_build_ms": 100,
    # Construir el system prompt — solo strings
    "prompt_build_ms": 20,
    # Overhead del endpoint con LLM mockeado
    "endpoint_mock_ms": 400,
    # TTFT aceptable con LLM real en CPU (Ollama local)
    "ttft_acceptable_ms": 8_000,
    # Tiempo total de respuesta aceptable con LLM real
    "total_llm_acceptable_ms": 30_000,
}


# ── ETAPA 1 — Construcción de contexto (DB query) ────────────────────────────

class TestContextBuildLatency:
    """
    _build_stock_context() hace queries a SQLite.
    Debe ser muy rápido (< 100ms) — si no lo es, SQLite o el ORM están lentos.
    """

    def test_admin_context_build(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()

        start = time.perf_counter()
        ctx = chatbot_service._build_stock_context(seeded_db, user)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert ctx  # tiene contenido
        print(f"\n  [CONTEXTO] Admin (todos los almacenes): {elapsed_ms:.2f}ms  chars={len(ctx)}")
        assert elapsed_ms < THRESHOLDS["context_build_ms"], (
            f"_build_stock_context tardó {elapsed_ms:.1f}ms. "
            "SQLite local no debería tardar tanto — revisa si hay índices faltantes "
            "o si el archivo .db está en una ubicación lenta (NFS, red)."
        )

    def test_operador_context_build(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="operador_u").first()

        start = time.perf_counter()
        ctx = chatbot_service._build_stock_context(seeded_db, user)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [CONTEXTO] Operador (solo su almacén): {elapsed_ms:.2f}ms  chars={len(ctx)}")
        assert elapsed_ms < THRESHOLDS["context_build_ms"]

    def test_context_build_10_times_stable(self, seeded_db):
        """10 construcciones de contexto seguidas — verifica que no hay degradación."""
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        times_ms = []

        for _ in range(10):
            start = time.perf_counter()
            chatbot_service._build_stock_context(seeded_db, user)
            times_ms.append((time.perf_counter() - start) * 1000)

        avg = sum(times_ms) / len(times_ms)
        mx = max(times_ms)
        print(
            f"\n  [CONTEXTO x10] avg={avg:.2f}ms  max={mx:.2f}ms  "
            f"todos={[f'{t:.1f}' for t in times_ms]}"
        )
        assert mx < THRESHOLDS["context_build_ms"] * 3, (
            f"El contexto tardó hasta {mx:.1f}ms en alguna iteración. "
            "Podría haber fluctuaciones de I/O."
        )


# ── ETAPA 2 — Construcción del system prompt ──────────────────────────────────

class TestSystemPromptBuildLatency:
    """
    _build_system_prompt() solo hace queries simples a DB y concatena strings.
    Debe ser < 20ms.
    """

    def test_prompt_build_operador(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="operador_u").first()
        ctx = chatbot_service._build_stock_context(seeded_db, user)

        start = time.perf_counter()
        prompt = chatbot_service._build_system_prompt(user, seeded_db, ctx)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert "operador" in prompt.lower()
        print(f"\n  [PROMPT] Operador: {elapsed_ms:.2f}ms  chars={len(prompt)}")
        assert elapsed_ms < THRESHOLDS["prompt_build_ms"]

    def test_prompt_build_admin(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        ctx = chatbot_service._build_stock_context(seeded_db, user)

        start = time.perf_counter()
        prompt = chatbot_service._build_system_prompt(user, seeded_db, ctx)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [PROMPT] Admin: {elapsed_ms:.2f}ms  chars={len(prompt)}")
        assert elapsed_ms < THRESHOLDS["prompt_build_ms"]


# ── ETAPA 3 — Endpoint con LLM mockeado ──────────────────────────────────────

class TestEndpointOverhead:
    """
    Mide el overhead de la app (auth, routing, DB) con el LLM completamente mockeado.
    Si este bloque ya es lento, el problema NO es Ollama.
    """

    def _make_mock_stream(self, text: str = "El stock está bien."):
        async def _mock(db, user, question, session_id=None):
            sid = session_id or "sess-perf"
            yield f"data: {json.dumps({'type': 'delta', 'delta': text})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': sid, 'response_time_ms': 1})}\n\n"
        return _mock

    def test_single_message_overhead(self, client, admin_headers):
        with patch("backend.routers.chatbot.chatbot_service.ask_stream", self._make_mock_stream()):
            start = time.perf_counter()
            resp = client.post(
                "/chatbot/message",
                json={"message": "¿Cuántas laptops hay?"},
                headers=admin_headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

        assert resp.status_code == 200
        print(f"\n  [ENDPOINT] POST /chatbot/message con mock: {elapsed_ms:.1f}ms  (umbral: {THRESHOLDS['endpoint_mock_ms']}ms)")
        assert elapsed_ms < THRESHOLDS["endpoint_mock_ms"], (
            f"El overhead del endpoint es {elapsed_ms:.0f}ms. "
            "Revisa importaciones lentas, middlewares o el arranque de la app."
        )

    def test_5_consecutive_messages_no_degradation(self, client, admin_headers):
        times_ms = []

        with patch("backend.routers.chatbot.chatbot_service.ask_stream", self._make_mock_stream()):
            for i in range(5):
                start = time.perf_counter()
                resp = client.post(
                    "/chatbot/message",
                    json={"message": f"Pregunta {i}"},
                    headers=admin_headers,
                )
                times_ms.append((time.perf_counter() - start) * 1000)
                assert resp.status_code == 200

        avg = sum(times_ms) / len(times_ms)
        print(
            f"\n  [ENDPOINT x5] avg={avg:.1f}ms  "
            f"tiempos={[f'{t:.0f}ms' for t in times_ms]}"
        )
        assert times_ms[-1] < times_ms[0] * 4, (
            f"Degradación detectada: req1={times_ms[0]:.0f}ms, req5={times_ms[-1]:.0f}ms"
        )

    def test_write_query_overhead(self, client, admin_headers):
        """Misma medición pero con una pregunta de escritura (activa la ruta con tools)."""
        async def _mock_write(db, user, question, session_id=None):
            sid = session_id or "sess-write"
            payload = json.dumps({
                "type": "action_pending",
                "summary": "Transferir 2 P001",
                "action_token": "tok-mock",
                "session_id": sid,
                "response_time_ms": 1,
            })
            yield f"data: {payload}\n\n"

        with patch("backend.routers.chatbot.chatbot_service.ask_stream", _mock_write):
            start = time.perf_counter()
            resp = client.post(
                "/chatbot/message",
                json={"message": "Transfiere 2 laptops de ALM-A a ALM-B"},
                headers=admin_headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

        assert resp.status_code == 200
        print(f"\n  [ENDPOINT] Consulta de escritura con mock: {elapsed_ms:.1f}ms")
        assert elapsed_ms < THRESHOLDS["endpoint_mock_ms"]


# ── ETAPA 4 — Latencia del agent loop (mocks con delay simulado) ──────────────

class TestAgentLoopLatency:
    """
    Mide el overhead del agent loop (_run_agent) con un LLM mock que responde
    sin delay. Aísla el costo del bucle de tools vs el tiempo del LLM real.
    """

    def test_run_agent_no_tools_is_fast(self):
        """Sin tool calls, el agent loop hace solo 1 invocación al LLM."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "Hay 10 laptops disponibles."
        mock_llm.invoke.return_value = mock_response

        start = time.perf_counter()
        result = chatbot_service._run_agent(mock_llm, [], [MagicMock()], {})
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result == "Hay 10 laptops disponibles."
        print(f"\n  [AGENT LOOP] Sin tool calls: {elapsed_ms:.3f}ms")
        assert elapsed_ms < 10

    def test_run_agent_1_tool_call_overhead(self):
        """Con 1 tool call: mide el overhead de dispatch + ToolMessage + segunda invocación."""
        mock_tool = MagicMock()
        mock_tool.name = "query_stock"
        mock_tool.invoke.return_value = "P001 | Laptop | cant: 10"

        first = MagicMock()
        first.tool_calls = [{"name": "query_stock", "args": {}, "id": "call-1"}]
        first.content = ""

        second = MagicMock()
        second.tool_calls = []
        second.content = "Tienes 10 laptops."

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [first, second]

        start = time.perf_counter()
        result = chatbot_service._run_agent(mock_llm, [mock_tool], [MagicMock()], {})
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result == "Tienes 10 laptops."
        print(f"\n  [AGENT LOOP] 1 tool call: {elapsed_ms:.3f}ms  (2 invocaciones al LLM)")
        assert elapsed_ms < 20


# ── ETAPA 5 — LLM real (integration — requiere Ollama corriendo) ──────────────

@pytest.mark.integration
@pytest.mark.slow
class TestLLMRealPerformance:
    """
    Tests de integración — requieren Ollama corriendo en local.

    Mide el rendimiento REAL del LLM en esta máquina.

    Cómo interpretar los resultados:
      TTFT < 3s   → bueno para UX (el usuario ve algo rápido)
      TTFT 3-8s   → aceptable pero perceptible
      TTFT > 8s   → demasiado lento — revisa RAM libre, modelo usado, OLLAMA_HOST

      Tiempo total depende de la longitud de la respuesta y los tokens/s del hardware.

    Antes de correr:
      Verifica que Ollama está corriendo: curl http://localhost:11434/api/tags
    """

    def _check_ollama_reachable(self):
        """Salta el test si Ollama no está disponible."""
        try:
            import httpx
            from backend.config import settings
            if not settings.ollama_base_url:
                pytest.skip("OLLAMA_BASE_URL no está configurado en .env")
            resp = httpx.get(settings.ollama_base_url.rstrip("/") + "/api/tags", timeout=3)
            if resp.status_code != 200:
                pytest.skip(f"Ollama no responde en {settings.ollama_base_url}")
        except Exception as e:
            pytest.skip(f"Ollama no alcanzable: {e}")

    def test_llm_first_token_latency_read_query(self, seeded_db):
        """
        Mide el TTFT (Time To First Token) en una consulta de lectura simple.
        Este es el tiempo que el usuario espera antes de ver la primera palabra.
        """
        self._check_ollama_reachable()

        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        session_id = str(uuid.uuid4())

        async def _measure():
            first_delta_ms = None
            start = time.perf_counter()
            async for chunk in chatbot_service.ask_stream(seeded_db, user, "¿Cuántas laptops hay?", session_id):
                elapsed = (time.perf_counter() - start) * 1000
                if first_delta_ms is None and '"delta"' in chunk:
                    first_delta_ms = elapsed
            total_ms = (time.perf_counter() - start) * 1000
            return first_delta_ms, total_ms

        ttft_ms, total_ms = asyncio.run(_measure())

        print(
            f"\n  [LLM REAL] TTFT={ttft_ms:.0f}ms  Total={total_ms:.0f}ms  "
            f"(umbral TTFT: {THRESHOLDS['ttft_acceptable_ms']}ms)"
        )
        if ttft_ms and ttft_ms > THRESHOLDS["ttft_acceptable_ms"]:
            print(
                f"  ⚠ TTFT demasiado alto ({ttft_ms:.0f}ms). "
                "Posibles causas:\n"
                "  · Ollama cargando el modelo en RAM (primera petición)\n"
                "  · RAM insuficiente → swap activo → muy lento\n"
                "  · Modelo demasiado grande para esta máquina\n"
                "  Prueba con un modelo más pequeño: OLLAMA_MODEL=qwen2.5:1.5b"
            )

        assert ttft_ms is not None, "No se recibió ningún chunk de tipo 'delta'"
        assert ttft_ms < THRESHOLDS["ttft_acceptable_ms"], (
            f"TTFT de {ttft_ms:.0f}ms supera el umbral de {THRESHOLDS['ttft_acceptable_ms']}ms"
        )

    def test_llm_total_response_time_short_answer(self, seeded_db):
        """
        Mide el tiempo total para una respuesta corta y directa.
        El contexto del seeded_db es pequeño (3-4 productos) así que la respuesta
        debería ser concisa.
        """
        self._check_ollama_reachable()

        user = seeded_db.query(models.User).filter_by(username="operador_u").first()
        session_id = str(uuid.uuid4())

        deltas = []

        async def _measure():
            start = time.perf_counter()
            async for chunk in chatbot_service.ask_stream(seeded_db, user, "¿Hay laptops disponibles?", session_id):
                if '"delta"' in chunk:
                    try:
                        data = json.loads(chunk.replace("data: ", "").strip())
                        deltas.append(data.get("delta", ""))
                    except Exception:
                        pass
            return (time.perf_counter() - start) * 1000

        total_ms = asyncio.run(_measure())
        full_response = "".join(deltas)

        print(
            f"\n  [LLM REAL] Respuesta corta — Total={total_ms:.0f}ms  "
            f"tokens≈{len(full_response.split())}  chars={len(full_response)}"
        )
        print(f"  Respuesta: '{full_response[:120]}{'...' if len(full_response) > 120 else ''}'")

        tokens_per_s = len(full_response.split()) / (total_ms / 1000) if total_ms > 0 else 0
        print(f"  Velocidad ≈ {tokens_per_s:.1f} palabras/s")

        assert total_ms < THRESHOLDS["total_llm_acceptable_ms"], (
            f"Tiempo total {total_ms:.0f}ms supera {THRESHOLDS['total_llm_acceptable_ms']}ms. "
            "El LLM es demasiado lento para esta máquina."
        )

    def test_llm_warm_vs_cold_comparison(self, seeded_db):
        """
        Compara la primera llamada (cold — modelo cargándose) vs la segunda (warm).
        La diferencia indica si Ollama tiene el modelo en RAM entre peticiones.
        """
        self._check_ollama_reachable()

        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        times_ms = []

        for i in range(2):
            session_id = str(uuid.uuid4())

            async def _measure(sid=session_id):
                start = time.perf_counter()
                async for _ in chatbot_service.ask_stream(seeded_db, user, "¿Cuántos productos hay?", sid):
                    pass
                return (time.perf_counter() - start) * 1000

            t = asyncio.run(_measure())
            times_ms.append(t)
            print(f"\n  [LLM WARM/COLD] Llamada {i+1}: {t:.0f}ms")

        cold, warm = times_ms
        ratio = cold / warm if warm > 0 else 0
        print(
            f"\n  [RESUMEN] Cold={cold:.0f}ms  Warm={warm:.0f}ms  "
            f"ratio={ratio:.1f}x  "
            f"({'Ollama mantiene el modelo en RAM ✓' if ratio > 1.5 else 'Cold y warm similares — modelo ya estaba cargado'})"
        )
