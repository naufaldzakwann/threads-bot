"""System: info/shutdown/killswitch/diagnostics (§16)."""
from __future__ import annotations

import os
import time

import psutil
from fastapi import APIRouter
from pydantic import BaseModel

from thbuzzer import __version__
from thbuzzer.tasks.queue import KillSwitch

router = APIRouter(prefix="/system", tags=["system"])
KILL = KillSwitch()


class KillBody(BaseModel):
    scope: str = "global"
    id: int | None = None
    on: bool = True


@router.get("/info")
async def info():
    return {"app": "THBuzzer", "version": __version__, "time": int(time.time())}


@router.get("/diagnostics")
async def diagnostics():
    return {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent,
            "disk_free_gb": round(psutil.disk_usage(os.path.expanduser("~")).free / 1e9, 2)}


@router.post("/killswitch")
async def killswitch(b: KillBody):
    if b.scope == "global":
        KILL.global_kill = b.on
    elif b.scope == "account" and b.id is not None:
        (KILL.account_kill.add if b.on else KILL.account_kill.discard)(b.id)
    elif b.scope == "group" and b.id is not None:
        (KILL.group_kill.add if b.on else KILL.group_kill.discard)(b.id)
    return {"ok": True, "global": KILL.global_kill}


@router.post("/shutdown")
async def shutdown():
    import asyncio

    async def _exit():
        import time as _t
        _t.sleep(1)
        os._exit(0)

    asyncio.create_task(_exit())
    return {"ok": True, "flush": "<=15s"}
