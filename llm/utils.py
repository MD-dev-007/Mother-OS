from __future__ import annotations

import json
from typing import Any, Dict


class PlannerOutputError(ValueError):
    pass


def extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise PlannerOutputError("Planner did not return a JSON object.")
    return text[start : end + 1]


def parse_planner_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(extract_json_object(text))
    except json.JSONDecodeError as e:
        raise PlannerOutputError(f"Planner did not return valid JSON: {e}") from e

