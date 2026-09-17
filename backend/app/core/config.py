from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ai_analyst:change-me-for-local-development@localhost:5432/ai_analyst"
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 20 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
