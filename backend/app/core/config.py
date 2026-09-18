from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://ai_analyst:change-me-for-local-development@localhost:5432/ai_analyst"
    )
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 20 * 1024 * 1024
    max_dataset_rows: int = 100_000
    max_dataset_columns: int = 200
    max_xlsx_uncompressed_bytes: int = 100 * 1024 * 1024
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-5.5"
    openai_fallback_model: str | None = None
    openai_request_timeout_seconds: float = 300.0
    openai_tool_calling_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
