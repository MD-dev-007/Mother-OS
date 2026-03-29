from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


def get_service(service_name: str, version: str, credentials: Credentials) -> Any:
    return build(service_name, version, credentials=credentials)

