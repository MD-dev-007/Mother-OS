from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials

from tools.base import Tool
from utils.google_service import get_service


ACCOUNTS_FILE = os.getenv("GOOGLE_ACCOUNTS_FILE", "accounts.json")


def _load_account_credentials(nickname: str) -> Optional[Credentials]:
    if not os.path.exists(ACCOUNTS_FILE):
        return None
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)
    except Exception:
        return None
    if not isinstance(accounts, list):
        return None
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        if acc.get("nickname") == nickname:
            cred_path = acc.get("credentials_path")
            if cred_path and os.path.exists(cred_path):
                try:
                    return Credentials.from_authorized_user_file(cred_path)
                except Exception:
                    return None
    return None


@dataclass(frozen=True)
class CalendarGetTool(Tool):
    name: str = "calendar.get"
    description: str = "Get upcoming events from Google Calendar for a connected Google account."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"account": "string"})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        account = (args or {}).get("account") or ""
        if not account:
            return {"status": "error", "message": "Missing account nickname"}

        creds = _load_account_credentials(str(account))
        if not creds:
            return {"status": "error", "message": "Account not found or credentials invalid"}

        try:
            service = get_service("calendar", "v3", creds)
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=7)).isoformat()
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=5,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", []) or []
            summaries: List[str] = []
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                summary = ev.get("summary", "Untitled event")
                start = ev.get("start", {})
                when = start.get("dateTime") or start.get("date") or ""
                label = f"{when} - {summary}" if when else summary
                summaries.append(label)
            return {"status": "success", "events": summaries}
        except Exception as e:
            return {"status": "error", "message": f"Calendar API error: {e}"}

