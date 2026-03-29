from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from tools.base import Tool
load_dotenv() 

@dataclass(frozen=True)
class WebSearchTool(Tool):
    name: str = "web.search"
    description: str = "Search the web via Serper (Google Search API)."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"query": "string"})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = ((args or {}).get("query") or "").strip()
        if not query:
            return {"status": "success", "results": []}

        api_key = os.getenv("SERPER_API_KEY", "").strip()
        if not api_key :
            return {"status": "error", "message": "Search failed"}

        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query},
                timeout=20,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": "Search failed"}

            data = resp.json() if resp.content else {}
            organic = data.get("organic") or []
            results: List[str] = []
            for item in organic[:3]:
                if not isinstance(item, dict):
                    continue
                title = (item.get("title") or "").strip()
                snippet = (item.get("snippet") or "").strip()
                text = title or snippet
                if title and snippet:
                    text = f"{title} — {snippet}"
                if text:
                    results.append(text)

            return {"status": "success", "results": results[:3]}
        except Exception:
            return {"status": "error", "message": "Search failed"}

