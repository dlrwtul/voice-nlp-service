import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.asr.whisper_service import transcribe
from app.services.nlp.ollama_service import extract
from app.models.requests import ExtractionSchema
from app.models.responses import PipelineResponse

router = APIRouter(prefix="/v1", tags=["Pipeline"])


@router.post("/voice-to-json", response_model=PipelineResponse)
async def voice_to_json(
    audio: UploadFile = File(...),
    extraction_schema: str = Form(..., alias="schema"),   # JSON-encoded ExtractionSchema
    today: str | None = Form(None),
):
    try:
        schema_obj = ExtractionSchema.model_validate(json.loads(extraction_schema))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid schema: {e}")

    data = await audio.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    transcription = await transcribe(data, audio.filename or "audio.wav")
    extraction = await extract(transcription.text, schema_obj, today)

    return PipelineResponse(transcription=transcription, extraction=extraction)
