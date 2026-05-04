import asyncio
import tempfile
import os
from pathlib import Path
from faster_whisper import WhisperModel
from app.config import get_settings
from app.models.responses import TranscribeResponse


_model: WhisperModel | None = None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        settings = get_settings()
        compute_type = "float16" if settings.whisper_device == "cuda" else "int8"
        _model = WhisperModel(settings.whisper_model, device=settings.whisper_device, compute_type=compute_type)
    return _model


def _transcribe_sync(audio_path: str) -> TranscribeResponse:
    model = get_model()
    segments, info = model.transcribe(audio_path, beam_size=5)
    text = " ".join(seg.text.strip() for seg in segments)
    return TranscribeResponse(
        text=text.strip(),
        language=info.language,
        confidence=round(info.language_probability, 3),
        duration_seconds=round(info.duration, 2),
    )


async def transcribe(audio_bytes: bytes, filename: str) -> TranscribeResponse:
    suffix = Path(filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        # Run blocking CPU work in a thread pool to avoid blocking the event loop
        return await asyncio.to_thread(_transcribe_sync, tmp_path)
    finally:
        os.unlink(tmp_path)
