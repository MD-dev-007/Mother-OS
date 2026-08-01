from __future__ import annotations

import string
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import questionary
from questionary import Style

from setup.onboarding.profile import UserProfile, default_profile_path


ENTITY_TYPES: List[str] = [
    "Software Project",
    "Study / Course Material",
    "Work / Client Deliverable",
    "Personal Media (Family/Events)",
    "Downloaded Media (Movies/Shows)",
    "Design Assets",
    "Documents / Records",
    "Archive / Unknown",
]

_SCATTERED = "Scattered / no single location"
_NOT_ORGANIZED = "Not organized / varies"

_CUSTOM_STYLE = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("answer", "fg:green bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
    ]
)

# entity -> list of (question, choices) where choices are select options
ENTITY_FOLLOWUPS: Dict[str, List[Dict[str, Any]]] = {
    "Software Project": [
        {
            "key": "frontend_backend_split",
            "question": "Do your projects split into frontend/backend folders?",
            "choices": ["Yes", "No", "Mixed — some projects do, some don't"],
        },
        {
            "key": "project_naming",
            "question": "How are project folders typically named?",
            "choices": [
                "By project name",
                "By client name",
                "By date",
                "Inconsistent / no pattern",
            ],
        },
        {
            "key": "repo_vs_folder",
            "question": "Are most projects Git repos or plain folders?",
            "choices": [
                "Mostly Git repositories",
                "Mostly plain folders",
                "About half and half",
            ],
        },
    ],
    "Study / Course Material": [
        {
            "key": "organization_style",
            "question": "How is your study material organized?",
            "choices": [
                "By semester / term",
                "By subject",
                "By course code",
                "Mixed — several patterns",
            ],
        },
        {
            "key": "assignments_separate",
            "question": "Do you keep assignments separate from lectures?",
            "choices": ["Yes", "No", "Sometimes — depends on the course"],
        },
    ],
    "Work / Client Deliverable": [
        {
            "key": "organize_by",
            "question": "Do you organize work primarily by client or by project?",
            "choices": [
                "By client",
                "By project",
                "Nested: client then project",
                "Flat — single work folder",
            ],
        },
        {
            "key": "active_vs_archived",
            "question": "Are active and archived work kept in separate places?",
            "choices": ["Yes — clearly separated", "No — all together", "Partially"],
        },
    ],
    "Personal Media (Family/Events)": [
        {
            "key": "event_folder_naming",
            "question": "How do you name event folders?",
            "choices": [
                "By event name (e.g. Wedding-2024)",
                "By year only",
                _NOT_ORGANIZED,
            ],
        },
        {
            "key": "photos_videos_split",
            "question": "Do you separate photos and videos?",
            "choices": [
                "Yes — different folders",
                "No — same folders",
                "Sometimes",
            ],
        },
    ],
    "Downloaded Media (Movies/Shows)": [
        {
            "key": "download_organization",
            "question": "How are your downloads organized?",
            "choices": [
                "By title",
                "By genre",
                "Flat — everything in one folder",
                _NOT_ORGANIZED,
            ],
        },
        {
            "key": "movies_shows_together",
            "question": "Are movies and shows stored together?",
            "choices": [
                "Yes — same tree",
                "No — separate folders",
                "Separate drives or roots",
            ],
        },
    ],
    "Design Assets": [
        {
            "key": "primary_asset_types",
            "question": "What design asset types do you keep most often?",
            "choices": [
                "Figma / vector exports",
                "Photoshop / raster (PSD, PNG)",
                "Mixed design tools",
                "Video / motion assets",
            ],
        },
        {
            "key": "grouping_style",
            "question": "Are assets grouped by project or by file type?",
            "choices": [
                "By project",
                "By type (icons, logos, etc.)",
                "Both — project folders with type subfolders",
            ],
        },
    ],
    "Documents / Records": [
        {
            "key": "records_organization",
            "question": "How are records organized?",
            "choices": [
                "By year",
                "By category (tax, medical, etc.)",
                "Mixed year and category",
                _NOT_ORGANIZED,
            ],
        },
        {
            "key": "scanned_vs_digital",
            "question": "Are scanned documents separated from born-digital files?",
            "choices": ["Yes", "No", "Unsure / not consistent"],
        },
    ],
    "Archive / Unknown": [
        {
            "key": "old_stuff_folder",
            "question": "Do you have an 'old stuff' folder you rarely open?",
            "choices": ["Yes", "No", "Several archive-style folders"],
        },
        {
            "key": "review_unknown_during_setup",
            "question": "During setup, should we flag unknown files for your review?",
            "choices": [
                "Yes — show ambiguous items",
                "No — auto-classify with best guess only",
                "Only high-confidence items automatically",
            ],
        },
    ],
}

# Entities that get a "where is this usually kept?" root question
_ROOT_ENTITIES: Dict[str, str] = {
    "Software Project": "Where do you usually keep software projects?",
    "Study / Course Material": "Where do you usually keep study material?",
    "Work / Client Deliverable": "Where do you usually keep work deliverables?",
    "Personal Media (Family/Events)": "Where do you usually keep personal media?",
    "Downloaded Media (Movies/Shows)": "Where do you usually keep downloaded media?",
    "Design Assets": "Where do you usually keep design assets?",
    "Documents / Records": "Where do you usually keep documents and records?",
}


def _exit_cancelled() -> None:
    print("\nSetup cancelled. No changes were saved.")
    print("Run the setup wizard again when you are ready.")
    sys.exit(0)


def _ask_select(
    question: str,
    choices: List[str],
    *,
    default: Optional[str] = None,
) -> str:
    answer = questionary.select(
        question,
        choices=choices,
        style=_CUSTOM_STYLE,
        default=default,
    ).ask()
    if answer is None:
        _exit_cancelled()
    return answer


def _ask_checkbox(question: str, choices: List[str]) -> List[str]:
    answer = questionary.checkbox(
        question,
        choices=choices,
        style=_CUSTOM_STYLE,
        validate=lambda selected: True
        if selected
        else "Select at least one option (use Space to toggle).",
    ).ask()
    if answer is None:
        _exit_cancelled()
    return list(answer)


def _ask_confirm(question: str, *, default: bool = False) -> bool:
    answer = questionary.confirm(
        question,
        default=default,
        style=_CUSTOM_STYLE,
    ).ask()
    if answer is None:
        _exit_cancelled()
    return bool(answer)


def _detect_drives() -> List[str]:
    found: List[str] = []
    if sys.platform == "win32":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:/")
            if root.exists():
                found.append(f"{letter}:\\")
    else:
        found.append("/")
        media = Path("/media")
        if media.is_dir():
            for entry in sorted(media.iterdir()):
                if entry.is_dir():
                    found.append(str(entry))
        volumes = Path("/Volumes")
        if volumes.is_dir():
            for entry in sorted(volumes.iterdir()):
                if entry.is_dir() and entry.name not in found:
                    found.append(str(entry))
    return found or [str(Path.home())]


def _common_location_choices() -> List[str]:
    home = Path.home()
    candidates = [
        _SCATTERED,
        str(home / "Documents"),
        str(home / "Desktop"),
        str(home / "Downloads"),
        str(home / "Projects"),
        str(home / "Documents" / "Projects"),
        str(home / "OneDrive"),
        str(home / "Pictures"),
        str(home / "Videos"),
        str(home / "Dev"),
        str(home / "Development"),
        str(home / "src"),
        str(home / "Work"),
    ]
    for drive in _detect_drives():
        for suffix in ("Projects", "Work", "Media", "Documents"):
            candidates.append(str(Path(drive) / suffix))

    seen: set[str] = set()
    unique: List[str] = []
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path == _SCATTERED:
            unique.append(path)
            continue
        if Path(path).exists():
            unique.append(path)
    if _SCATTERED not in unique:
        unique.insert(0, _SCATTERED)
    return unique


def _run_entity_followups(entity: str) -> Dict[str, str]:
    prefs: Dict[str, str] = {}
    for item in ENTITY_FOLLOWUPS.get(entity, []):
        answer = _ask_select(
            f"[{entity}] {item['question']}",
            list(item["choices"]),
        )
        prefs[item["key"]] = answer
    return prefs


def _ask_known_roots(selected: List[str]) -> Dict[str, str]:
    roots: Dict[str, str] = {}
    locations = _common_location_choices()
    for entity in selected:
        prompt = _ROOT_ENTITIES.get(entity)
        if not prompt:
            continue
        answer = _ask_select(prompt, locations)
        if answer == _SCATTERED:
            roots[entity] = "scattered"
        else:
            roots[entity] = answer
    return roots


def _ask_external_disk() -> Optional[str]:
    has_external = _ask_confirm(
        "Do you have an external disk connected (USB drive, secondary HDD)?",
        default=False,
    )
    if not has_external:
        return None

    drives = _detect_drives()
    home_drive = ""
    if sys.platform == "win32" and Path.home().drive:
        home_drive = str(Path.home().drive) + "\\"
    external_candidates = [d for d in drives if d != home_drive] or drives

    if len(external_candidates) == 1:
        use_it = _ask_confirm(
            f"Use this drive as your external disk? ({external_candidates[0]})",
            default=True,
        )
        return external_candidates[0] if use_it else None

    return _ask_select(
        "Which drive letter or mount point is your external disk?",
        external_candidates,
    )


def run_questionnaire(*, save: bool = True) -> UserProfile:
    """
    Run the interactive onboarding questionnaire.

    Returns a UserProfile and saves it to ~/.motherai/user_profile.json by default.
    """
    print("\n  MotherAI — Digital Life Profile")
    print("  " + "─" * 40)
    print("  Answer a few questions before we scan your system.\n")

    selected = _ask_checkbox(
        "Which types of content exist on your computer? (Space to select, Enter to confirm)",
        ENTITY_TYPES,
    )

    entity_preferences: Dict[str, Dict[str, Any]] = {}
    for entity in selected:
        entity_preferences[entity] = _run_entity_followups(entity)

    external_disk = _ask_external_disk()
    known_roots = _ask_known_roots(selected)

    profile = UserProfile(
        selected_entities=selected,
        entity_preferences=entity_preferences,
        external_disk=external_disk,
        known_roots=known_roots,
    )

    if save:
        path = profile.save()
        print(f"\n  Profile saved to: {path}")
    else:
        print(f"\n  Profile ready (not saved). Default path: {default_profile_path()}")

    print("  You can continue to the system scanner when ready.\n")
    return profile


def main() -> None:
    try:
        run_questionnaire()
    except KeyboardInterrupt:
        _exit_cancelled()


if __name__ == "__main__":
    main()
