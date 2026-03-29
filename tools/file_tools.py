from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict

from tools.base import Tool
from utils.path_resolver import (
    is_unsafe_file_path,
    resolve_path_with_change_flag,
    resolve_system_path,
)


@dataclass(frozen=True)
class FileReadTool(Tool):
    name: str = "file.read"
    description: str = "Read a file from a given path safely."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"path": "string"})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = (args or {}).get("path") or ""
        if not isinstance(path, str) or not path.strip():
            return {"status": "error", "message": "Missing 'path' argument"}

        try:
            requested_path = path.strip()
            abs_path = resolve_system_path(requested_path)
            if is_unsafe_file_path(abs_path):
                return {"status": "error", "message": "Invalid or unsafe file path"}
            if not os.path.exists(abs_path):
                return {"status": "error", "message": "File not found"}
            # Avoid loading huge files in the MVP.
            max_bytes = int(os.getenv("MOTHEROS_MAX_READ_BYTES", "1048576"))
            if os.path.getsize(abs_path) > max_bytes:
                return {"status": "error", "message": "File too large to read"}
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                return {
                    "status": "success",
                    "content": f.read(),
                    "requested_path": requested_path,
                    "resolved_path": abs_path,
                }
        except Exception as e:
            return {"status": "error", "message": f"Read failed: {e}"}


@dataclass(frozen=True)
class FileWriteTool(Tool):
    name: str = "file.write"
    description: str = "Write a file to disk (requires user approval)."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"path": "string", "content": "string"})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = (args or {}).get("path") or ""
        content = (args or {}).get("content") or ""
        approved = bool((args or {}).get("_approved"))

        if not isinstance(path, str) or not path.strip():
            return {"status": "error", "message": "Missing 'path' argument"}
        if not isinstance(content, str):
            content = str(content)

        resolved_path, changed = resolve_path_with_change_flag(path)
        if is_unsafe_file_path(resolved_path):
            return {"status": "error", "message": "Invalid or unsafe file path"}

        if not approved:
            return {
                "status": "pending_approval",
                "tool": "file.write",
                "args": {
                    "path": path,
                    "content": content,
                    "resolved_path": resolved_path,
                    "path_modified": changed,
                },
            }

        try:
            abs_path = resolved_path
            parent = os.path.dirname(abs_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "status": "success",
                "tool": "file.write",
                "path": abs_path,
                "requested_path": path,
                "resolved_path": abs_path,
            }
        except Exception as e:
            return {"status": "error", "message": f"Write failed: {e}"}


@dataclass(frozen=True)
class FileUpdateTool(Tool):
    name: str = "file.update"
    description: str = "Update a file to disk (requires user approval)."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"path": "string", "content": "string"})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = (args or {}).get("path") or ""
        content = (args or {}).get("content") or ""
        approved = bool((args or {}).get("_approved"))

        if not isinstance(path, str) or not path.strip():
            return {"status": "error", "message": "Missing 'path' argument"}
        if not isinstance(content, str):
            content = str(content)

        resolved_path, changed = resolve_path_with_change_flag(path)
        if is_unsafe_file_path(resolved_path):
            return {"status": "error", "message": "Invalid or unsafe file path"}

        if not approved:
            return {
                "status": "pending_approval",
                "tool": "file.update",
                "args": {
                    "path": path,
                    "content": content,
                    "resolved_path": resolved_path,
                    "path_modified": changed,
                },
            }

        try:
            abs_path = resolved_path
            parent = os.path.dirname(abs_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "status": "success",
                "tool": "file.update",
                "path": abs_path,
                "requested_path": path,
                "resolved_path": abs_path,
            }
        except Exception as e:
            return {"status": "error", "message": f"Update failed: {e}"}


@dataclass(frozen=True)
class FileDeleteTool(Tool):
    name: str = "file.delete"
    description: str = "Delete a file from disk (requires user approval)."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"path": "string"})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = (args or {}).get("path") or ""
        approved = bool((args or {}).get("_approved"))

        if not isinstance(path, str) or not path.strip():
            return {"status": "error", "message": "Missing 'path' argument"}

        resolved_path, changed = resolve_path_with_change_flag(path)
        if is_unsafe_file_path(resolved_path):
            return {"status": "error", "message": "Invalid or unsafe file path"}

        if not approved:
            return {
                "status": "pending_approval",
                "tool": "file.delete",
                "args": {
                    "path": path,
                    "resolved_path": resolved_path,
                    "path_modified": changed,
                },
            }

        try:
            abs_path = resolved_path
            if os.path.exists(abs_path):
                os.remove(abs_path)
            return {
                "status": "success",
                "tool": "file.delete",
                "path": abs_path,
                "requested_path": path,
                "resolved_path": abs_path,
            }
        except Exception as e:
            return {"status": "error", "message": f"Delete failed: {e}"}

