from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set

from setup.scanner.disk import DiskInfo, list_disks


@dataclass
class FolderNode:
    path: str
    parent: Optional[str]
    depth: int
    child_count: int
    total_size: int
    file_types_present: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Basename skips (case-insensitive).
_SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "windows",
        "program files",
        "program files (x86)",
        "$recycle.bin",
        "system volume information",
        "node_modules",
        ".git",
        "__pycache__",
        "venv",
        ".venv",
    }
)


def _normalize_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except (OSError, RuntimeError):
        return str(path)


def _is_appdata_local_temp(path: Path) -> bool:
    parts = [p.lower() for p in path.parts]
    for i in range(len(parts) - 2):
        if parts[i] == "appdata" and parts[i + 1] == "local" and parts[i + 2] == "temp":
            return True
    return False


def should_skip_dir(path: Path) -> bool:
    """Return True if this directory must not be entered (read-only check)."""
    if _is_appdata_local_temp(path):
        return True
    name = path.name.lower()
    if name in _SKIP_DIR_NAMES:
        return True
    # Skip Windows folder at drive root (e.g. C:\Windows).
    parts = [p.lower() for p in path.parts]
    if len(parts) >= 2 and parts[1] == "windows":
        return True
    return False


def default_scan_roots(extra_roots: Iterable[str | Path] | None = None) -> List[Path]:
    """User-accessible roots: home + mounted drives (non-system when possible)."""
    roots: List[Path] = []
    seen: Set[str] = set()

    def add(path: Path) -> None:
        key = _normalize_path(path)
        if key not in seen and path.exists():
            seen.add(key)
            roots.append(path)

    add(Path.home())

    for disk in list_disks():
        mp = Path(disk.mountpoint)
        add(mp)

    if extra_roots:
        for raw in extra_roots:
            add(Path(raw))

    return roots


def _extension_of(name: str) -> Optional[str]:
    suffix = Path(name).suffix.lower()
    if suffix and len(suffix) <= 12:
        return suffix
    return None


def _iter_child_dirs(path: Path) -> Iterator[Path]:
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    yield Path(entry.path)
    except (PermissionError, OSError):
        return


def _scan_direct_files(path: Path) -> tuple[int, Set[str]]:
    """Sum file sizes and extensions for files directly in `path` (not subdirs)."""
    size = 0
    exts: Set[str] = set()
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        size += entry.stat(follow_symlinks=False).st_size
                        ext = _extension_of(entry.name)
                        if ext:
                            exts.add(ext)
                    elif entry.is_dir(follow_symlinks=False):
                        if entry.name == ".git":
                            # Detect .git but do not recurse into it.
                            exts.add(".git")
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass
    return size, exts


def build_folder_tree(
    roots: Iterable[str | Path] | None = None,
    *,
    max_depth: Optional[int] = None,
) -> Dict[str, FolderNode]:
    """
    Walk user-accessible paths and return a flat map of folder metadata.

    READ-ONLY: uses os.scandir / stat only; never creates, moves, or deletes files.
    """
    root_paths = (
        [Path(r) for r in roots]
        if roots is not None
        else default_scan_roots()
    )

    # path -> (direct_file_bytes, extensions, child_folder_paths)
    raw: Dict[str, Dict[str, Any]] = {}

    stack: List[tuple[Path, Optional[str], int]] = []
    for root in root_paths:
        if root.is_dir() and not should_skip_dir(root):
            stack.append((root, None, 0))

    while stack:
        path, parent_norm, depth = stack.pop()
        if max_depth is not None and depth > max_depth:
            continue
        if should_skip_dir(path):
            continue

        norm = _normalize_path(path)
        if norm in raw:
            continue

        direct_size, exts = _scan_direct_files(path)
        child_paths: List[str] = []

        for child in _iter_child_dirs(path):
            if should_skip_dir(child):
                continue
            child_paths.append(_normalize_path(child))
            stack.append((child, norm, depth + 1))

        raw[norm] = {
            "parent": parent_norm,
            "depth": depth,
            "direct_size": direct_size,
            "exts": exts,
            "children": child_paths,
        }

    # Aggregate total_size bottom-up (deepest folders first).
    total_size: Dict[str, int] = {}
    child_count: Dict[str, int] = {}
    by_depth = sorted(raw.items(), key=lambda kv: kv[1]["depth"], reverse=True)

    for norm, info in by_depth:
        size = int(info["direct_size"])
        children: List[str] = info["children"]
        child_count[norm] = len(children)
        for child_norm in children:
            size += total_size.get(child_norm, 0)
        total_size[norm] = size

    tree: Dict[str, FolderNode] = {}
    for norm, info in raw.items():
        tree[norm] = FolderNode(
            path=norm,
            parent=info["parent"],
            depth=int(info["depth"]),
            child_count=child_count.get(norm, 0),
            total_size=total_size.get(norm, 0),
            file_types_present=sorted(info["exts"]),
        )

    return tree


def tree_as_dicts(tree: Dict[str, FolderNode] | None = None) -> Dict[str, Dict[str, Any]]:
    items = tree if tree is not None else build_folder_tree()
    return {k: v.to_dict() for k, v in items.items()}
