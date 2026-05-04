from pydantic import BaseModel
from typing import Any


class TranscribeResponse(BaseModel):
    text: str
    language: str
    confidence: float | None = None
    duration_seconds: float | None = None


class ExtractResponse(BaseModel):
    extracted: dict[str, Any]
    missing_fields: list[str]
    confidence: float
    raw_text: str


class PipelineResponse(BaseModel):
    transcription: TranscribeResponse
    extraction: ExtractResponse
