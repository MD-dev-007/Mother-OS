from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

import psutil


@dataclass(frozen=True)
class DiskInfo:
    device: str
    mountpoint: str
    fstype: str
    label: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float
    is_removable: bool
    is_external: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _volume_label(mountpoint: str) -> str:
    if sys.platform != "win32":
        return ""
    try:
        import ctypes

        root = mountpoint.rstrip("\\") + "\\"
        buf = ctypes.create_unicode_buffer(261)
        serial = ctypes.c_uint32()
        max_len = ctypes.c_uint32()
        flags = ctypes.c_uint32()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(root),
            buf,
            ctypes.sizeof(buf),
            ctypes.byref(serial),
            ctypes.byref(max_len),
            ctypes.byref(flags),
            None,
            0,
        )
        if ok:
            return buf.value.strip()
    except Exception:
        pass
    return ""


def _is_removable(opts: str, mountpoint: str) -> bool:
    low = (opts or "").lower()
    if "removable" in low:
        return True
    if sys.platform == "win32":
        drive = mountpoint.rstrip("\\")[:1].upper()
        if drive and len(mountpoint) <= 3:
            try:
                import ctypes

                root = f"{drive}:\\"
                t = ctypes.windll.kernel32.GetDriveTypeW(root)  # type: ignore[attr-defined]
                # 2 = DRIVE_REMOVABLE, 5 = DRIVE_CDROM
                return t in (2, 5)
            except Exception:
                pass
    return False


def list_disks() -> List[DiskInfo]:
    """
    List all mounted disks/partitions (read-only).

    Uses psutil.disk_partitions() and disk_usage(); never writes to disks.
    """
    results: List[DiskInfo] = []
    seen_mounts: set[str] = set()

    for part in psutil.disk_partitions(all=False):
        mount = (part.mountpoint or "").strip()
        if not mount or mount in seen_mounts:
            continue
        seen_mounts.add(mount)

        try:
            usage = psutil.disk_usage(mount)
        except (PermissionError, OSError):
            continue

        removable = _is_removable(part.opts, mount)
        total = int(usage.total)
        used = int(usage.used)
        free = int(usage.free)
        pct = round((used / total) * 100, 2) if total else 0.0

        results.append(
            DiskInfo(
                device=part.device or "",
                mountpoint=mount,
                fstype=part.fstype or "",
                label=_volume_label(mount),
                total_bytes=total,
                used_bytes=used,
                free_bytes=free,
                percent_used=pct,
                is_removable=removable,
                is_external=removable,
            )
        )

    return results


def disks_as_dicts(disks: List[DiskInfo] | None = None) -> List[Dict[str, Any]]:
    items = disks if disks is not None else list_disks()
    return [d.to_dict() for d in items]
