"""Tests for configuration settings."""

from pathlib import Path

from config.settings import Settings


def test_settings_default_values():
    """Verify default setting values and types."""
    cfg = Settings(
        _env_file=None,  # Do not read .env
    )
    assert cfg.DAILY_EMAIL_CAP == 15
    assert cfg.MIN_LEAD_FIT_SCORE == 7
    assert cfg.GMAIL_CREDENTIALS_FILE == Path("config/credentials.json")
    assert cfg.GMAIL_TOKEN_FILE == Path("config/token.json")
    assert cfg.EMAIL_JITTER_MIN_SECONDS == 600
    assert cfg.EMAIL_JITTER_MAX_SECONDS == 1500
    assert cfg.ENVIRONMENT == "development"


def test_settings_custom_env_override(monkeypatch):
    """Verify that environment variables properly override settings."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot_token_123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654321")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_secret_key")
    monkeypatch.setenv("GROQ_API_KEY", "groq_secret_key")
    monkeypatch.setenv("SUPABASE_URL", "https://xyz.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "supabase_service_role_secret")
    monkeypatch.setenv("DAILY_EMAIL_CAP", "25")
    monkeypatch.setenv("MIN_LEAD_FIT_SCORE", "8")

    cfg = Settings(_env_file=None)

    assert cfg.TELEGRAM_BOT_TOKEN == "test_bot_token_123"
    assert cfg.TELEGRAM_CHAT_ID == "987654321"
    assert cfg.GEMINI_API_KEY == "gemini_secret_key"
    assert cfg.GROQ_API_KEY == "groq_secret_key"
    assert cfg.SUPABASE_URL == "https://xyz.supabase.co"
    assert cfg.SUPABASE_KEY == "supabase_service_role_secret"
    assert cfg.DAILY_EMAIL_CAP == 25
    assert cfg.MIN_LEAD_FIT_SCORE == 8
