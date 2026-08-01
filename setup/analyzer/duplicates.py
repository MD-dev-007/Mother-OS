from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from setup.scanner.tree import should_skip_dir

_MIN_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB
_HASH_CHUNK = 64 * 1024  # first 64 KB


@dataclass
class DuplicateGroup:
    paths: List[str]
    size_each: int
    total_wasted_mb: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _partial_hash(path: Path) -> Optional[str]:
    try:
        size = path.stat().st_size
        if size < _MIN_SIZE_BYTES:
            return None
        h = hashlib.sha256()
        with path.open("rb") as f:
            h.update(f.read(_HASH_CHUNK))
        # Include size to reduce false positives from partial hash collision
        return f"{h.hexdigest()}:{size}"
    except (PermissionError, OSError):
        return None


def _iter_files(roots: Iterable[str | Path]) -> Iterable[Path]:
    for raw in roots:
        root = Path(raw)
        if not root.exists():
            continue
        if root.is_file():
            if root.stat().st_size >= _MIN_SIZE_BYTES:
                yield root
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
                current = Path(dirpath)
                if should_skip_dir(current):
                    dirnames.clear()
                    continue
                dirnames[:] = [
                    d
                    for d in dirnames
                    if not should_skip_dir(current / d)
                    and d.lower() not in {".git", "node_modules", "__pycache__", "venv", ".venv"}
                ]
                for name in filenames:
                    p = current / name
                    try:
                        if p.stat().st_size >= _MIN_SIZE_BYTES:
                            yield p
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue


def find_duplicates(
    roots: Iterable[str | Path],
    *,
    size_by_hash: Optional[Dict[str, int]] = None,
) -> List[DuplicateGroup]:
    """
    Find duplicate files by SHA-256 of first 64KB + file size (read-only).

    Only considers files larger than 1MB.
    """
    buckets: Dict[str, List[str]] = {}
    sizes: Dict[str, int] = dict(size_by_hash or {})

    seen_paths: Set[str] = set()
    for path in _iter_files(roots):
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen_paths:
            continue
        seen_paths.add(key)

        digest = _partial_hash(path)
        if digest is None:
            continue
        try:
            sizes[digest] = path.stat().st_size
        except (PermissionError, OSError):
            continue
        buckets.setdefault(digest, []).append(key)

    groups: List[DuplicateGroup] = []
    for digest, paths in buckets.items():
        if len(paths) < 2:
            continue
        size = sizes.get(digest, 0)
        wasted_bytes = size * (len(paths) - 1)
        groups.append(
            DuplicateGroup(
                paths=sorted(paths),
                size_each=size,
                total_wasted_mb=round(wasted_bytes / (1024 * 1024), 3),
            )
        )

    groups.sort(key=lambda g: g.total_wasted_mb, reverse=True)
    return groups
