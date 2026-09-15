"""Engines status + threads-tokens CRUD/refresh/test (§7.5, §16)."""
from __future__ import annotations

import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from thbuzzer import GRAPH_BASE
from thbuzzer.api.deps import get_session
from thbuzzer.engines.private_unofficial.adapter import PrivateUnofficialEngine
from thbuzzer.models.all import Account, ThreadsToken
from thbuzzer.security.crypto import decrypt, encrypt

router = APIRouter(prefix="/engines", tags=["engines"])
SCOPES = ["threads_basic", "threads_content_publish", "threads_manage_replies",
          "threads_manage_insights", "threads_keyword_search", "threads_delete"]


class TokenIn(BaseModel):
    account_id: int
    app_id: str = ""
    access_token: str
    expires_in_days: int = Field(default=60, ge=1, le=60)


@router.get("/status")
async def status():
    try:
        import playwright  # type: ignore  # noqa
        browser_ok = True
    except ImportError:
        browser_ok = False
    return {"official_api": "ok", "private_unofficial": {"degraded": PrivateUnofficialEngine._consec_bug >= 3},
            "browser": "ok" if browser_ok else "missing-dep"}


@router.get("/threads-tokens")
async def list_tokens(s=Depends(get_session)):
    rows = (await s.execute(select(ThreadsToken))).scalars().all()
    out = []
    for t in rows:
        days_left = max(0, (t.expires_at - int(time.time())) // 86400)
        out.append({"id": t.id, "account_id": t.account_id, "app_id": t.app_id,
                    "expires_at": t.expires_at, "days_left": days_left,
                    "needs_refresh": days_left <= 10})  # H-50 dari 60 hari (§7.5)
    return {"items": out}


@router.post("/threads-tokens", status_code=201)
async def save_token(b: TokenIn, s=Depends(get_session)):
    a = await s.get(Account, b.account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    t = ThreadsToken(account_id=b.account_id, app_id=b.app_id, scopes_json="[]",
                     expires_at=int(time.time()) + b.expires_in_days * 86400,
                     last_refreshed_at=int(time.time()))
    s.add(t)
    await s.flush()
    t.access_token_enc = encrypt(b.access_token, "threads_tokens.access_token_enc", str(t.id))
    t.scopes_json = '["threads_basic","threads_content_publish","threads_manage_replies"]'
    a.oauth_token_id = t.id
    a.needs_reauth = 0
    await s.commit()
    return {"id": t.id}


@router.post("/threads-tokens/{tid}/test")
async def test_token(tid: int, s=Depends(get_session)):
    t = await s.get(ThreadsToken, tid)
    if not t:
        raise HTTPException(404, "token tidak ada")
    token = decrypt(t.access_token_enc, "threads_tokens.access_token_enc", str(t.id))
    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as c:
        r = await c.get("/me", params={"fields": "id,username", "access_token": token})
        return {"status_code": r.status_code, "body": r.text[:500]}


@router.post("/threads-tokens/{tid}/refresh")
async def refresh_token(tid: int, body: dict, s=Depends(get_session)):
    """Refresh long-lived 60 hari: manual (body.access_token) atau otomatis via Meta (§7.5)."""
    from thbuzzer.services.dispatch import refresh_oauth_token
    t = await s.get(ThreadsToken, tid)
    if not t:
        raise HTTPException(404, "token tidak ada")
    if body.get("access_token"):
        t.access_token_enc = encrypt(body["access_token"], "threads_tokens.access_token_enc", str(t.id))
        t.expires_at = int(time.time()) + 60 * 86400
        t.last_refreshed_at = int(time.time())
        await s.commit()
        return {"id": t.id, "expires_at": t.expires_at, "mode": "manual"}
    r = await refresh_oauth_token(s, tid)
    if not r.get("ok"):
        raise HTTPException(401, "refresh gagal; perlu re-auth (wizard)")
    return {"id": tid, "expires_at": r["expires_at"], "mode": "auto"}


@router.post("/oauth/start")
async def oauth_start(body: dict):
    """Wizard Meta App Threads §7.5: kembalikan authorize URL untuk ditempel operator."""
    from urllib.parse import urlencode
    from thbuzzer.utils.validators import Invalid as _InvO, fail as _failO, http_url as _huO, non_empty as _neO
    try:
        app_id = _neO(body.get("app_id"), "app_id", max_len=50)
        redirect = _huO(body.get("redirect_uri"), "redirect_uri")
        scopes = body.get("scopes", SCOPES)
        if not isinstance(scopes, list) or not scopes:
            raise _InvO("scopes tidak valid: minimal 1 scope")
        unknown = [s for s in scopes if s not in SCOPES]
        if unknown:
            raise _InvO(f"scopes tidak valid: {unknown} — pilihan: {', '.join(SCOPES)}")
    except _InvO as e:
        raise _failO(str(e))
    q = urlencode({"client_id": app_id, "redirect_uri": redirect,
                   "scope": ",".join(scopes), "response_type": "code"})
    return {"authorize_url": f"https://www.threads.com/oauth/authorize?{q}", "scopes": scopes}


@router.post("/oauth/callback")
async def oauth_callback(body: dict, s=Depends(get_session)):
    """Tukar code -> short -> long-lived 60 hari, simpan terenkripsi per akun (§7.5)."""
    from thbuzzer.utils.validators import Invalid as _InvC, fail as _failC, http_url as _huC, non_empty as _neC, pos_int as _piC
    try:
        account_id = _piC(body.get("account_id"), "account_id")
        code = _neC(body.get("code"), "code", max_len=2000)
        app_id = _neC(body.get("app_id"), "app_id", max_len=50)
        app_secret = _neC(body.get("app_secret"), "app_secret", max_len=200)
        redirect = _huC(body.get("redirect_uri"), "redirect_uri")
    except _InvC as e:
        raise _failC(str(e))
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as c:
        r1 = await c.post("/oauth/access_token", data={
            "client_id": app_id, "client_secret": app_secret,
            "grant_type": "authorization_code", "redirect_uri": redirect,
            "code": code})
        if r1.status_code != 200:
            raise HTTPException(400, f"tukar code gagal: {r1.text[:200]}")
        short = r1.json()["access_token"]
        r2 = await c.get("/access_token", params={
            "grant_type": "th_exchange_token", "client_secret": app_secret,
            "access_token": short})
        if r2.status_code != 200:
            raise HTTPException(400, f"tukar long-lived gagal: {r2.text[:200]}")
        long = r2.json()
    t = ThreadsToken(account_id=a.id, app_id=app_id,
                     scopes_json=json.dumps(body.get("scopes", SCOPES)),
                     expires_at=int(time.time()) + int(long.get("expires_in", 5184000)),
                     last_refreshed_at=int(time.time()))
    s.add(t)
    await s.flush()
    t.access_token_enc = encrypt(long["access_token"], "threads_tokens.access_token_enc", str(t.id))
    a.oauth_token_id = t.id
    a.needs_reauth = 0
    # Verifikasi ringan GET /me
    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as c:
        me = await c.get("/me", params={"fields": "id,username", "access_token": long["access_token"]})
        if me.status_code == 200:
            a.threads_user_id = me.json().get("id", "")
    await s.commit()
    try:
        from thbuzzer.api.hub import broadcast
        await broadcast("account.status_changed", {"account_id": a.id, "status": a.status})
    except Exception:
        pass
    return {"token_id": t.id, "threads_user_id": a.threads_user_id}
