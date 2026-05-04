from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout: int = 30
    api_keys: str = ""          # comma-separated, empty = no auth
    max_audio_duration_seconds: int = 120
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_api_keys(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
