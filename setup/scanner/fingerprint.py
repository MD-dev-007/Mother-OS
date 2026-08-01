from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Dict, List

from setup.scanner.tree import should_skip_dir

_MAGIC = None
_MAGIC_UNAVAILABLE = False


def _get_magic():
    global _MAGIC, _MAGIC_UNAVAILABLE
    if _MAGIC is not None:
        return _MAGIC
    if _MAGIC_UNAVAILABLE:
        return None
    try:
        import magic

        _MAGIC = magic.Magic(mime=True)
        return _MAGIC
    except Exception:
        _MAGIC_UNAVAILABLE = True
        return None


def _mime_for_file(path: Path) -> str:
    m = _get_magic()
    if m is not None:
        try:
            return m.from_file(str(path)) or "application/octet-stream"
        except Exception:
            pass
    import mimetypes

    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _collect_file_candidates(folder: Path, *, max_pool: int = 200) -> List[Path]:
    """Gather file paths under folder (read-only); cap pool for sampling."""
    candidates: List[Path] = []
    if not folder.is_dir():
        return candidates

    stack: List[Path] = [folder]
    while stack and len(candidates) < max_pool:
        current = stack.pop()
        if should_skip_dir(current):
            continue
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        candidates.append(Path(entry.path))
                        if len(candidates) >= max_pool:
                            break
                    elif entry.is_dir(follow_symlinks=False):
                        child = Path(entry.path)
                        if entry.name == ".git":
                            continue
                        if not should_skip_dir(child):
                            stack.append(child)
        except (PermissionError, OSError):
            continue
    return candidates


def fingerprint_folder(
    folder: str | Path,
    *,
    max_samples: int = 20,
) -> Dict[str, int]:
    """
    Sample up to `max_samples` files and return MIME type distribution.

    READ-ONLY: reads file headers via python-magic; never modifies files.
    """
    root = Path(folder)
    if not root.is_dir():
        return {}

    candidates = _collect_file_candidates(root)
    if not candidates:
        return {}

    sample_size = min(max_samples, len(candidates))
    if len(candidates) <= sample_size:
        sample = candidates
    else:
        sample = random.sample(candidates, sample_size)

    distribution: Dict[str, int] = {}
    for path in sample:
        mime = _mime_for_file(path)
        distribution[mime] = distribution.get(mime, 0) + 1
    return distribution
