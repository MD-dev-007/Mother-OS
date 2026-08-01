"""Read-only system scanner for MotherAI setup (Phase 1)."""

from setup.scanner.disk import DiskInfo, disks_as_dicts, list_disks
from setup.scanner.fingerprint import fingerprint_folder
from setup.scanner.metadata import (
    DORMANT_THRESHOLD_DAYS,
    FolderMetadata,
    collect_folder_metadata,
    collect_tree_metadata,
    metadata_as_dicts,
)
from setup.scanner.snapshot import (
    PreExecutionSnapshot,
    capture_pre_execution_snapshot,
    default_snapshots_dir,
)
from setup.scanner.tree import (
    FolderNode,
    build_folder_tree,
    default_scan_roots,
    should_skip_dir,
    tree_as_dicts,
)

__all__ = [
    "DiskInfo",
    "DORMANT_THRESHOLD_DAYS",
    "FolderMetadata",
    "FolderNode",
    "PreExecutionSnapshot",
    "build_folder_tree",
    "capture_pre_execution_snapshot",
    "collect_folder_metadata",
    "collect_tree_metadata",
    "default_scan_roots",
    "default_snapshots_dir",
    "disks_as_dicts",
    "fingerprint_folder",
    "list_disks",
    "metadata_as_dicts",
    "should_skip_dir",
    "tree_as_dicts",
]
