from fastapi import APIRouter
from app.services.nlp.ollama_service import extract
from app.models.requests import ExtractRequest
from app.models.responses import ExtractResponse

router = APIRouter(prefix="/v1", tags=["NLP"])


@router.post("/extract", response_model=ExtractResponse)
async def extract_intent(req: ExtractRequest):
    return await extract(req.text, req.schema_, req.today)
