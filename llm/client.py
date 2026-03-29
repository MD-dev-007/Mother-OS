from __future__ import annotations

from dataclasses import dataclass

from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings


@dataclass
class LLMClient:
    model: str = settings.google_model
    temperature: float = 0

    def _client(self) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=self.model,
            temperature=self.temperature,
            api_key=settings.google_api_key,
        )

    def generate(self, prompt: str) -> str:
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

