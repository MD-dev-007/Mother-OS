from __future__ import annotations

import json
import os
from typing import Any, Generator, Iterator, List

import vertexai

try:
    from vertexai.preview.generative_models import GenerativeModel
except ImportError:  # pragma: no cover - preview path varies by SDK version
    from vertexai.generative_models import GenerativeModel

try:
    from vertexai.preview.generative_models import GenerationConfig
except ImportError:  # pragma: no cover
    from vertexai.generative_models import GenerationConfig

_FALLBACK_MODELS: tuple[str, ...] = ("gemini-2.5-flash", "gemini-2.0-flash-001")
_UNAVAILABLE = json.dumps({"final": True, "response": "LLM temporarily unavailable."})


def _response_text(response: Any) -> str:
    if response is None:
        return ""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    return ""


class VertexLLMClient:
    """Gemini on Vertex AI via google-cloud-aiplatform (vertexai SDK)."""

    def __init__(self, model_name: str = "gemini-1.5-pro", temperature: float = 0.0) -> None:
        self._model_name = (model_name or "gemini-1.5-pro").strip()
        self._temperature = float(temperature)
        self._project_id = (os.getenv("GOOGLE_PROJECT_ID") or "").strip()
        self._region = (os.getenv("GOOGLE_REGION") or "us-central1").strip()
        self._initialized = False

    def _ensure_init(self) -> str | None:
        """Initialize Vertex once; returns error JSON string if misconfigured."""
        if self._initialized:
            return None
        if not self._project_id:
            return json.dumps(
                {
                    "final": True,
                    "response": "GOOGLE_PROJECT_ID is not set. Set it (and GOOGLE_APPLICATION_CREDENTIALS) for Vertex AI.",
                }
            )
        try:
            vertexai.init(project=self._project_id, location=self._region)
            self._initialized = True
        except Exception as e:
            return json.dumps(
                {
                    "final": True,
                    "response": "Vertex AI init failed: " + str(e).replace('"', "'"),
                }
            )
        return None

    def _model_sequence(self) -> List[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in (self._model_name, *_FALLBACK_MODELS):
            m = m.strip()
            if not m or m in seen:
                continue
            seen.add(m)
            out.append(m)
        return out

    def generate(self, prompt: str) -> str:
        err = self._ensure_init()
        if err is not None:
            return err

        gen_cfg = GenerationConfig(temperature=self._temperature)
        last_error: str | None = None

        for model_id in self._model_sequence():
            try:
                model = GenerativeModel(model_id)
                response = model.generate_content(prompt, generation_config=gen_cfg)
                text = _response_text(response)
                if text:
                    return text
                last_error = "empty response from model"
            except Exception as e:
                last_error = str(e)
                continue

        if last_error:
            low = last_error.lower()
            if "permission" in low or "403" in low or "401" in low:
                return json.dumps(
                    {
                        "final": True,
                        "response": "Vertex AI auth failed. Check GOOGLE_APPLICATION_CREDENTIALS and IAM roles.",
                    }
                )
            if (
                "publisher model" in low
                and ("was not found" in low or "does not have access" in low or "not found" in low or "404" in low)
            ):
                models = ", ".join(self._model_sequence())
                return json.dumps(
                    {
                        "final": True,
                        "response": (
                            "Vertex model not found / not accessible in this region. "
                            f"project={self._project_id}, region={self._region}, models_tried=[{models}]. "
                            "Try a different GOOGLE_REGION (commonly us-central1) or a supported model name, "
                            "and ensure Vertex AI API is enabled and your principal has access."
                        ),
                    }
                )
            if "quota" in low or "429" in low or "resource exhausted" in low:
                return _UNAVAILABLE

        return _UNAVAILABLE

    def stream_generate(self, prompt: str) -> Generator[str, None, None]:
        err = self._ensure_init()
        if err is not None:
            yield err
            return

        gen_cfg = GenerationConfig(temperature=self._temperature)
        for model_id in self._model_sequence():
            try:
                model = GenerativeModel(model_id)
                stream = model.generate_content(prompt, generation_config=gen_cfg, stream=True)
                got_any = False
                for chunk in stream:
                    piece = getattr(chunk, "text", None) or ""
                    if piece:
                        got_any = True
                        yield piece
                if got_any:
                    return
            except Exception:
                continue
        yield _UNAVAILABLE
