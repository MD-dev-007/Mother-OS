from __future__ import annotations

import os
import re
from typing import Dict, Tuple


def get_system_paths() -> Dict[str, str]:
    home = os.path.expanduser("~")
    return {
        "home": home,
        "downloads": os.path.join(home, "Downloads"),
        "documents": os.path.join(home, "Documents"),
        "desktop": os.path.join(home, "Desktop"),
    }


def _normalize_separators(path: str) -> str:
    # Accept either slash style from the model/user.
    return os.path.normpath((path or "").strip().replace("\\", os.sep).replace("/", os.sep))


def resolve_system_path(path: str) -> str:
    if not isinstance(path, str):
        return ""

    raw = path.strip()
    if not raw:
        return ""

    paths = get_system_paths()
    home = paths["home"]
    p = os.path.expanduser(raw)
    p = _normalize_separators(p)

    # Replace hallucinated canonical path.
    if re.match(r"^[cC]:[\\/]+Users[\\/]+User(?:[\\/]|$)", p):
        suffix = re.sub(r"^[cC]:[\\/]+Users[\\/]+User", "", p)
        p = _normalize_separators(home + suffix)

    # Map generic top-level folders to actual user locations (capitalized aliases).
    # Lowercase relative paths like `downloads/file.txt` stay workspace-relative.
    if raw == "Downloads" or raw.startswith("Downloads/") or raw.startswith("Downloads\\"):
        tail = raw[len("Downloads") :].lstrip("\\/")
        p = os.path.join(paths["downloads"], tail)
    elif raw == "Documents" or raw.startswith("Documents/") or raw.startswith("Documents\\"):
        tail = raw[len("Documents") :].lstrip("\\/")
        p = os.path.join(paths["documents"], tail)
    elif raw == "Desktop" or raw.startswith("Desktop/") or raw.startswith("Desktop\\"):
        tail = raw[len("Desktop") :].lstrip("\\/")
        p = os.path.join(paths["desktop"], tail)

    # Resolve relative paths from current working directory.
    if not os.path.isabs(p):
        p = os.path.abspath(p)

    p = os.path.normpath(p)

    # If clearly directory-like, append default filename.
    ends_with_sep = raw.endswith(("/", "\\"))
    has_extension = bool(os.path.splitext(p)[1])
    directory_token = os.path.basename(p).lower() in ("downloads", "documents", "desktop")
    if ends_with_sep or os.path.isdir(p) or directory_token:
        p = os.path.join(p, "output.txt")
    elif not has_extension:
        # Filename-like path without extension.
        p = f"{p}.txt"

    return os.path.normpath(p)


def is_unsafe_file_path(path: str) -> bool:
    p = os.path.normpath((path or "").strip())
    if not p:
        return True

    # POSIX root protection.
    if p == os.path.sep:
        return True

    # Windows drive root protection.
    drive, tail = os.path.splitdrive(p)
    if drive and tail in ("\\", "/"):
        return True

    return False


def resolve_path_with_change_flag(path: str) -> Tuple[str, bool]:
    requested = os.path.normpath((path or "").strip()) if isinstance(path, str) else ""
    resolved = resolve_system_path(path if isinstance(path, str) else "")
    if not requested:
        return resolved, False
    changed = os.path.normcase(requested) != os.path.normcase(resolved)
    return resolved, changed
