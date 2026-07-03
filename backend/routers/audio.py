import asyncio
from functools import partial
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from backend.middleware.auth import get_current_user
from backend import models
from backend.services import audio_service

router = APIRouter(prefix="/audio", tags=["audio"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
):
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio demasiado grande (máx 10 MB).")
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Archivo de audio vacío.")

    try:
        # Whisper es CPU-bound y bloqueante — se ejecuta en thread pool
        # para no bloquear el event loop de uvicorn durante la transcripción.
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None,
            partial(audio_service.transcribe, audio_bytes, file.filename or "audio.webm"),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al transcribir: {e}")

    if not text:
        raise HTTPException(status_code=422, detail="No se detectó voz en el audio.")

    return {"text": text}
