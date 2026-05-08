import asyncio
import io
import logging
import os

import httpx
import soundfile as sf
from kokoro_onnx import Kokoro

from app.config import get_settings

log = logging.getLogger(__name__)

_kokoro: Kokoro | None = None

_MODEL_URLS = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin":  "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}

# Kokoro-82M has exactly one French voice; Wolof falls back to it.
_VOICE_MAP: dict[str, tuple[str, str]] = {
    "fr": ("ff_siwis", "fr-fr"),
    "wo": ("ff_siwis", "fr-fr"),
    "en": ("af_sarah", "en-us"),
}
_DEFAULT: tuple[str, str] = ("ff_siwis", "fr-fr")


def _ensure_models(models_dir: str) -> None:
    os.makedirs(models_dir, exist_ok=True)
    for filename, url in _MODEL_URLS.items():
        path = os.path.join(models_dir, filename)
        if os.path.exists(path):
            continue
        log.info("Downloading Kokoro model file: %s", filename)
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        log.info("Downloaded %s (%.1f MB)", filename, os.path.getsize(path) / 1_048_576)


def get_kokoro() -> Kokoro:
    global _kokoro
    if _kokoro is None:
        models_dir = get_settings().kokoro_models_dir
        _ensure_models(models_dir)
        _kokoro = Kokoro(
            os.path.join(models_dir, "kokoro-v1.0.onnx"),
            os.path.join(models_dir, "voices-v1.0.bin"),
        )
        log.info("Kokoro TTS loaded")
    return _kokoro


def _synthesize_sync(text: str, voice: str, lang: str) -> bytes:
    samples, sample_rate = get_kokoro().create(text, voice=voice, speed=1.0, lang=lang)
    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV")
    return buf.getvalue()


async def synthesize(text: str, language: str = "fr") -> bytes:
    """Return WAV bytes for `text` in the given language."""
    voice, lang = _VOICE_MAP.get(language.lower()[:2], _DEFAULT)
    return await asyncio.to_thread(_synthesize_sync, text, voice, lang)
