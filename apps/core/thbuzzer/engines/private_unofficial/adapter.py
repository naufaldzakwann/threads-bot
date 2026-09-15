"""Adapter unofficial fragile/eksperimental §7.2. Pluggable, isolasi total error ke E-*.

JANGAN jadikan tumpuan tunggal. 3x E-ENGINE-BUG beruntun -> degraded_engine 24 jam + fallback browser.
Login via kredensial IG + cached_token_path bersama.
"""
from __future__ import annotations

import time

from thbuzzer.engines.base import ActionResult, Engine, EngineCtx

ERROR_MAP = {
    "4279013": "E-LIMIT-BLOCK",
    "feedback_required": "E-LIMIT-BLOCK",
    "challenge_required": "E-AUTH-CHECKPOINT",
    "login_required": "E-AUTH-SESSION-EXPIRED",
    "rate_limit": "E-LIMIT-RATE",
}


def map_private_error(raw: str) -> str:
    low = (raw or "").lower()
    for k, v in ERROR_MAP.items():
        if k.lower() in low:
            return v
    return "E-ENGINE-BUG"


class PrivateUnofficialEngine(Engine):
    name = "private_unofficial"
    _consec_bug = 0

    async def perform(self, ctx: EngineCtx) -> ActionResult:
        t0 = time.monotonic()
        try:
            # v1: modul pihak ketiga belum di-bundle; tandai degraded agar router fallback ke browser.
            raise RuntimeError("private_unofficial backend not configured (fragile, pin sadar)")
        except Exception as e:  # noqa: BLE001
            code = map_private_error(str(e))
            type(self)._consec_bug += 1
            return ActionResult(
                False, error_code=code, engine_used=self.name,
                raw_snapshot={"err": str(e), "consec_bug": type(self)._consec_bug},
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
