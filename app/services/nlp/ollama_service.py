import json
import httpx
from datetime import date
from app.config import get_settings
from app.models.requests import ExtractionSchema, FieldType
from app.models.responses import ExtractResponse


def _build_system_prompt(schema: ExtractionSchema, today: str | None) -> str:
    today_str = today or date.today().isoformat()
    field_lines = []
    for f in schema.fields:
        type_hint = f.type.value
        if f.type == FieldType.date:
            type_hint = f'string "YYYY-MM-DD" (today is {today_str})'
        elif f.type == FieldType.datetime:
            type_hint = f'string ISO 8601 (today is {today_str})'
        elif f.type == FieldType.enum and f.enum_values:
            type_hint = f'one of: {json.dumps(f.enum_values)}'
        req = "REQUIRED" if f.required else "optional"
        field_lines.append(f'  - "{f.name}" ({type_hint}, {req}): {f.description}')

    hints_section = ""
    if schema.hints:
        hints_section = "\n\nHints:\n" + "\n".join(f"- {h}" for h in schema.hints)

    fields_section = "\n".join(field_lines)

    return f"""You are a structured data extraction assistant.
Context: {schema.context}

Extract the following fields from the user's text:
{fields_section}{hints_section}

Rules:
- Return ONLY valid JSON, no markdown, no explanation.
- Use null for fields that are absent or unclear.
- For relative dates ("tomorrow", "next Friday", "demain"), resolve to YYYY-MM-DD using today = {today_str}.
- "missing_fields" must list the names of required fields that are null.
- "confidence" is a float between 0 and 1 reflecting your certainty.

JSON schema:
{{
  "extracted": {{ {', '.join(f'"{f.name}": <{f.type.value}|null>' for f in schema.fields)} }},
  "missing_fields": ["<field_name>", ...],
  "confidence": <float>
}}"""


async def extract(text: str, schema: ExtractionSchema, today: str | None = None) -> ExtractResponse:
    settings = get_settings()
    system_prompt = _build_system_prompt(schema, today)

    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "format": "json",
        "options": {"temperature": 0},
    }

    async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
        resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
        resp.raise_for_status()

    content = resp.json()["message"]["content"]
    data = json.loads(content)

    return ExtractResponse(
        extracted=data.get("extracted", {}),
        missing_fields=data.get("missing_fields", []),
        confidence=float(data.get("confidence", 0.0)),
        raw_text=text,
    )
