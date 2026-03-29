from __future__ import annotations

from typing import Any, Dict


class Tool:
    name: str
    description: str
    args_schema: Dict[str, str]

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

