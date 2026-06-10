"""Integration tests for audio/transcribe endpoint (mocked faster-whisper)."""
import pytest
from unittest.mock import patch


class TestAudioTranscribe:
    def test_transcribe_returns_text(self, client, admin_headers):
        with patch("backend.services.audio_service.transcribe", return_value="cinco laptops disponibles"):
            fake_audio = b"RIFF" + b"\x00" * 100  # minimal fake wav bytes
            resp = client.post(
                "/audio/transcribe",
                files={"file": ("audio.webm", fake_audio, "audio/webm")},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["text"] == "cinco laptops disponibles"

    def test_transcribe_empty_file_returns_400(self, client, admin_headers):
        resp = client.post(
            "/audio/transcribe",
            files={"file": ("audio.webm", b"", "audio/webm")},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_transcribe_unauthenticated_returns_403(self, client):
        resp = client.post(
            "/audio/transcribe",
            files={"file": ("audio.webm", b"data", "audio/webm")},
        )
        assert resp.status_code in (401, 403)

    def test_transcribe_silent_audio_returns_422(self, client, admin_headers):
        with patch("backend.services.audio_service.transcribe", return_value=""):
            resp = client.post(
                "/audio/transcribe",
                files={"file": ("audio.webm", b"fake", "audio/webm")},
                headers=admin_headers,
            )
        assert resp.status_code == 422

    def test_transcribe_too_large_returns_413(self, client, admin_headers):
        big = b"x" * (10 * 1024 * 1024 + 1)
        resp = client.post(
            "/audio/transcribe",
            files={"file": ("audio.webm", big, "audio/webm")},
            headers=admin_headers,
        )
        assert resp.status_code == 413
