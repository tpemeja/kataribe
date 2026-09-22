from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="KATARIBE_", extra="ignore")

    gemini_api_key: str = ""
    live_model: str = "gemini-live-2.5-flash-preview"
    text_model: str = "gemini-2.5-flash"
    data_dir: Path = Path("var")
    allowed_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
