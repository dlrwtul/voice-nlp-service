from pydantic import BaseModel, Field
from typing import Any, Literal
from enum import Enum


class FieldType(str, Enum):
    string = "string"
    integer = "integer"
    float_ = "float"
    boolean = "boolean"
    date = "date"        # → YYYY-MM-DD
    datetime = "datetime"  # → ISO 8601
    enum = "enum"


class SchemaField(BaseModel):
    name: str
    type: FieldType
    description: str
    required: bool = False
    enum_values: list[str] | None = None  # used when type == "enum"


class ExtractionSchema(BaseModel):
    context: str = Field(..., description="Description of the app/use case for the LLM")
    fields: list[SchemaField]
    hints: list[str] | None = None  # domain hints (city names, product names, etc.)


class ExtractRequest(BaseModel):
    text: str
    extraction_schema: ExtractionSchema = Field(..., alias="schema")
    today: str | None = None  # ISO date, for relative date resolution


class WhisperModel(str, Enum):
    tiny = "tiny"
    base = "base"
    small = "small"
    medium = "medium"
    large = "large-v3"
