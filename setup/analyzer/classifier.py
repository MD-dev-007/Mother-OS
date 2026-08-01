from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from setup.onboarding.profile import UserProfile
from setup.scanner.metadata import FolderMetadata
from setup.scanner.tree import FolderNode

_SCORE_CAP = 1.0

# MIME prefixes counted as personal / downloaded media.
_MEDIA_MIME_PREFIXES = ("image/", "video/")
_MEDIA_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".heic",
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".m4v",
    }
)
_DOC_EXTENSIONS = frozenset({".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"})
_DESIGN_EXTENSIONS = frozenset({".psd", ".ai", ".sketch", ".fig", ".xd", ".svg", ".eps"})
_PROJECT_MARKERS = frozenset(
    {
        "package.json",
        "requirements.txt",
        "pom.xml",
        "cargo.toml",
        "pyproject.toml",
        "go.mod",
        "build.gradle",
    }
)

_EVENT_YEAR_RE = re.compile(
    r"^(?:\d{4}[-_\s].+|[A-Z][a-zA-Z]+[-_\s]+\d{4}|\d{4}[-_\s][A-Z][a-zA-Z]+)$"
)


@dataclass
class ClassificationResult:
    entity_type: str
    confidence: float
    signals: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class _FolderContext:
    path: Path
    node: FolderNode
    metadata: FolderMetadata
    profile: UserProfile
    fingerprint: Dict[str, int]

    _child_names: Optional[set[str]] = field(default=None, repr=False)
    _child_dirs: Optional[set[str]] = field(default=None, repr=False)
    _child_files: Optional[set[str]] = field(default=None, repr=False)

    def refresh_listing(self) -> None:
        if self._child_names is not None:
            return
        dirs: set[str] = set()
        files: set[str] = set()
        try:
            with os.scandir(self.path) as it:
                for entry in it:
                    name = entry.name
                    if entry.is_dir(follow_symlinks=False):
                        dirs.add(name.lower())
                    elif entry.is_file(follow_symlinks=False):
                        files.add(name.lower())
        except (PermissionError, OSError):
            pass
        self._child_dirs = dirs
        self._child_files = files
        self._child_names = dirs | files

    @property
    def child_dirs(self) -> set[str]:
        self.refresh_listing()
        return self._child_dirs or set()

    @property
    def child_files(self) -> set[str]:
        self.refresh_listing()
        return self._child_files or set()

    def has_child_dir(self, name: str) -> bool:
        return name.lower() in self.child_dirs

    def has_marker_file(self, name: str) -> bool:
        return name.lower() in self.child_files

    def has_git(self) -> bool:
        if self.has_child_dir(".git"):
            return True
        return ".git" in (self.node.file_types_present or [])

    def name_matches(self, *patterns: str) -> bool:
        low = self.path.name.lower()
        return any(p in low for p in patterns)

    def is_in_downloads(self) -> bool:
        return "downloads" in [p.lower() for p in self.path.parts]

    def media_ratio(self) -> float:
        if self.fingerprint:
            total = sum(self.fingerprint.values())
            if total == 0:
                return 0.0
            media = sum(
                n
                for mime, n in self.fingerprint.items()
                if mime.startswith(_MEDIA_MIME_PREFIXES)
            )
            return media / total
        exts = {e.lower() for e in self.node.file_types_present}
        if not exts:
            return 0.0
        media_exts = exts & _MEDIA_EXTENSIONS
        return len(media_exts) / len(exts)

    def extension_ratio(self, extensions: frozenset[str]) -> float:
        exts = [e.lower() for e in self.node.file_types_present]
        if not exts:
            self.refresh_listing()
            exts = [Path(f).suffix.lower() for f in self.child_files if "." in f]
        if not exts:
            return 0.0
        hits = sum(1 for e in exts if e in extensions)
        return hits / len(exts)

    def event_name_match(self) -> bool:
        name = self.path.name.replace("_", " ").replace("-", " ")
        if _EVENT_YEAR_RE.match(self.path.name):
            return True
        if re.search(r"\b(19|20)\d{2}\b", name) and len(name.split()) >= 2:
            return True
        return False


def _cap(score: float) -> float:
    return min(_SCORE_CAP, max(0.0, round(score, 4)))


def _add(signals: List[str], score: float, delta: float, message: str) -> float:
    if delta == 0:
        return score
    signals.append(f"{message} ({delta:+.2f})")
    return score + delta


def _profile_selected(ctx: _FolderContext, entity: str) -> bool:
    return entity in (ctx.profile.selected_entities or [])


def _under_known_root(ctx: _FolderContext, entity: str) -> bool:
    root = (ctx.profile.known_roots or {}).get(entity)
    if not root or root == "scattered":
        return False
    try:
        folder = ctx.path.resolve()
        root_path = Path(root).resolve()
        return folder == root_path or root_path in folder.parents
    except (OSError, RuntimeError):
        return False


def _score_software_project(ctx: _FolderContext, signals: List[str]) -> float:
    s = 0.0
    if ctx.has_git():
        s = _add(signals, s, 0.5, "Contains .git/")
    if any(ctx.has_marker_file(m) for m in _PROJECT_MARKERS):
        s = _add(signals, s, 0.3, "Has package manifest (package.json, requirements.txt, etc.)")
    if ctx.has_child_dir("src") and (ctx.has_child_dir("tests") or ctx.has_child_dir("test")):
        s = _add(signals, s, 0.2, "Has src/ and tests/ or test/")
    if _profile_selected(ctx, "Software Project"):
        s = _add(signals, s, 0.15, 'User profile includes "Software Project"')
    if _under_known_root(ctx, "Software Project"):
        s = _add(signals, s, 0.2, "Inside known root for Software Project")
    return _cap(s)


def _score_personal_media(ctx: _FolderContext, signals: List[str]) -> float:
    s = 0.0
    ratio = ctx.media_ratio()
    if ratio > 0.6:
        s = _add(signals, s, 0.4, f">{60}% files are image/video (ratio={ratio:.0%})")
    if ctx.event_name_match():
        s = _add(signals, s, 0.3, "Folder name matches event/year naming pattern")
    if _profile_selected(ctx, "Personal Media (Family/Events)"):
        s = _add(signals, s, 0.2, 'User profile includes "Personal Media"')
    if _under_known_root(ctx, "Personal Media (Family/Events)"):
        s = _add(signals, s, 0.2, "Inside known root for Personal Media")
    if ctx.is_in_downloads():
        s = _add(signals, s, -0.2, "Folder is under Downloads/ (penalty)")
    return _cap(s)


def _score_study(ctx: _FolderContext, signals: List[str]) -> float:
    s = 0.0
    if ctx.extension_ratio(_DOC_EXTENSIONS) >= 0.4:
        s = _add(signals, s, 0.35, "High share of document types (pdf/doc/ppt)")
    if ctx.name_matches("lecture", "assignment", "semester", "course", "exam", "hw"):
        s = _add(signals, s, 0.25, "Study-related keywords in folder name")
    if ctx.has_child_dir("lectures") or ctx.has_child_dir("assignments"):
        s = _add(signals, s, 0.2, "Contains lectures/ or assignments/ subfolder")
    if _profile_selected(ctx, "Study / Course Material"):
        s = _add(signals, s, 0.15, 'User profile includes "Study / Course Material"')
    if _under_known_root(ctx, "Study / Course Material"):
        s = _add(signals, s, 0.2, "Inside known root for Study material")
    return _cap(s)


def _score_work(ctx: _FolderContext, signals: List[str]) -> float:
    s = 0.0
    if ctx.name_matches("client", "deliverable", "proposal", "contract", "invoice"):
        s = _add(signals, s, 0.3, "Work/client keywords in folder name")
    if ctx.extension_ratio(_DOC_EXTENSIONS) >= 0.3 or ctx.extension_ratio(_DESIGN_EXTENSIONS) >= 0.2:
        s = _add(signals, s, 0.25, "Deliverable-style documents or design files present")
    if ctx.has_child_dir("deliverables") or ctx.has_child_dir("output"):
        s = _add(signals, s, 0.2, "Has deliverables/ or output/ subfolder")
    if _profile_selected(ctx, "Work / Client Deliverable"):
        s = _add(signals, s, 0.15, 'User profile includes "Work / Client Deliverable"')
    if _under_known_root(ctx, "Work / Client Deliverable"):
        s = _add(signals, s, 0.2, "Inside known root for Work deliverables")
    return _cap(s)


def _score_downloaded_media(ctx: _FolderContext, signals: List[str]) -> float:
    s = 0.0
    ratio = ctx.media_ratio()
    if ratio > 0.5:
        s = _add(signals, s, 0.45, f"Mostly video/image content (ratio={ratio:.0%})")
    if ctx.name_matches("movie", "movies", "show", "series", "anime", "torrent"):
        s = _add(signals, s, 0.3, "Media library keywords in folder name")
    if ctx.is_in_downloads() or "videos" in [p.lower() for p in ctx.path.parts]:
        s = _add(signals, s, 0.2, "Under Downloads or Videos path")
    if ctx.has_git():
        s = _add(signals, s, -0.15, "Contains .git (unlikely downloaded media)")
    if _profile_selected(ctx, "Downloaded Media (Movies/Shows)"):
        s = _add(signals, s, 0.15, 'User profile includes "Downloaded Media"')
    if _under_known_root(ctx, "Downloaded Media (Movies/Shows)"):
        s = _add(signals, s, 0.2, "Inside known root for Downloaded Media")
    return _cap(s)


def _score_design(ctx: _FolderContext, signals: List[str]) -> float:
    s = 0.0
    if ctx.extension_ratio(_DESIGN_EXTENSIONS) >= 0.3:
        s = _add(signals, s, 0.4, "Design file extensions (.psd, .ai, .svg, etc.)")
    if ctx.name_matches("design", "assets", "mockup", "brand", "logo", "figma"):
        s = _add(signals, s, 0.25, "Design-related keywords in folder name")
    if ctx.has_child_dir("exports") or ctx.has_child_dir("icons"):
        s = _add(signals, s, 0.15, "Has exports/ or icons/ subfolder")
    if _profile_selected(ctx, "Design Assets"):
        s = _add(signals, s, 0.15, 'User profile includes "Design Assets"')
    if _under_known_root(ctx, "Design Assets"):
        s = _add(signals, s, 0.2, "Inside known root for Design Assets")
    return _cap(s)


def _score_documents(ctx: _FolderContext, signals: List[str]) -> float:
    s = 0.0
    if ctx.extension_ratio(_DOC_EXTENSIONS) >= 0.5:
        s = _add(signals, s, 0.4, "Mostly document/record file types")
    if ctx.name_matches("record", "tax", "receipt", "invoice", "legal", "scan"):
        s = _add(signals, s, 0.25, "Records/administrative keywords in folder name")
    if ctx.metadata.dormant:
        s = _add(signals, s, 0.1, "Dormant folder (may be archived records)")
    if _profile_selected(ctx, "Documents / Records"):
        s = _add(signals, s, 0.15, 'User profile includes "Documents / Records"')
    if _under_known_root(ctx, "Documents / Records"):
        s = _add(signals, s, 0.2, "Inside known root for Documents / Records")
    return _cap(s)


def _score_archive(ctx: _FolderContext, signals: List[str]) -> float:
    s = 0.0
    if ctx.metadata.dormant:
        s = _add(signals, s, 0.4, f"Dormant >180 days (dormancy={ctx.metadata.dormancy_days}d)")
    if ctx.name_matches("archive", "old", "backup", "misc", "unused", "temp_hold"):
        s = _add(signals, s, 0.3, "Archive/backup keywords in folder name")
    if ctx.metadata.total_files == 0 and ctx.node.child_count == 0:
        s = _add(signals, s, 0.15, "Empty leaf folder")
    if _profile_selected(ctx, "Archive / Unknown"):
        s = _add(signals, s, 0.15, 'User profile includes "Archive / Unknown"')
    return _cap(s)


_SCORERS: Dict[str, Callable[[_FolderContext, List[str]], float]] = {
    "Software Project": _score_software_project,
    "Personal Media (Family/Events)": _score_personal_media,
    "Study / Course Material": _score_study,
    "Work / Client Deliverable": _score_work,
    "Downloaded Media (Movies/Shows)": _score_downloaded_media,
    "Design Assets": _score_design,
    "Documents / Records": _score_documents,
    "Archive / Unknown": _score_archive,
}


def classify_folder(
    node: FolderNode,
    metadata: FolderMetadata,
    profile: UserProfile,
    *,
    fingerprint: Optional[Dict[str, int]] = None,
) -> ClassificationResult:
    """
    Classify a single folder using pure heuristics (no LLM).

    Only scores entity types present in user_profile.selected_entities.
    """
    ctx = _FolderContext(
        path=Path(node.path),
        node=node,
        metadata=metadata,
        profile=profile,
        fingerprint=dict(fingerprint or {}),
    )

    entities = profile.selected_entities or list(_SCORERS.keys())
    all_signals: List[str] = []
    scores: Dict[str, float] = {}

    for entity in entities:
        scorer = _SCORERS.get(entity)
        if scorer is None:
            continue
        entity_signals: List[str] = []
        scores[entity] = scorer(ctx, entity_signals)
        for sig in entity_signals:
            all_signals.append(f"[{entity}] {sig}")

    if not scores:
        return ClassificationResult(
            entity_type="Unknown",
            confidence=0.0,
            signals=["No entity types in user profile to score"],
            scores={},
        )

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_entity, best_score = ranked[0]

    if best_score <= 0 and len(ranked) > 1:
        best_entity = ranked[0][0]
        best_score = ranked[0][1]

    return ClassificationResult(
        entity_type=best_entity,
        confidence=best_score,
        signals=all_signals,
        scores=scores,
    )


def classify_tree(
    tree: Dict[str, FolderNode],
    metadata: Dict[str, FolderMetadata],
    profile: UserProfile,
    *,
    fingerprints: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, ClassificationResult]:
    """Classify every folder in a tree map."""
    fps = fingerprints or {}
    out: Dict[str, ClassificationResult] = {}
    for path, node in tree.items():
        meta = metadata.get(path)
        if meta is None:
            continue
        out[path] = classify_folder(
            node,
            meta,
            profile,
            fingerprint=fps.get(path),
        )
    return out
