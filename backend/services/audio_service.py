import tempfile
import os
from functools import lru_cache
from backend.config import settings


@lru_cache(maxsize=1)
def _get_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper no está instalado. Ejecuta: pip install faster-whisper"
        ) from e
    return WhisperModel(
        settings.whisper_model,
        device="cpu",
        compute_type="int8",
    )


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
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        os.unlink(tmp_path)
