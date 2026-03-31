from __future__ import annotations


def detect_intent(query: str) -> str:
    q = (query or "").lower()
    keywords = ["list", "read", "file", "email", "open", "fetch", "search", "google", "find", "on", "web","send"]
    if any(k in q for k in keywords):
        return "act"
    return "respond"

