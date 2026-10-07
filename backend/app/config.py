"""Runtime configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Load only this project's root .env file. Existing shell variables take precedence.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://intentshield:intentshield@localhost:5432/intentshield",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")
INTENTSHIELD_ENV = os.getenv("INTENTSHIELD_ENV", "development").lower()
