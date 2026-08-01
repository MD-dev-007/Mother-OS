from __future__ import annotations

import os
from dataclasses import dataclass, field

from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings


def _llm_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()


def _ollama_model() -> str:
    """Return the Ollama model from env, falling back to settings or 'llama3.1'."""
    return (os.getenv("OLLAMA_MODEL") or settings.ollama_model or "llama3.1").strip()


@dataclass
class LLMClient:
    model: str = settings.google_model
    temperature: float = settings.google_temperature
    _provider: str = field(init=False, repr=False)
    _vertex: object | None = field(init=False, default=None, repr=False)
    _ollama: object | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self._provider = _llm_provider()
        self._vertex = None
        self._ollama = None
        if self._provider == "vertex":
            from llm.providers.vertex import VertexLLMClient

            self._vertex = VertexLLMClient(model_name=self.model, temperature=self.temperature)
        elif self._provider == "ollama":
            from llm.providers.ollama import OllamaLLMClient

            self._ollama = OllamaLLMClient(
                model_name=_ollama_model(),
                temperature=self.temperature,
            )

    def _client(self) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=self.model,
            temperature=self.temperature,
            api_key=settings.google_api_key,
        )

    def generate(self, prompt: str) -> str:
        if self._provider == "vertex" and self._vertex is not None:
            return self._vertex.generate(prompt)

        if self._provider == "ollama" and self._ollama is not None:
            return self._ollama.generate(prompt)

        if (not settings.google_api_key) or settings.google_api_key.strip() == "your_api_key_here":
            # Keep `python app/main.py` runnable without external setup.
            return (
                '{"final": true, "response": "GOOGLE_API_KEY is not set. '
                'Set GOOGLE_API_KEY in your environment (or a .env file) to enable LLM planning."}'
            )
        try:
            llm = self._client()
            response = llm.invoke(prompt)
            return getattr(response, "content", "") or ""
        except Exception as e:
            msg = str(e)
            if "NOT_FOUND" in msg and "models/" in msg:
                for fallback_model in ("gemini-2.5-flash", "gemini-2.0-flash"):
                    if fallback_model == self.model:
                        continue
                    try:
                        llm = ChatGoogleGenerativeAI(
                            model=fallback_model,
                            temperature=self.temperature,
                            api_key=settings.google_api_key,
                        )
                        response = llm.invoke(prompt)
                        return getattr(response, "content", "") or ""
                    except Exception:
                        pass
            # MVP: avoid crashing the whole CLI on auth/config issues.
            return (
                '{"final": true, "response": "Gemini call failed: '
                + msg.replace('"', "'")
                + '"}'
            )
