from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.asr.whisper_service import transcribe
from app.models.responses import TranscribeResponse
from app.config import get_settings

router = APIRouter(prefix="/v1", tags=["ASR"])


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    settings = get_settings()
    data = await audio.read()

    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    return await transcribe(data, audio.filename or "audio.wav")
