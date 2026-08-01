from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def default_profile_path() -> Path:
    return Path.home() / ".motherai" / "user_profile.json"


@dataclass
class UserProfile:
    selected_entities: List[str]
    entity_preferences: Dict[str, Dict[str, Any]]
    external_disk: Optional[str]
    known_roots: Dict[str, str]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UserProfile:
        return cls(
            selected_entities=list(data.get("selected_entities") or []),
            entity_preferences=dict(data.get("entity_preferences") or {}),
            external_disk=data.get("external_disk"),
            known_roots=dict(data.get("known_roots") or {}),
            created_at=str(
                data.get("created_at")
                or datetime.now(timezone.utc).isoformat()
            ),
        )

    def save(self, path: Path | None = None) -> Path:
        target = path or default_profile_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> UserProfile:
        target = path or default_profile_path()
        if not target.is_file():
            raise FileNotFoundError(f"Profile not found: {target}")
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Profile file must contain a JSON object.")
        return cls.from_dict(data)
