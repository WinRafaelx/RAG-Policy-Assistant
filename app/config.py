from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ttb Policy Assistant"
    local_mode: bool = True
    policies_dir: Path = Field(default=Path("policies"))
    retrieval_backend: str = "tfidf"
    retrieval_min_score: float = 0.08
    default_top_k: int = 3
    max_top_k: int = 5
    bootstrap_on_startup: bool = False
    database_url: str | None = None
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dimension: int = 768
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "qwen3.5:9b"
    ollama_timeout_seconds: float = 60.0
    api_key: str | None = None
    rate_limit_per_minute: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TTB_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
