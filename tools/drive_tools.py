from __future__ import annotations

import json
import os
from dataclasses import dataclass
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
class DriveListTool(Tool):
    name: str = "drive.list"
    description: str = "List files from Google Drive for a connected Google account."
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
            service = get_service("drive", "v3", creds)
            resp = (
                service.files()
                .list(pageSize=10, fields="files(id, name)")
                .execute()
            )
            files_info = resp.get("files", []) or []
            names: List[str] = [f.get("name", "") for f in files_info if isinstance(f, dict)]
            names = [n for n in names if n]
            return {"status": "success", "files": names}
        except Exception as e:
            return {"status": "error", "message": f"Drive API error: {e}"}

