import io
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import StreamingResponse
from app.services.tts.kokoro_service import synthesize

router = APIRouter(prefix="/v1", tags=["TTS"])


@router.post(
    "/tts",
    response_class=StreamingResponse,
    responses={200: {"content": {"audio/wav": {}}, "description": "WAV audio stream"}},
)
async def text_to_speech(
    text: str = Form(...),
    language: str = Form("fr"),
):
    """Convert text to speech. Returns a WAV audio stream."""
    if not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")

    audio_bytes = await synthesize(text, language)

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=speech.wav"},
    )
