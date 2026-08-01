from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Always load project-root .env and let it override stale shell/session vars.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    # Default to a model that is currently supported by langchain-google-genai docs.
    # You can override via GOOGLE_MODEL in your environment.
    # Normalize common human-entered values like "Gemini 3.1 Pro" -> "gemini-3.1-pro".
    google_model: str = str(os.getenv("GOOGLE_MODEL", "gemini-3.1-pro")).strip().lower().replace(" ", "-")
    google_temperature: float = float(os.getenv("GOOGLE_TEMPERATURE", "0"))
    # Ollama provider settings
    ollama_model: str = str(os.getenv("OLLAMA_MODEL", "llama3.1")).strip()
    ollama_host: str = str(os.getenv("OLLAMA_HOST", "http://localhost:11434")).strip()


settings = Settings()

