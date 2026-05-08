import io
import json
from datetime import date
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from app.models.dialogue import DialogueResponse
from app.services.asr.whisper_service import transcribe
from app.services.nlp.dialogue_service import OPTIONAL_FIELDS, REQUIRED_FIELDS, process_turn
from app.services.tts.kokoro_service import synthesize

router = APIRouter(prefix="/v1", tags=["Dialogue"])

_COMPLETION_MESSAGE = {
    "fr": "Parfait, je lance la recherche.",
    "wo": "Bu baax, dañuy seet.",
}


@router.post("/dialogue", response_model=DialogueResponse)
async def dialogue_turn(
    audio: UploadFile | None = File(None),
    text: str | None = Form(None),
    collected: str = Form("{}"),
    ask_optional: bool = Form(True),
    today: str | None = Form(None),
):
    """
    One turn of the slot-filling dialogue.

    Send audio OR text plus the slots already collected (as JSON string).
    Returns the updated collected slots and the next question to speak to the user,
    or is_complete=true when all required fields are filled.
    """
    if audio is None and not text:
        raise HTTPException(status_code=422, detail="Provide either 'audio' or 'text'.")

    try:
        collected_dict: dict = json.loads(collected)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="'collected' must be a valid JSON string.")

    today_str = today or date.today().isoformat()

    transcription_text, detected_language, updated, next_question, next_field, is_complete, confidence = (
        await _run_turn(audio, text, collected_dict, ask_optional, today_str)
    )

    return DialogueResponse(
        transcription=transcription_text,
        detected_language=detected_language,
        collected=updated,
        missing_required=[f for f in REQUIRED_FIELDS if not updated.get(f)],
        missing_optional=[f for f in OPTIONAL_FIELDS if updated.get(f) is None],
        next_question=next_question,
        next_question_field=next_field,
        is_complete=is_complete,
        confidence=confidence,
    )


async def _run_turn(audio, text, collected_dict, ask_optional, today_str):
    """Shared processing for both dialogue endpoints."""
    transcription_text = None
    detected_language = None

    if audio is not None:
        data = await audio.read()
        if len(data) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file.")
        result = await transcribe(data, audio.filename or "audio.wav")
        transcription_text = result.text
        detected_language = result.language
        input_text = result.text
    else:
        input_text = text

    updated, next_question, next_field, is_complete, confidence = await process_turn(
        text=input_text,
        collected=collected_dict,
        ask_optional=ask_optional,
        detected_language=detected_language,
        today=today_str,
    )
    return transcription_text, detected_language, updated, next_question, next_field, is_complete, confidence


@router.post(
    "/dialogue-audio",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "WAV of the next question (or completion prompt). Dialogue state in X-Dialogue-State header.",
        }
    },
)
async def dialogue_turn_audio(
    audio: UploadFile | None = File(None),
    text: str | None = Form(None),
    collected: str = Form("{}"),
    ask_optional: bool = Form(True),
    today: str | None = Form(None),
):
    """
    Same as /v1/dialogue but returns an MP3 audio stream of the next question.

    The full dialogue state (JSON) is available in the **X-Dialogue-State** response header
    so the client can update its local slot cache without a second request.
    """
    if audio is None and not text:
        raise HTTPException(status_code=422, detail="Provide either 'audio' or 'text'.")

    try:
        collected_dict: dict = json.loads(collected)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="'collected' must be a valid JSON string.")

    today_str = today or date.today().isoformat()

    transcription_text, detected_language, updated, next_question, next_field, is_complete, confidence = (
        await _run_turn(audio, text, collected_dict, ask_optional, today_str)
    )

    lang = detected_language[:2].lower() if detected_language else "fr"
    speak_text = next_question if not is_complete else _COMPLETION_MESSAGE.get(lang, _COMPLETION_MESSAGE["fr"])

    audio_bytes = await synthesize(speak_text, lang)

    state = DialogueResponse(
        transcription=transcription_text,
        detected_language=detected_language,
        collected=updated,
        missing_required=[f for f in REQUIRED_FIELDS if not updated.get(f)],
        missing_optional=[f for f in OPTIONAL_FIELDS if updated.get(f) is None],
        next_question=next_question,
        next_question_field=next_field,
        is_complete=is_complete,
        confidence=confidence,
    )

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/wav",
        headers={
            "Content-Disposition": "inline; filename=question.wav",
            "X-Dialogue-State": state.model_dump_json(),
            "Access-Control-Expose-Headers": "X-Dialogue-State",
        },
    )
