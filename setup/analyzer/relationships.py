from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from rapidfuzz import fuzz

from setup.analyzer.classifier import _FolderContext, _score_software_project
from setup.onboarding.profile import UserProfile
from setup.scanner.metadata import FolderMetadata
from setup.scanner.tree import FolderNode

SIMILARITY_THRESHOLD = 80
CREATED_WITHIN_DAYS = 30


@dataclass
class RelatedGroup:
    folders: List[str]
    similarity_score: float
    likely_entity: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_iso(iso: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _created_within_days(a: FolderMetadata, b: FolderMetadata, days: int = CREATED_WITHIN_DAYS) -> bool:
    da = _parse_iso(a.created_at)
    db = _parse_iso(b.created_at)
    if da is None or db is None:
        return False
    return abs((da - db).days) <= days


def _project_indicators(node: FolderNode, path: Path, profile: UserProfile) -> bool:
    ctx = _FolderContext(
        path=path,
        node=node,
        metadata=FolderMetadata(
            path=str(path),
            last_modified="",
            last_accessed="",
            created_at="",
            total_files=0,
            total_size_mb=0.0,
            dormancy_days=0,
            dormant=False,
        ),
        profile=profile,
        fingerprint={},
    )
    signals: List[str] = []
    return _score_software_project(ctx, signals) >= 0.5


def find_related_groups(
    tree: Dict[str, FolderNode],
    metadata: Dict[str, FolderMetadata],
    profile: UserProfile,
    *,
    classifications: Optional[Dict[str, str]] = None,
) -> List[RelatedGroup]:
    """
    Find groups of related folders by name similarity and creation proximity.

    Uses rapidfuzz token_sort_ratio; read-only heuristics.
    """
    paths = list(tree.keys())
    parent_index: Dict[str, List[str]] = {}
    for norm, node in tree.items():
        if node.parent:
            parent_index.setdefault(node.parent, []).append(norm)

    used: Set[str] = set()
    groups: List[RelatedGroup] = []

    # Special rule: siblings under same parent with project indicators
    for parent, children in parent_index.items():
        if len(children) < 2:
            continue
        project_siblings = [
            c
            for c in children
            if _project_indicators(tree[c], Path(tree[c].path), profile)
        ]
        if len(project_siblings) >= 2:
            key = tuple(sorted(project_siblings))
            if not any(set(key).issubset(set(g.folders)) for g in groups):
                likely = "Software Project"
                if classifications:
                    votes = [classifications.get(c, "") for c in project_siblings]
                    likely = max(set(votes), key=votes.count) if votes else likely
                groups.append(
                    RelatedGroup(
                        folders=list(project_siblings),
                        similarity_score=95.0,
                        likely_entity=likely,
                    )
                )
                used.update(project_siblings)

    # Pairwise similarity + created_within 30 days
    for i, path_a in enumerate(paths):
        if path_a in used:
            continue
        node_a = tree[path_a]
        meta_a = metadata.get(path_a)
        if meta_a is None:
            continue
        name_a = Path(path_a).name

        cluster = [path_a]
        best_sim = 0.0

        for path_b in paths[i + 1 :]:
            if path_b in used:
                continue
            meta_b = metadata.get(path_b)
            if meta_b is None:
                continue
            if node_a.parent and tree[path_b].parent == node_a.parent:
                # Already handled or prefer sibling project rule
                pass

            name_b = Path(path_b).name
            sim = float(fuzz.token_sort_ratio(name_a, name_b))
            if sim < SIMILARITY_THRESHOLD:
                continue
            if not _created_within_days(meta_a, meta_b):
                continue

            cluster.append(path_b)
            best_sim = max(best_sim, sim)

        if len(cluster) >= 2:
            likely = "Unknown"
            if classifications:
                votes = [classifications.get(c, "Unknown") for c in cluster]
                likely = max(set(votes), key=votes.count)
            groups.append(
                RelatedGroup(
                    folders=sorted(cluster),
                    similarity_score=round(best_sim or SIMILARITY_THRESHOLD, 2),
                    likely_entity=likely,
                )
            )
            used.update(cluster)

    return groups
