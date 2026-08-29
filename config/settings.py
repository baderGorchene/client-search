"""Application settings and environment configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """System-wide configuration settings loaded from environment variables."""

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram bot API token")
    TELEGRAM_CHAT_ID: str = Field(default="", description="Operator Telegram chat ID")

    # LLM API Keys
    GEMINI_API_KEY: str = Field(default="", description="Google AI Studio Gemini API key")
    GROQ_API_KEY: str = Field(default="", description="Groq Cloud API key")

    # Supabase / PostgreSQL
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_KEY: str = Field(default="", description="Supabase service role or anon key")

    # Gmail Dispatch
    GMAIL_CREDENTIALS_FILE: Path = Field(
        default=Path("config/credentials.json"),
        description="Path to OAuth2 client credentials JSON",
    )
    GMAIL_TOKEN_FILE: Path = Field(
        default=Path("config/token.json"),
        description="Path to stored OAuth2 user token JSON",
    )

    # Operational Limits & Safety
    DAILY_EMAIL_CAP: int = Field(default=15, ge=1, le=100, description="Max emails dispatched per day")
    MIN_LEAD_FIT_SCORE: int = Field(default=7, ge=1, le=10, description="Minimum lead fit score (1-10) to qualify")
    EMAIL_JITTER_MIN_SECONDS: int = Field(default=600, ge=0, description="Min seconds between dispatches (10 min)")
    EMAIL_JITTER_MAX_SECONDS: int = Field(default=1500, ge=0, description="Max seconds between dispatches (25 min)")

    # Environment
    ENVIRONMENT: str = Field(default="development", description="Execution environment (development/production/test)")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
