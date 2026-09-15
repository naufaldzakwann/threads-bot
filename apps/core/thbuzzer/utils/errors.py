"""Taxonomy error §3.5."""
from __future__ import annotations

RETRYABLE = {"E-LIMIT-RATE", "E-NET-PROXY", "E-NET-TIMEOUT"}
NO_RETRY_AUTH = {"E-AUTH-LOGIN", "E-AUTH-2FA", "E-AUTH-CHECKPOINT", "E-AUTH-TOKEN-EXPIRED", "E-AUTH-SESSION-EXPIRED"}
NO_RETRY_LIMIT = {"E-LIMIT-BLOCK", "E-LIMIT-QUOTA"}


def is_retryable(code: str) -> bool:
    return code in RETRYABLE


def backoff_minutes(attempt: int, code: str) -> int:
    if code == "E-LIMIT-RATE":
        return [5, 15, 45][min(attempt, 2)]
    if code in ("E-NET-PROXY", "E-NET-TIMEOUT"):
        return [1, 5, 25][min(attempt, 2)]
    return 0
