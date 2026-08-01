from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List

try:
    from langchain.document_loaders import UnstructuredFileLoader
except ModuleNotFoundError:
    from langchain_community.document_loaders import UnstructuredFileLoader

from tools.base import Tool
from utils.path_resolver import (
    is_unsafe_file_path,
    resolve_path_with_change_flag,
    resolve_system_path,
)

_IMAGE_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".tiff",
        ".tif",
        ".heic",
        ".jfif",
        ".avif",
    }
)


def _is_image_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _IMAGE_SUFFIXES


@dataclass(frozen=True)
class FileReadTool(Tool):
    name: str = "file.read"
    description: str = (
        "Read a file from a given path safely. For images (png, jpg, etc.), extracts text and "
        "structure using Unstructured (layout + OCR); use the returned text to answer questions "
        "about what appears in the image as text or rough layout—not pixel-level vision."
    )
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"path": "string"})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = (args or {}).get("path") or ""
        if not isinstance(path, str) or not path.strip():
            return {"status": "error", "message": "Missing 'path' argument"}

        requested_path = path.strip()
        try:
            abs_path = resolve_system_path(requested_path)
        except Exception as e:
            return {"status": "error", "message": f"Failed to resolve path: {e}"}

        if is_unsafe_file_path(abs_path):
            return {
                "status": "error",
                "message": "Invalid or unsafe file path",
                "resolved_path": abs_path,
                "requested_path": requested_path,
            }

        if not os.path.exists(abs_path):
            return {
                "status": "error",
                "message": f"File not found: {abs_path}",
                "resolved_path": abs_path,
                "requested_path": requested_path,
            }

        if not os.path.isfile(abs_path):
            return {
                "status": "error",
                "message": f"Not a file: {abs_path}",
                "resolved_path": abs_path,
                "requested_path": requested_path,
            }

        max_bytes = int(os.getenv("MOTHEROS_MAX_READ_BYTES", "1048576"))
        try:
            if os.path.getsize(abs_path) > max_bytes:
                return {
                    "status": "error",
                    "message": "File too large to read",
                    "resolved_path": abs_path,
                    "requested_path": requested_path,
                }
        except OSError:
            pass

        loader_kwargs: Dict[str, Any] = {}
        if _is_image_file(abs_path):
            # Images require layout/OCR path; hi_res matches partition_image defaults and uses
            # unstructured-inference when available (else unstructured falls back per its rules).
            loader_kwargs["strategy"] = "hi_res"

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                loader = UnstructuredFileLoader(abs_path, **loader_kwargs)
                documents = loader.load()
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to read file: {str(e)}",
                "resolved_path": abs_path,
                "requested_path": requested_path,
            }

        content = "\n\n".join([doc.page_content for doc in documents])

        if _is_image_file(abs_path):
            if not (content or "").strip():
                content = (
                    "No text or layout elements could be extracted from this image "
                    "(Unstructured OCR/layout returned empty). It may be non-text artwork, "
                    "low contrast, or need different OCR settings."
                )
            else:
                content = (
                    "Extracted from image via Unstructured (layout detection + OCR). "
                    "Use this text to reason about words and structure in the image; "
                    "it is not a vision-model description of colors, objects, or fine visuals.\n\n"
                    + content
                )

        if len(content) > 10000:
            content = content[:10000] + "\n\n[TRUNCATED]"

        metadata: List[Dict[str, Any]] = [dict(doc.metadata) for doc in documents]

        out: Dict[str, Any] = {
            "status": "success",
            "content": content,
            "metadata": metadata,
            "requested_path": requested_path,
            "resolved_path": abs_path,
        }
        if _is_image_file(abs_path):
            out["content_source"] = "unstructured_image_ocr"
        return out


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

