from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from tools.base import Tool

# Schema keys that must be non-empty after coercion (no safe default).
_REQUIRED_NONEMPTY: frozenset[str] = frozenset({"path", "account", "nickname", "query"})

_STRING_DEFAULTS: Dict[str, str] = {
    "filter": "",
    "content": "",
    "body": "",
}

_STRING_DEFAULTS_SPECIAL: Dict[str, str] = {
    "subject": "No Subject",
}

_INT_DEFAULTS: Dict[str, int] = {
    "max_results": 5,
}


def _humanize_missing(fields: List[str]) -> str:
    if not fields:
        return ""
    labels = [f.replace("_", " ") for f in fields]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f" and {labels[-1]}"


def validate_and_fix_args(tool: Tool, args: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Coerce and fill defaults for tool args per args_schema.
    Returns structured result; if required values are still missing, valid=False.
    """
    schema = getattr(tool, "args_schema", None) or {}
    if not isinstance(schema, dict):
        schema = {}

    raw: Dict[str, Any] = dict(args) if isinstance(args, dict) else {}

    fixed: Dict[str, Any] = {}
    for k, v in raw.items():
        if isinstance(k, str) and k.startswith("_"):
            fixed[k] = v

    missing_fields: List[str] = []

    if not schema:
        merged = {**raw}
        for k, v in fixed.items():
            merged[k] = v
        return {
            "valid": True,
            "fixed_args": merged,
            "missing_fields": [],
            "message": "",
        }

    for key, type_hint in schema.items():
        if not isinstance(key, str):
            continue
        typ = (type_hint or "string").strip().lower()
        present = key in raw
        val = raw[key] if present else None

        if typ == "int":
            if val is None or val == "":
                default_i = _INT_DEFAULTS.get(key)
                if default_i is not None:
                    fixed[key] = default_i
                else:
                    missing_fields.append(key)
                continue
            if isinstance(val, bool):
                missing_fields.append(key)
                continue
            if isinstance(val, int):
                fixed[key] = val
                continue
            try:
                fixed[key] = int(str(val).strip())
            except (TypeError, ValueError):
                missing_fields.append(key)
            continue

        # string
        if not present or val is None:
            if key in _STRING_DEFAULTS_SPECIAL:
                fixed[key] = _STRING_DEFAULTS_SPECIAL[key]
            elif key in _STRING_DEFAULTS:
                fixed[key] = _STRING_DEFAULTS[key]
            elif key in _REQUIRED_NONEMPTY:
                missing_fields.append(key)
            else:
                fixed[key] = ""
            continue

        if isinstance(val, str):
            coerced = val.strip()
        elif isinstance(val, (int, float, bool)):
            coerced = str(val).strip()
        else:
            coerced = str(val).strip() if val is not None else ""

        if key in _REQUIRED_NONEMPTY and not coerced:
            missing_fields.append(key)
            continue

        if not coerced and key in _STRING_DEFAULTS:
            fixed[key] = _STRING_DEFAULTS[key]
        elif not coerced and key in _STRING_DEFAULTS_SPECIAL:
            fixed[key] = _STRING_DEFAULTS_SPECIAL[key]
        else:
            fixed[key] = coerced

    valid = len(missing_fields) == 0
    message = ""
    if not valid:
        msg = "Missing required fields: " + ", ".join(missing_fields)
        hint = _humanize_missing(missing_fields)
        if hint:
            message = f"{msg}. Please provide: {hint}."
        else:
            message = msg

    merged_args = {**raw, **fixed}
    for k, v in fixed.items():
        merged_args[k] = v

    return {
        "valid": valid,
        "fixed_args": merged_args,
        "missing_fields": missing_fields,
        "message": message,
    }
