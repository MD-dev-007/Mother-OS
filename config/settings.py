from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    # Default to a model that is currently supported by langchain-google-genai docs.
    # You can override via GOOGLE_MODEL in your environment.
    # Normalize common human-entered values like "Gemini 3.1 Pro" -> "gemini-3.1-pro".
    google_model: str = str(os.getenv("GOOGLE_MODEL", "gemini-3.1-pro")).strip().lower().replace(" ", "-")
    google_temperature: float = float(os.getenv("GOOGLE_TEMPERATURE", "0"))


settings = Settings()

