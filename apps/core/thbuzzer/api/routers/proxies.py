"""Proxies CRUD + import + test + auto-assign (§06). Health-check threads.com."""
from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from thbuzzer.api.deps import get_session
from thbuzzer.models.all import Account, Proxy
from thbuzzer.security.crypto import encrypt
from thbuzzer.services.logic import parse_proxy

router = APIRouter(prefix="/proxies", tags=["proxies"])


class ProxyIn(BaseModel):
    url: str
    country: str = ""


@router.get("")
async def list_proxies(s=Depends(get_session)):
    rows = (await s.execute(select(Proxy))).scalars().all()
    return {"items": [{"id": p.id, "host": p.host, "port": p.port, "status": p.status,
                       "latency_ms": p.latency_ms, "country": p.country} for p in rows]}


@router.post("", status_code=201)
async def add_proxy(b: ProxyIn, s=Depends(get_session)):
    from fastapi import HTTPException
    from thbuzzer.utils.validators import Invalid as _InvX, fail as _failX, pos_int as _piX
    try:
        d = parse_proxy(b.url)
        d["port"] = _piX(d["port"], "port", max=65535)
    except ValueError as e:
        raise _failX(f"proxy tidak valid: {e}")
    except _InvX as e:
        raise _failX(f"proxy tidak valid: {e}")
    p = Proxy(protocol=d["protocol"], host=d["host"], port=d["port"], username=d.get("username", ""),
              country=b.country, status="alive")
    s.add(p)
    await s.flush()
    if d.get("password"):
        p.password_enc = encrypt(d["password"], "proxies.password_enc", str(p.id))
    await s.commit()
    return {"id": p.id}


@router.post("/test-all")
async def test_all(s=Depends(get_session)):
    rows = (await s.execute(select(Proxy))).scalars().all()
    out = []
    async with httpx.AsyncClient(timeout=10) as c:
        for p in rows:
            t0 = time.monotonic()
            try:
                r = await c.get("https://www.threads.com/")
                p.latency_ms = int((time.monotonic() - t0) * 1000)
                p.status = "alive" if r.status_code < 500 and p.latency_ms <= 3000 else "degraded"
            except Exception:
                p.status = "dead"
            out.append({"id": p.id, "status": p.status, "latency_ms": p.latency_ms})
    await s.commit()
    return {"items": out}


@router.post("/auto-assign")
async def auto_assign(body: dict, s=Depends(get_session)):
    """Sticky accounts.proxy_id, maks 3 akun/proxy (warning), cocok country≈locale."""
    from sqlalchemy import func
    counts = dict((await s.execute(select(Account.proxy_id, func.count()).where(
        Account.proxy_id.is_not(None)).group_by(Account.proxy_id))).all())
    proxies = (await s.execute(select(Proxy).where(Proxy.status == "alive"))).scalars().all()
    if not proxies:
        return {"ok": False, "message": "tidak ada proxy alive"}
    best = min(proxies, key=lambda p: counts.get(p.id, 0))
    warning = counts.get(best.id, 0) >= 3 and "warning: >3 akun/proxy" or ""
    return {"proxy_id": best.id, "load": counts.get(best.id, 0), "warning": warning}
