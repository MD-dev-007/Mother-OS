from __future__ import annotations

import json
import os
from typing import Generator

import requests

_UNAVAILABLE = json.dumps({"final": True, "response": "Ollama LLM temporarily unavailable."})


class OllamaLLMClient:
    """Local Ollama provider — calls the Ollama REST API (http://localhost:11434 by default).

    Environment variables:
        OLLAMA_HOST  - Base URL for the Ollama server (default: http://localhost:11434)
        OLLAMA_MODEL - Model name to use (default: llama3.1)
    """

    def __init__(
        self,
        model_name: str = "llama3.1",
        temperature: float = 0.0,
    ) -> None:
        self._model_name = (model_name or "llama3.1").strip()
        self._temperature = float(temperature)
        self._host = (os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_url(self) -> str:
        return f"{self._host}/api/generate"

    def _chat_url(self) -> str:
        return f"{self._host}/api/chat"

    def _build_payload(self, prompt: str, stream: bool = False) -> dict:
        payload: dict = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": self._temperature,
            },
        }
        return payload

    def _check_server(self) -> str | None:
        """Returns an error JSON string if Ollama server is unreachable, else None."""
        try:
            resp = requests.get(f"{self._host}/api/tags", timeout=5)
            if resp.status_code != 200:
                return json.dumps(
                    {
                        "final": True,
                        "response": (
                            f"Ollama server returned HTTP {resp.status_code}. "
                            f"Make sure Ollama is running at {self._host}."
                        ),
                    }
                )
        except requests.exceptions.ConnectionError:
            return json.dumps(
                {
                    "final": True,
                    "response": (
                        f"Cannot reach Ollama at {self._host}. "
                        "Start Ollama with `ollama serve` and ensure the model is pulled "
                        f"(`ollama pull {self._model_name}`)."
                    ),
                }
            )
        except Exception as e:
            return json.dumps(
                {
                    "final": True,
                    "response": "Ollama health check failed: " + str(e).replace('"', "'"),
                }
            )
        return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(self, prompt: str) -> str:
        err = self._check_server()
        if err is not None:
            return err

        try:
            resp = requests.post(
                self._generate_url(),
                json=self._build_payload(prompt, stream=False),
                timeout=120,
            )
            if resp.status_code != 200:
                return json.dumps(
                    {
                        "final": True,
                        "response": (
                            f"Ollama request failed (HTTP {resp.status_code}): {resp.text[:200]}"
                        ),
                    }
                )
            data = resp.json()
            text = (data.get("response") or "").strip()
            if not text:
                return _UNAVAILABLE
            return text
        except requests.exceptions.Timeout:
            return json.dumps(
                {
                    "final": True,
                    "response": (
                        f"Ollama request timed out after 120 s. "
                        "The model may still be loading — try again in a moment."
                    ),
                }
            )
        except Exception as e:
            return json.dumps(
                {
                    "final": True,
                    "response": "Ollama generate failed: " + str(e).replace('"', "'"),
                }
            )

    def stream_generate(self, prompt: str) -> Generator[str, None, None]:
        err = self._check_server()
        if err is not None:
            yield err
            return

        try:
            with requests.post(
                self._generate_url(),
                json=self._build_payload(prompt, stream=True),
                timeout=120,
                stream=True,
            ) as resp:
                if resp.status_code != 200:
                    yield json.dumps(
                        {
                            "final": True,
                            "response": f"Ollama stream failed (HTTP {resp.status_code}): {resp.text[:200]}",
                        }
                    )
                    return
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        piece = (chunk.get("response") or "").strip()
                        if piece:
                            yield piece
                        if chunk.get("done"):
                            break
                    except Exception:
                        continue
        except Exception as e:
            yield json.dumps(
                {
                    "final": True,
                    "response": "Ollama stream failed: " + str(e).replace('"', "'"),
                }
            )
