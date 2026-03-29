from __future__ import annotations

from typing import Any, Dict

from utils.path_resolver import resolve_path_with_change_flag


SENSITIVE_TOOLS = {
    "file.write",
    "file.update",
    "file.delete",
    "email.send",
    "drive.upload",
    "calendar.create",
}


def validate_action(action: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Returns a structured decision for whether an action requires user approval.
    """
    try:
        if not isinstance(action, dict):
            return {"requires_approval": False}
        tool = action.get("tool")
        if not isinstance(tool, str):
            return {"requires_approval": False}
        args = action.get("args", {})
        if not isinstance(args, dict):
            args = {}

        # If a path gets rewritten by resolver, require approval and show both paths.
        if tool.startswith("file."):
            raw_path = args.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                resolved_path, changed = resolve_path_with_change_flag(raw_path)
                if changed:
                    return {
                        "requires_approval": True,
                        "reason": "Requested path was normalized for safety",
                        "requested_path": raw_path,
                        "resolved_path": resolved_path,
                    }
        if tool in SENSITIVE_TOOLS:
            return {
                "requires_approval": True,
                "reason": "This action modifies or deletes data",
            }
        return {"requires_approval": False}
    except Exception:
        # Never crash the agent due to validator issues.
        return {"requires_approval": False}

