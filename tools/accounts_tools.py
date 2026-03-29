from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

from tools.base import Tool


ACCOUNTS_FILE = os.getenv("GOOGLE_ACCOUNTS_FILE", "accounts.json")


@dataclass(frozen=True)
class AccountsListTool(Tool):
    name: str = "accounts.list"
    description: str = "List connected Google account nicknames from accounts.json."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        accounts: List[str] = []
        try:
            if not os.path.exists(ACCOUNTS_FILE):
                return {"status": "success", "accounts": accounts}

            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                return {"status": "success", "accounts": accounts}

            seen = set()
            for item in data:
                if not isinstance(item, dict):
                    continue
                nickname = item.get("nickname")
                if not isinstance(nickname, str):
                    continue
                # De-dup while keeping the first occurrence.
                key = nickname.strip()
                if not key or key.lower() in seen:
                    continue
                seen.add(key.lower())
                accounts.append(key)
        except Exception:
            # Never crash the agent for account discovery.
            return {"status": "success", "accounts": []}

        return {"status": "success", "accounts": accounts}

