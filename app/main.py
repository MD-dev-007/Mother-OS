from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.agent import build_agent
from core.intent_router import detect_intent
from llm.client import LLMClient
from utils.logger import get_logger


logger = get_logger(__name__)


def _read_query_from_cli() -> str:
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:]).strip()
    return input("motheros> ").strip()


def main() -> None:
    query = _read_query_from_cli()
    if not query:
        print("No query provided.")
        return

    intent = detect_intent(query)
    if intent == "respond":
        llm = LLMClient()
        print(llm.generate(query))
        return

    agent = build_agent()
    result = agent.invoke({"query": query})
    response = (result or {}).get("response") or ""
    print(response)


if __name__ == "__main__":
    main()

