from __future__ import annotations

import json
import re
from typing import Any, Dict

# Placeholders: {{key}} with optional whitespace inside braces.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def _output_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, str):
            return content
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _resolve_string(s: str, tool_outputs: Dict[str, Any]) -> str:
    if not s or "{{" not in s:
        return s

    def replace_one(match: re.Match[str]) -> str:
        key = (match.group(1) or "").strip()
        if not key or key not in tool_outputs:
            return match.group(0)
        return _output_to_str(tool_outputs[key])

    return _PLACEHOLDER_RE.sub(replace_one, s)


def _resolve_value(value: Any, tool_outputs: Dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_value(v, tool_outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(v, tool_outputs) for v in value]
    if isinstance(value, str):
        return _resolve_string(value, tool_outputs)
    return value


def resolve_variables(args: dict, tool_outputs: dict) -> dict:
    if not isinstance(args, dict):
        return {}
    outs: Dict[str, Any] = tool_outputs if isinstance(tool_outputs, dict) else {}
    return _resolve_value(dict(args), outs)
