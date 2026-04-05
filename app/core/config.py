"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment and optional `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field(
        default="",
        description="OpenAI API key; required for live LLM calls.",
    )
    openai_model: str = Field(default="gpt-4o-mini", description="Default model for agent calls.")
    openai_timeout_seconds: float = Field(default=120.0, ge=5.0, le=600.0)

    llm_max_retries: int = Field(default=3, ge=1, le=10)
    llm_retry_min_wait_seconds: float = Field(default=1.0, ge=0.1)
    llm_retry_max_wait_seconds: float = Field(default=30.0, ge=1.0)

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)

    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False)

    default_max_refinement_loops: int = Field(default=2, ge=0, le=10)

    @field_validator("log_level")
    @classmethod
    def log_level_upper(cls, v: str) -> str:
        return v.upper()


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton for dependency injection."""
    return Settings()
