from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from setup.scanner.disk import DiskInfo, disks_as_dicts, list_disks
from setup.scanner.tree import FolderNode, build_folder_tree, should_skip_dir


def default_snapshots_dir() -> Path:
    return Path.home() / ".motherai" / "snapshots"


@dataclass
class PreExecutionSnapshot:
    """Full system state captured immediately before execution (read-only scan)."""

    timestamp: str
    disks: List[Dict[str, Any]]
    folder_tree: Dict[str, Dict[str, Any]]
    vscode_workspaces: List[str]
    env_file_paths: List[str]
    script_paths: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _utc_timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _find_vscode_workspaces(roots: List[Path]) -> List[str]:
    found: List[str] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            found.append(key)

    for root in roots:
        if not root.exists():
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
                current = Path(dirpath)
                if should_skip_dir(current):
                    dirnames.clear()
                    continue

                # Prune skip dirs in-place for os.walk
                dirnames[:] = [
                    d
                    for d in dirnames
                    if not should_skip_dir(current / d)
                    and d.lower() not in {".git", "node_modules", "__pycache__", "venv", ".venv"}
                ]

                if current.name == ".vscode":
                    for name in filenames:
                        if name.endswith(".code-workspace"):
                            add(current / name)

                for name in filenames:
                    if name.endswith(".code-workspace"):
                        add(current / name)
        except (PermissionError, OSError):
            continue

    return sorted(found)


def _find_env_files(roots: List[Path]) -> List[str]:
    found: List[str] = []
    seen: set[str] = set()

    for root in roots:
        if not root.exists():
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
                    if name == ".env" or name.startswith(".env."):
                        p = current / name
                        key = str(p.resolve()) if p.exists() else str(p)
                        if key not in seen:
                            seen.add(key)
                            found.append(key)
        except (PermissionError, OSError):
            continue

    return sorted(found)


def _find_scripts(roots: List[Path]) -> List[str]:
    found: List[str] = []
    seen: set[str] = set()
    suffixes = (".bat", ".cmd", ".sh", ".ps1")

    for root in roots:
        if not root.exists():
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
                    lower = name.lower()
                    if lower.endswith(suffixes):
                        p = current / name
                        key = str(p.resolve()) if p.exists() else str(p)
                        if key not in seen:
                            seen.add(key)
                            found.append(key)
        except (PermissionError, OSError):
            continue

    return sorted(found)


def capture_pre_execution_snapshot(
    *,
    tree: Dict[str, FolderNode] | None = None,
    disks: List[DiskInfo] | None = None,
    scan_roots: Optional[List[str | Path]] = None,
    output_dir: Path | None = None,
) -> Path:
    """
    Capture full pre-execution state to ~/.motherai/snapshots/{timestamp}.json.

    Intended to run ONLY immediately before mutating operations — not during
    routine scanning. All operations are read-only.
    """
    disk_list = disks if disks is not None else list_disks()
    folder_tree = tree if tree is not None else build_folder_tree(scan_roots)

    roots: List[Path] = []
    if scan_roots:
        roots = [Path(r) for r in scan_roots]
    else:
        roots = list({Path(node.path) for node in folder_tree.values()})
        if not roots:
            roots = [Path.home()]

    slim_tree: Dict[str, Dict[str, Any]] = {
        path: {
            "path": node.path,
            "parent": node.parent,
            "depth": node.depth,
            "child_count": node.child_count,
            "total_size": node.total_size,
            "file_types_present": node.file_types_present,
        }
        for path, node in folder_tree.items()
    }

    ts = _utc_timestamp_slug()
    snapshot = PreExecutionSnapshot(
        timestamp=ts,
        disks=disks_as_dicts(disk_list),
        folder_tree=slim_tree,
        vscode_workspaces=_find_vscode_workspaces(roots),
        env_file_paths=_find_env_files(roots),
        script_paths=_find_scripts(roots),
    )

    out_dir = output_dir or default_snapshots_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts}.json"
    out_path.write_text(
        json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path
