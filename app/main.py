import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from app.routers import dialogue, extract, pipeline, transcribe, tts
from app.config import get_settings
from app.services.asr.whisper_service import get_model
from app.services.tts.kokoro_service import get_kokoro
import logging

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="Voice NLP Service",
    description="Generic audio → structured JSON extraction. Send audio + schema, get JSON back.",
    version="1.0.0",
)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    valid_keys = settings.get_api_keys()
    if not valid_keys:
        return await call_next(request)
    if request.url.path.startswith(("/health", "/docs", "/openapi.json", "/guide")):
        return await call_next(request)
    key = request.headers.get("X-API-Key")
    if key not in valid_keys:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


app.include_router(transcribe.router)
app.include_router(extract.router)
app.include_router(pipeline.router)
app.include_router(dialogue.router)
app.include_router(tts.router)


@app.get("/guide", include_in_schema=False)
@app.get("/guide/", include_in_schema=False)
async def serve_docs():
    return FileResponse("/service/docs/index.html", media_type="text/html")


@app.on_event("startup")
async def warmup():
    get_model()
    await asyncio.to_thread(get_kokoro)


@app.get("/health")
async def health():
    return {"status": "ok", "whisper_model": settings.whisper_model, "ollama_model": settings.ollama_model}
