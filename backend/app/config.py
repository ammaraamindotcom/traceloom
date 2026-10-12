"""Runtime configuration loaded from environment variables, without logging secrets."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _csv_environment(name: str, default: str = "") -> list[str]:
    return [item.strip().rstrip("/") for item in os.getenv(name, default).split(",") if item.strip()]


def _database_url(value: str) -> str:
    """Accept provider URLs while using SQLAlchemy's psycopg dialect."""
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value.removeprefix("postgresql://")
    return value


APP_ENV = os.getenv("TRACELOOM_ENV", os.getenv("INTENTSHIELD_ENV", "development")).lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}
DATABASE_URL = _database_url(os.getenv("DATABASE_URL", "postgresql+psycopg://intentshield:intentshield@localhost:5432/intentshield"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")
CORS_ORIGINS = _csv_environment("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

# This value is server-only. A public Vercel build must never contain it.
INTENT_ACCESS_TOKEN = os.getenv("INTENT_ACCESS_TOKEN")
INTENT_RATE_LIMIT_REQUESTS = int(os.getenv("INTENT_RATE_LIMIT_REQUESTS", "3"))
INTENT_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("INTENT_RATE_LIMIT_WINDOW_SECONDS", "3600"))
WRITE_RATE_LIMIT_REQUESTS = int(os.getenv("WRITE_RATE_LIMIT_REQUESTS", "30"))
WRITE_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("WRITE_RATE_LIMIT_WINDOW_SECONDS", "3600"))


def validate_production_config() -> None:
    """Fail fast for unsafe production configuration without disclosing values."""
    if not IS_PRODUCTION:
        return
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL must be configured in production")
    if not CORS_ORIGINS or "*" in CORS_ORIGINS:
        raise RuntimeError("CORS_ORIGINS must list explicit production origins")
    if OPENAI_API_KEY and not INTENT_ACCESS_TOKEN:
        raise RuntimeError("INTENT_ACCESS_TOKEN is required when OpenAI intent inference is configured in production")
