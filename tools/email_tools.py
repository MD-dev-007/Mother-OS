from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from tools.base import Tool
from utils.google_service import get_service

from dotenv import load_dotenv
load_dotenv()

ACCOUNTS_FILE = os.getenv("GOOGLE_ACCOUNTS_FILE", "accounts.json")
DEBUG = str(os.getenv("MOTHEROS_DEBUG", "")).lower() in ("1", "true", "yes")


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
    nickname_lower = nickname.strip().lower()
    if DEBUG:
        print(f"[email.read] resolve credentials for nickname='{nickname_lower}' from {ACCOUNTS_FILE}")

    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        acc_nickname = acc.get("nickname")
        if not isinstance(acc_nickname, str):
            continue
        if acc_nickname.strip().lower() != nickname_lower:
            continue

        cred_path = acc.get("credentials_path")
        if not isinstance(cred_path, str) or not cred_path:
            return None
        if not os.path.exists(cred_path):
            if DEBUG:
                print(f"[email.read] credentials_path does not exist: {cred_path}")
            return None

        try:
            creds = Credentials.from_authorized_user_file(cred_path)
            return creds
        except Exception:
            return None
    return None


@dataclass(frozen=True)
class EmailReadTool(Tool):
    name: str = "email.read"
    description: str = "Read emails from Gmail for a connected Google account."
    args_schema: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "args_schema", {"account": "string", "filter": "string", "max_results": "int"})

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        account = (args or {}).get("account") or ""
        if not isinstance(account, str) or not account.strip():
            return {"status": "error", "message": "Missing account nickname"}

        filter_query = (args or {}).get("filter") or ""
        if not isinstance(filter_query, str):
            filter_query = str(filter_query)

        max_results_raw = (args or {}).get("max_results", 5)
        try:
            max_results = int(max_results_raw)
        except Exception:
            max_results = 5
        max_results = max(1, min(max_results, 10))

        creds = _load_account_credentials(account)
        if not creds:
            return {
                "status": "error",
                "message": f"Account '{account}' not found. Please connect it first.",
            }

        # Refresh token if needed (no OAuth flow triggered here).
        try:
            if getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
                creds.refresh(Request())
        except Exception:
            # If refresh fails, treat as invalid credentials.
            return {
                "status": "error",
                "message": f"Account '{account}' not found. Please connect it first.",
            }

        try:
            service = get_service("gmail", "v1", creds)
            msg_list = service.users().messages().list(
                userId="me",
                q=filter_query,
                maxResults=max_results,
            ).execute()

            messages = msg_list.get("messages", []) or []
            emails: List[Dict[str, str]] = []

            for m in messages[:max_results]:
                if not isinstance(m, dict):
                    continue
                msg_id = m.get("id")
                if not msg_id:
                    continue

                msg = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_id,
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date"],
                    )
                    .execute()
                )
                headers = {
                    (h.get("name") or "").strip(): (h.get("value") or "").strip()
                    for h in msg.get("payload", {}).get("headers", [])
                    if isinstance(h, dict)
                }
                sender = headers.get("From", "")
                subject = headers.get("Subject", "")
                date = headers.get("Date", "")
                snippet = msg.get("snippet", "") or ""

                emails.append(
                    {
                        "id": str(msg_id),
                        "from": sender,
                        "subject": subject,
                        "date": date,
                        "snippet": snippet,
                    }
                )

            return {"status": "success", "emails": emails}
        except Exception as e:
            return {"status": "error", "message": "Gmail API error"}

