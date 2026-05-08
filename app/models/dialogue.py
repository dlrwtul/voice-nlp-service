from pydantic import BaseModel
from typing import Any


class DialogueResponse(BaseModel):
    transcription: str | None = None
    detected_language: str | None = None
    collected: dict[str, Any]
    missing_required: list[str]
    missing_optional: list[str]
    next_question: str | None
    next_question_field: str | None
    is_complete: bool
    confidence: float
