import logging
import shutil
import subprocess
import sys
import tempfile
import os
from functools import lru_cache
from backend.config import settings

logger = logging.getLogger(__name__)


def _check_ffmpeg() -> None:
    """Verifica que ffmpeg esté disponible en el sistema (requerido en Linux)."""
    if sys.platform == "win32":
        return  # faster-whisper en Windows no necesita ffmpeg del sistema
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg no está instalado. En Garuda/Arch ejecuta: sudo pacman -S ffmpeg"
        )


@lru_cache(maxsize=1)
def _get_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper no está instalado. Ejecuta: pip install faster-whisper"
        ) from e
    _check_ffmpeg()
    logger.info("Cargando modelo Whisper '%s' en CPU...", settings.whisper_model)
    model = WhisperModel(
        settings.whisper_model,
        device="cpu",
        compute_type="int8",
    )
    logger.info("Modelo Whisper '%s' cargado.", settings.whisper_model)
    return model


def preload_model() -> None:
    """Precarga el modelo en un thread al arrancar para que el primer usuario no espere."""
    try:
        _get_model()
    except Exception as exc:
        logger.warning("No se pudo precargar Whisper: %s", exc)


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    ext = os.path.splitext(filename)[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        model = _get_model()
        segments, _ = model.transcribe(
            tmp_path,
            language=settings.whisper_language,
            beam_size=1,   # más rápido que beam_size=5, apenas peor calidad
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        os.unlink(tmp_path)
