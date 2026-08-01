from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from setup.scanner.tree import FolderNode, build_folder_tree, should_skip_dir

DORMANT_THRESHOLD_DAYS = 180


@dataclass
class FolderMetadata:
    path: str
    last_modified: str
    last_accessed: str
    created_at: str
    total_files: int
    total_size_mb: float
    dormancy_days: int
    dormant: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _folder_stat_times(path: Path) -> tuple[float, float, float]:
    try:
        st = path.stat()
        return st.st_mtime, st.st_atime, st.st_ctime
    except (PermissionError, OSError):
        now = datetime.now(timezone.utc).timestamp()
        return now, now, now


def _count_direct_files(path: Path) -> int:
    count = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False):
                    count += 1
    except (PermissionError, OSError):
        pass
    return count


def _aggregate_file_counts(tree: Dict[str, FolderNode]) -> Dict[str, int]:
    """Bottom-up file counts (direct + descendants) using tree parent links."""
    children_map: Dict[str, List[str]] = {}
    for norm, node in tree.items():
        if node.parent:
            children_map.setdefault(node.parent, []).append(norm)

    totals: Dict[str, int] = {}
    for norm, node in sorted(tree.items(), key=lambda x: x[1].depth, reverse=True):
        total = _count_direct_files(Path(node.path))
        for child in children_map.get(norm, []):
            total += totals.get(child, 0)
        totals[norm] = total
    return totals


def collect_folder_metadata(
    folder: str | Path,
    *,
    total_size_bytes: Optional[int] = None,
    total_files: Optional[int] = None,
) -> FolderMetadata:
    """
    Collect metadata for a single folder (read-only stat / scandir).
    """
    path = Path(folder)
    mtime, atime, ctime = _folder_stat_times(path)

    now = datetime.now(timezone.utc)
    last_access_dt = datetime.fromtimestamp(atime, tz=timezone.utc)
    dormancy_days = max(0, (now - last_access_dt).days)

    if total_size_bytes is None:
        total_size_bytes = 0
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        try:
                            total_size_bytes += entry.stat(follow_symlinks=False).st_size
                        except (PermissionError, OSError):
                            pass
        except (PermissionError, OSError):
            pass

    files = total_files if total_files is not None else _count_direct_files(path)

    return FolderMetadata(
        path=str(path),
        last_modified=_iso(mtime),
        last_accessed=_iso(atime),
        created_at=_iso(ctime),
        total_files=files,
        total_size_mb=round(total_size_bytes / (1024 * 1024), 3),
        dormancy_days=dormancy_days,
        dormant=dormancy_days > DORMANT_THRESHOLD_DAYS,
    )


def collect_tree_metadata(
    tree: Dict[str, FolderNode] | None = None,
) -> Dict[str, FolderMetadata]:
    """
    Build metadata for every folder in a folder tree map.
    """
    nodes = tree if tree is not None else build_folder_tree()
    file_counts = _aggregate_file_counts(nodes)
    out: Dict[str, FolderMetadata] = {}
    for norm, node in nodes.items():
        out[norm] = collect_folder_metadata(
            node.path,
            total_size_bytes=node.total_size,
            total_files=file_counts.get(norm, 0),
        )
    return out


def metadata_as_dicts(
    meta: Dict[str, FolderMetadata] | None = None,
) -> Dict[str, Dict[str, Any]]:
    items = meta if meta is not None else collect_tree_metadata()
    return {k: v.to_dict() for k, v in items.items()}
