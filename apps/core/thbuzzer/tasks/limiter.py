"""Limiter 3 lapis §3.3 + §19: per-akun (§19.5), per-IP 6/mnt, global 120/mnt. Tidak bisa dimatikan."""
from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_sec: int = 60) -> bool:
        now = time.monotonic()
        dq = self._hits[key]
        while dq and now - dq[0] > window_sec:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


class TripleLimiter:
    def __init__(self, per_ip: int = 6, glob: int = 120) -> None:
        self._l = SlidingLimiter()
        self.per_ip = per_ip
        self.glob = glob

    def check(self, account_id: int, ip: str, account_per_min: int) -> tuple[bool, str]:
        if not self._l.allow(f"acct:{account_id}", account_per_min):
            return False, "account"
        if not self._l.allow(f"ip:{ip}", self.per_ip):
            return False, "ip"
        if not self._l.allow("global", self.glob):
            return False, "global"
        return True, ""
