from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    mode: str
    step_history: List[Dict[str, Any]]
    tool_outputs: Dict[str, Any]
    pending_action: Dict[str, Any] | None
    step_count: int
    final: bool
    response: str
    step: int

