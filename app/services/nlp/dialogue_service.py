from typing import Any
from app.models.requests import ExtractionSchema, SchemaField, FieldType
from app.services.nlp.ollama_service import extract

FAYPASS_SCHEMA = ExtractionSchema(
    context="Senegalese intercity transport booking app. Users speak in French or Wolof.",
    fields=[
        SchemaField(name="origin_city",      type=FieldType.string, description="Departure city",        required=True),
        SchemaField(name="destination_city", type=FieldType.string, description="Arrival city",           required=True),
        SchemaField(name="date",             type=FieldType.date,   description="Travel date YYYY-MM-DD", required=False),
        SchemaField(
            name="service_type",
            type=FieldType.enum,
            description="Vehicle type",
            required=False,
            enum_values=["bus", "minibus", "sept-place"],
        ),
    ],
    hints=[
        "Senegalese cities: Dakar, Thiès, Ziguinchor, Saint-Louis, Kaolack, Touba, Mbour, Tambacounda, Kolda, Diourbel, Fatick, Louga",
        "'sept-place' is a shared 7-seat sedan taxi common in Senegal",
    ],
)

REQUIRED_FIELDS = ["origin_city", "destination_city"]
OPTIONAL_FIELDS = ["date", "service_type"]

# Wolof phrases verified against common transport vocabulary; review with a native speaker.
_QUESTIONS: dict[str, dict[str, str]] = {
    "fr": {
        "origin_city":      "D'où partez-vous ?",
        "destination_city": "Où souhaitez-vous aller ?",
        "date":             "Quelle date souhaitez-vous voyager ?",
        "service_type":     "Quel type de transport préférez-vous ? Bus, minibus ou sept-place ?",
    },
    "wo": {
        "origin_city":      "Fan nga jógël ?",
        "destination_city": "Fan ngay dem ?",
        "date":             "Bés bu ñu jëm, lañu dox ?",
        "service_type":     "Looy jëfandikoo ? Bus, minibus walla sept-place ?",
    },
}


def _lang_key(detected: str | None) -> str:
    if detected and detected.lower().startswith("wo"):
        return "wo"
    return "fr"


def _next_missing(collected: dict[str, Any], ask_optional: bool) -> str | None:
    for field in REQUIRED_FIELDS:
        if not collected.get(field):
            return field
    if ask_optional:
        for field in OPTIONAL_FIELDS:
            if collected.get(field) is None:
                return field
    return None


def _merge(collected: dict[str, Any], new_values: dict[str, Any]) -> dict[str, Any]:
    """Non-null values from the new extraction override existing slots."""
    merged = dict(collected)
    for key, value in new_values.items():
        if value is not None:
            merged[key] = value
    return merged


async def process_turn(
    text: str,
    collected: dict[str, Any],
    ask_optional: bool,
    detected_language: str | None,
    today: str | None,
) -> tuple[dict[str, Any], str | None, str | None, bool, float]:
    """
    Extract slots from `text`, merge into `collected`, determine next question.

    Returns: (updated_collected, next_question, next_question_field, is_complete, confidence)
    """
    extraction = await extract(text, FAYPASS_SCHEMA, today)
    updated = _merge(collected, extraction.extracted)

    lang = _lang_key(detected_language)
    next_field = _next_missing(updated, ask_optional)

    if next_field:
        questions = _QUESTIONS.get(lang, _QUESTIONS["fr"])
        question = questions.get(next_field, _QUESTIONS["fr"][next_field])
        return updated, question, next_field, False, extraction.confidence

    return updated, None, None, True, extraction.confidence
