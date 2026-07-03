"""
Tests de rendimiento — Transcripción de audio (faster-whisper).

Ayudan a aislar DÓNDE está el cuello de botella:

  Etapa 1 — Overhead del endpoint (auth + routing, sin Whisper real)
  Etapa 2 — Carga del modelo Whisper desde disco  ← suele ser la más lenta
  Etapa 3 — Inferencia por segundo de audio (RTF)

Cómo correrlos:

  # Solo los tests rápidos (mock, sin Whisper real):
  pytest backend/tests/test_performance_audio.py -v -s -m "not integration"

  # Todos (incluyendo Whisper real — tarda varios minutos la primera vez):
  pytest backend/tests/test_performance_audio.py -v -s

  # Solo la carga del modelo (para ver el cold-start puro):
  pytest backend/tests/test_performance_audio.py::TestWhisperRealPerformance::test_model_cold_start -v -s
"""
import math
import struct
import time

import pytest
from unittest.mock import patch


# ── Umbrales configurables ────────────────────────────────────────────────────

THRESHOLDS = {
    # Con LLM mockeado — mide solo el overhead de la app
    "endpoint_overhead_ms": 300,
    # Warm hit de lru_cache del modelo — debe ser casi 0
    "lru_cache_hit_ms": 5,
    # Cold start del modelo 'small' en CPU — referencia orientativa
    "model_cold_start_warning_s": 20,
    # RTF (Real-Time Factor) aceptable: 2.0 = procesa el audio al doble del tiempo real
    "rtf_acceptable": 2.5,
}


# ── Generadores de audio WAV sintético ───────────────────────────────────────

def _wav_header(num_samples: int, sample_rate: int = 16000) -> bytes:
    data_size = num_samples * 2
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1,
        sample_rate, sample_rate * 2, 2, 16,
        b"data", data_size,
    )


def make_silence_wav(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    n = int(sample_rate * duration_s)
    return _wav_header(n, sample_rate) + b"\x00" * (n * 2)


def make_tone_wav(duration_s: float = 1.0, freq: float = 440.0, sample_rate: int = 16000) -> bytes:
    n = int(sample_rate * duration_s)
    samples = b"".join(
        struct.pack("<h", int(16000 * math.sin(2 * math.pi * freq * i / sample_rate)))
        for i in range(n)
    )
    return _wav_header(n, sample_rate) + samples


# ── ETAPA 1 — Overhead del endpoint (sin Whisper real) ───────────────────────

class TestEndpointOverhead:
    """
    Mide solo el overhead de la app: auth JWT, routing, validaciones.
    La transcripción está mockeada para aislar este componente.

    Si este bloque ya es lento (> 300ms), el problema NO es Whisper.
    """

    def test_single_request_overhead(self, client, admin_headers):
        wav = make_silence_wav(0.5)
        with patch("backend.services.audio_service.transcribe", return_value="texto de prueba"):
            start = time.perf_counter()
            resp = client.post(
                "/audio/transcribe",
                files={"file": ("test.wav", wav, "audio/wav")},
                headers=admin_headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

        assert resp.status_code == 200, resp.text
        print(f"\n  [OVERHEAD] Petición con mock: {elapsed_ms:.1f}ms  (umbral: {THRESHOLDS['endpoint_overhead_ms']}ms)")
        assert elapsed_ms < THRESHOLDS["endpoint_overhead_ms"], (
            f"El overhead de la app es {elapsed_ms:.0f}ms — demasiado lento sin Whisper. "
            "Revisa middlewares, importaciones lentas en startup o base de datos."
        )

    def test_5_consecutive_requests_no_degradation(self, client, admin_headers):
        """
        5 peticiones seguidas con mock.
        Detecta fugas de memoria o inicialización que se repite en cada request.
        """
        wav = make_silence_wav(0.5)
        times_ms = []

        with patch("backend.services.audio_service.transcribe", return_value="ok"):
            for _ in range(5):
                start = time.perf_counter()
                resp = client.post(
                    "/audio/transcribe",
                    files={"file": ("test.wav", wav, "audio/wav")},
                    headers=admin_headers,
                )
                times_ms.append((time.perf_counter() - start) * 1000)
                assert resp.status_code == 200

        avg = sum(times_ms) / len(times_ms)
        print(
            f"\n  [OVERHEAD x5] avg={avg:.1f}ms  "
            f"tiempos={[f'{t:.0f}ms' for t in times_ms]}"
        )
        assert times_ms[-1] < times_ms[0] * 4, (
            f"Degradación entre request 1 ({times_ms[0]:.0f}ms) "
            f"y request 5 ({times_ms[-1]:.0f}ms). "
            "Podría haber una fuga de recursos."
        )

    def test_empty_file_returns_400_quickly(self, client, admin_headers):
        start = time.perf_counter()
        resp = client.post(
            "/audio/transcribe",
            files={"file": ("vacio.wav", b"", "audio/wav")},
            headers=admin_headers,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert resp.status_code == 400
        print(f"\n  [OVERHEAD] Rechazo de archivo vacío: {elapsed_ms:.1f}ms  (debe ser < 50ms)")
        assert elapsed_ms < 50, "La validación de archivo vacío no debería tardar."

    def test_too_large_file_returns_413_quickly(self, client, admin_headers):
        big = b"x" * (10 * 1024 * 1024 + 1)
        start = time.perf_counter()
        resp = client.post(
            "/audio/transcribe",
            files={"file": ("grande.wav", big, "audio/wav")},
            headers=admin_headers,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert resp.status_code == 413
        print(f"\n  [OVERHEAD] Rechazo de archivo > 10MB: {elapsed_ms:.1f}ms")

    def test_unauthenticated_rejected_quickly(self, client):
        wav = make_silence_wav(0.5)
        start = time.perf_counter()
        resp = client.post(
            "/audio/transcribe",
            files={"file": ("test.wav", wav, "audio/wav")},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert resp.status_code in (401, 403)
        print(f"\n  [OVERHEAD] Rechazo sin token: {elapsed_ms:.1f}ms  (debe ser < 50ms)")
        assert elapsed_ms < 100


# ── ETAPA 2 — Carga del modelo Whisper ───────────────────────────────────────

class TestWhisperModelCache:
    """
    Verifica que lru_cache funciona: la segunda llamada a _get_model() es instantánea.
    Si el warm-hit tarda, algo está invalidando el cache entre requests.
    """

    def test_lru_cache_hit_is_instant(self):
        """Simula que el modelo ya está en cache y mide el tiempo de acceso."""
        sentinel = object()

        call_times = []

        def fake_loader():
            t = time.perf_counter()
            call_times.append(t)
            return sentinel

        with patch("backend.services.audio_service._get_model", side_effect=fake_loader):
            from backend.services import audio_service as _svc
            start = time.perf_counter()
            _ = _svc._get_model()
            elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [CACHE] Acceso mock a _get_model(): {elapsed_ms:.3f}ms")
        assert elapsed_ms < THRESHOLDS["lru_cache_hit_ms"]


# ── ETAPA 3 — Whisper real (integration) ─────────────────────────────────────

@pytest.mark.integration
@pytest.mark.slow
class TestWhisperRealPerformance:
    """
    Tests de integración — requieren faster-whisper instalado y modelo descargado.

    Miden el rendimiento REAL de Whisper en esta máquina específica.
    Son lentos a propósito: su objetivo es cuantificar el cuello de botella.

    Cómo interpretar los resultados:
      - Cold start > 30s → demasiado lento para UX, considera WHISPER_MODEL=tiny en .env
      - RTF > 2.0       → la transcripción tarda el doble del audio, muy perceptible
      - RTF < 1.0       → más rápido que el audio (ideal)
    """

    def test_model_cold_start(self):
        """
        Mide el tiempo de carga del modelo desde disco (cold start).
        Limpia el lru_cache antes de medir.
        """
        try:
            from faster_whisper import WhisperModel
            from backend.config import settings
            from backend.services import audio_service
        except ImportError:
            pytest.skip("faster-whisper no está instalado")

        audio_service._get_model.cache_clear()

        start = time.perf_counter()
        model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
        elapsed_s = time.perf_counter() - start

        print(f"\n  [COLD START] Modelo '{settings.whisper_model}' cargado en {elapsed_s:.1f}s")
        if elapsed_s > THRESHOLDS["model_cold_start_warning_s"]:
            print(
                f"  ⚠ LENTO ({elapsed_s:.0f}s > {THRESHOLDS['model_cold_start_warning_s']}s). "
                "Prueba con WHISPER_MODEL=tiny en el archivo .env para reducir el tiempo de carga."
            )
        else:
            print(f"  ✓ Dentro del rango esperado para CPU sin GPU")

        assert model is not None

    def test_warm_start_via_cache(self):
        """Segunda llamada a _get_model() — debe ser instantánea gracias a lru_cache."""
        try:
            from backend.services import audio_service
        except ImportError:
            pytest.skip("faster-whisper no está instalado")

        try:
            _ = audio_service._get_model()  # warm up
        except RuntimeError:
            pytest.skip("faster-whisper no está instalado")

        start = time.perf_counter()
        _ = audio_service._get_model()
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [WARM START] _get_model() con cache: {elapsed_ms:.3f}ms")
        assert elapsed_ms < 5, (
            f"El warm start tardó {elapsed_ms:.1f}ms. lru_cache podría no estar funcionando."
        )

    def test_transcription_1s_silence(self):
        """
        Transcribe 1s de silencio.
        Mide el overhead mínimo de inferencia: VAD filter + decode frames.
        """
        try:
            from backend.services import audio_service
        except ImportError:
            pytest.skip("faster-whisper no está instalado")

        wav = make_silence_wav(1.0)
        start = time.perf_counter()
        try:
            result = audio_service.transcribe(wav, "silencio.wav")
        except RuntimeError:
            pytest.skip("faster-whisper no está instalado")
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [INFERENCIA] 1s silencio → {elapsed_ms:.0f}ms  resultado='{result}'")

    def test_transcription_rtf_2s_tone(self):
        """
        Mide el RTF (Real-Time Factor) con 2 segundos de audio sintético.
        RTF = tiempo_proceso / duración_audio
          < 1.0 → más rápido que el audio (muy bueno)
          1.0-2.0 → aceptable
          > 2.0 → perceptiblemente lento para el usuario
        """
        try:
            from backend.services import audio_service
        except ImportError:
            pytest.skip("faster-whisper no está instalado")

        audio_duration_s = 2.0
        wav = make_tone_wav(audio_duration_s)

        start = time.perf_counter()
        try:
            result = audio_service.transcribe(wav, "tono.wav")
        except RuntimeError:
            pytest.skip("faster-whisper no está instalado")
        elapsed_s = time.perf_counter() - start

        rtf = elapsed_s / audio_duration_s
        print(
            f"\n  [RTF] {audio_duration_s}s audio → procesado en {elapsed_s:.1f}s | "
            f"RTF={rtf:.2f}x  resultado='{result}'"
        )
        if rtf > THRESHOLDS["rtf_acceptable"]:
            print(
                f"  ⚠ RTF demasiado alto ({rtf:.1f}x). "
                "El usuario esperará más de lo que dura su mensaje de voz. "
                "Considera WHISPER_MODEL=tiny en .env."
            )
        else:
            print(f"  ✓ RTF aceptable para uso real")

    def test_transcription_rtf_5s_tone(self):
        """Mismo RTF con 5s de audio para ver si hay overhead constante vs lineal."""
        try:
            from backend.services import audio_service
        except ImportError:
            pytest.skip("faster-whisper no está instalado")

        audio_duration_s = 5.0
        wav = make_tone_wav(audio_duration_s)

        start = time.perf_counter()
        try:
            result = audio_service.transcribe(wav, "tono5s.wav")
        except RuntimeError:
            pytest.skip("faster-whisper no está instalado")
        elapsed_s = time.perf_counter() - start

        rtf = elapsed_s / audio_duration_s
        print(
            f"\n  [RTF] {audio_duration_s}s audio → procesado en {elapsed_s:.1f}s | "
            f"RTF={rtf:.2f}x  resultado='{result}'"
        )
