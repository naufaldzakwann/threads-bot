"""Interface Engine generik (§3.8, §07). Service DILARANG panggil library langsung."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EngineCtx:
    account_id: int
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    engine_hint: str = ""


@dataclass
class ActionResult:
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    raw_snapshot: dict[str, Any] = field(default_factory=dict)
    engine_used: str = ""
    latency_ms: int = 0


class Engine:
    name = "base"

    async def perform(self, ctx: EngineCtx) -> ActionResult:
        raise NotImplementedError
