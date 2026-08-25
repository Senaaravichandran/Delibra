"""Typed, environment-driven application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="VERDICTFORGE_",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "VerdictForge"
    app_version: str = "2.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    database_path: Path = Path("data/verdictforge.db")
    request_timeout_seconds: float = Field(default=60.0, ge=5.0, le=300.0)
    max_concurrent_models: int = Field(default=4, ge=1, le=16)
    max_question_length: int = Field(default=12_000, ge=100, le=100_000)
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    api_key: str | None = None

    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    nvidia_api_key: str | None = Field(default=None, validation_alias="NVIDIA_API_KEY")
    nvidia_openai_api_key: str | None = Field(
        default=None, validation_alias="NVIDIA_OPENAI_API_KEY"
    )
    groq_model: str = "llama-3.3-70b-versatile"
    nvidia_model: str = "nvidia/llama-3.1-nemotron-nano-8b-v1"
    gpt_oss_model: str = "openai/gpt-oss-20b"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "api_key",
        "groq_api_key",
        "nvidia_api_key",
        "nvidia_openai_api_key",
        mode="before",
    )
    @classmethod
    def empty_string_is_none(cls, value: str | None) -> str | None:
        return value or None

    @property
    def is_production(self) -> bool:
        return self.environment.casefold() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings object per process."""

    return Settings()
