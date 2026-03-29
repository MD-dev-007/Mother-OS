from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

from tools.base import Tool


DEFAULT_CLIENT_SECRETS = os.getenv(
    "GOOGLE_OAUTH_CLIENT_SECRETS", "config/google_client_secrets.json"
)
ACCOUNTS_FILE = os.getenv("GOOGLE_ACCOUNTS_FILE", "accounts.json")
CREDENTIALS_DIR = os.getenv("GOOGLE_CREDENTIALS_DIR", "credentials")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


@dataclass(frozen=True)
class GoogleAccountAddTool(Tool):
    name: str = "google.account.add"
    description: str = "Connect a Google account (Gmail/Drive/Calendar) via OAuth and assign a nickname."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"nickname": "string"})

    def _load_accounts(self) -> List[Dict[str, Any]]:
        if not os.path.exists(ACCOUNTS_FILE):
            return []
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _save_accounts(self, accounts: List[Dict[str, Any]]) -> None:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2)

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if not os.path.exists(DEFAULT_CLIENT_SECRETS):
            return {
                "status": "error",
                "message": f"Client secrets file not found at {DEFAULT_CLIENT_SECRETS}",
            }

        os.makedirs(CREDENTIALS_DIR, exist_ok=True)

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                DEFAULT_CLIENT_SECRETS, scopes=SCOPES
            )
            creds: Credentials = flow.run_local_server(port=0)
        except Exception as e:
            return {"status": "error", "message": f"OAuth flow failed: {e}"}

        nickname = (args or {}).get("nickname")
        if not isinstance(nickname, str) or not nickname.strip():
            return {"status": "error", "message": "Missing nickname. Pass {'nickname': 'personal'}."}
        nickname = nickname.strip()

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        cred_path = os.path.join(CREDENTIALS_DIR, f"{account_id}.json")
        try:
            with open(cred_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as e:
            return {"status": "error", "message": f"Failed to save credentials: {e}"}

        accounts = self._load_accounts()
        account_entry: Dict[str, Any] = {
            "id": account_id,
            "nickname": nickname,
            "service": "google",
            "email": None,
            "credentials_path": cred_path,
        }
        accounts.append(account_entry)
        self._save_accounts(accounts)

        return {"status": "success", "account": nickname}

