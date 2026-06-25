from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ttb Policy Assistant"
    local_mode: bool = True
    policies_dir: Path = Field(default=Path("policies"))
    retrieval_min_score: float = 0.08
    default_top_k: int = 3
    max_top_k: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TTB_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
