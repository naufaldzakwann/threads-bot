"""Analytics §12: dashboard, series, threads, logs, jobs, dead-letter. Alerts + AI + Settings."""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from thbuzzer.api.deps import get_session
from thbuzzer.models.all import (Account, AccountStatsSnapshot, ActivityLog, AIProfile,
                                 AIUsage, AlertHistory, Interaction, Job, ScheduledThread)
from thbuzzer.security.crypto import encrypt

analytics = APIRouter(prefix="/analytics", tags=["analytics"])
alerts = APIRouter(prefix="/alerts", tags=["alerts"])
ai = APIRouter(prefix="/ai", tags=["ai"])
settings = APIRouter(prefix="/settings", tags=["settings"])


@analytics.get("/dashboard")
async def dashboard(s=Depends(get_session)):
    by_status = dict((await s.execute(select(Account.status, func.count()).where(
        Account.deleted == 0).group_by(Account.status))).all())
    last24 = int(time.time()) - 86400
    acts24 = (await s.execute(select(func.count()).select_from(Interaction).where(
        Interaction.created_at >= last24))).scalar() or 0
    return {"accounts_by_status": by_status, "actions_24h": acts24,
            "alerts": ["threads_quota_90", "search_quota_weekly_80"]}


@analytics.get("/threads")
async def threads(account_id: int = 0, s=Depends(get_session)):
    q = select(ScheduledThread)
    if account_id:
        q = q.where(ScheduledThread.account_id == account_id)
    rows = (await s.execute(q.limit(200))).scalars().all()
    return {"items": [{"id": t.id, "status": t.status, "topic_tag": t.topic_tag} for t in rows]}


@analytics.get("/logs")
async def logs(limit: int = Query(default=50, ge=1, le=500), s=Depends(get_session)):
    rows = (await s.execute(select(ActivityLog).order_by(ActivityLog.id.desc()).limit(min(limit, 500)))).scalars().all()
    return {"items": [{"id": l.id, "action": l.action, "status": l.status, "message": l.message} for l in rows]}


@analytics.get("/jobs")
async def jobs(status: str = "", s=Depends(get_session)):
    q = select(Job)
    if status:
        q = q.where(Job.status == status)
    rows = (await s.execute(q.limit(200))).scalars().all()
    return {"items": [{"id": j.id, "type": j.type, "status": j.status, "attempt": j.attempt} for j in rows]}


@analytics.get("/dead-letter")
async def dead_letter(s=Depends(get_session)):
    rows = (await s.execute(select(Job).where(Job.status == "dead_letter").limit(200))).scalars().all()
    return {"items": [{"id": j.id, "type": j.type} for j in rows]}


@analytics.get("/series/account")
async def series_account(account_id: int = Query(ge=1), days: int = Query(default=30, ge=1, le=365), s=Depends(get_session)):
    import time as _t
    rows = (await s.execute(select(AccountStatsSnapshot).where(
        AccountStatsSnapshot.account_id == account_id,
        AccountStatsSnapshot.created_at >= int(_t.time()) - days * 86400)
        .order_by(AccountStatsSnapshot.created_at))).scalars().all()
    return {"items": [{"t": r.created_at, "followers": r.followers, "following": r.following,
                       "threads": r.thread_count, "views": r.views, "likes": r.likes,
                       "replies": r.replies, "reposts": r.reposts, "quotes": r.quotes} for r in rows]}


@analytics.post("/snapshot-now")
async def snapshot_now(body: dict, s=Depends(get_session)):
    import time as _t
    from thbuzzer.tasks.queue import enqueue
    from thbuzzer.utils.validators import Invalid as _InvS, fail as _failS, pos_int as _piS
    try:
        account_id = _piS(body.get("account_id"), "account_id")
    except _InvS as e:
        raise _failS(str(e))
    job = await enqueue(s, "snapshot", account_id=account_id, priority="high",
                        payload={}, scheduled_at=int(_t.time()),
                        dedup_key=f"snapnow:{account_id}:{_t.time_ns()}")
    await s.commit()
    return {"job_id": job.id}


@analytics.post("/jobs/{jid}/retry")
async def job_retry(jid: int, s=Depends(get_session)):
    from fastapi import HTTPException
    j = await s.get(Job, jid)
    if not j:
        raise HTTPException(404, "job tidak ada")
    j.status = "pending"
    j.attempt = 0
    await s.commit()
    return {"ok": True}


@analytics.post("/jobs/{jid}/cancel")
async def job_cancel(jid: int, s=Depends(get_session)):
    from fastapi import HTTPException
    j = await s.get(Job, jid)
    if not j:
        raise HTTPException(404, "job tidak ada")
    j.status = "cancelled"
    await s.commit()
    return {"ok": True}


@analytics.get("/recurring")
async def recurring_list(s=Depends(get_session)):
    from thbuzzer.models.all import RecurringJob
    rows = (await s.execute(select(RecurringJob))).scalars().all()
    return {"items": [{"name": r.name, "note": r.cron_note, "enabled": r.enabled} for r in rows]}


@analytics.post("/recurring/{name}")
async def recurring_toggle(name: str, body: dict, s=Depends(get_session)):
    from fastapi import HTTPException
    from thbuzzer.models.all import RecurringJob
    r = (await s.execute(select(RecurringJob).where(RecurringJob.name == name))).scalars().first()
    if not r:
        raise HTTPException(404, "recurring tidak ada")
    r.enabled = 1 if body.get("enabled", True) else 0
    await s.commit()
    return {"ok": True, "enabled": r.enabled}


@alerts.get("/history")
async def alert_history(s=Depends(get_session)):
    rows = (await s.execute(select(AlertHistory).order_by(AlertHistory.id.desc()).limit(100))).scalars().all()
    return {"items": [{"id": a.id, "kind": a.kind, "message": a.message} for a in rows]}


@alerts.post("/test")
async def alert_test(body: dict, s=Depends(get_session)):
    s.add(AlertHistory(kind=body.get("channel", "desktop"), message="test alert"))
    await s.commit()
    return {"ok": True}


@alerts.get("/settings")
async def alert_settings(s=Depends(get_session)):
    from thbuzzer.models.all import SettingsKV
    out = {}
    for k in ("alerts.webhook_url", "alerts.telegram_bot_token", "alerts.telegram_chat_id",
              "alerts.quiet_hours"):
        row = await s.get(SettingsKV, k)
        out[k] = ("***" if "token" in k and row and row.value else (row.value if row else ""))
    return out


@alerts.post("/settings")
async def save_alert_settings(body: dict, s=Depends(get_session)):
    from thbuzzer.models.all import SettingsKV
    from thbuzzer.utils.validators import QUIET_RE, Invalid as _InvA, fail as _failA, http_url as _huA
    try:
        if "alerts.webhook_url" in body and body["alerts.webhook_url"]:
            body["alerts.webhook_url"] = _huA(body["alerts.webhook_url"], "alerts.webhook_url")
        if "alerts.quiet_hours" in body and body["alerts.quiet_hours"]:
            if not QUIET_RE.match(str(body["alerts.quiet_hours"]).strip()):
                raise _InvA("alerts.quiet_hours tidak valid: format JJ:MM-JJ:MM (contoh 22:00-08:00)")
    except _InvA as e:
        raise _failA(str(e))
    for k in ("alerts.webhook_url", "alerts.telegram_bot_token", "alerts.telegram_chat_id",
              "alerts.quiet_hours"):
        if k in body:
            row = await s.get(SettingsKV, k)
            if row:
                row.value = str(body[k])
            else:
                s.add(SettingsKV(key=k, value=str(body[k])))
    await s.commit()
    return {"ok": True}


class AIProfileIn(BaseModel):
    name: str = "default"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    rpm: int = Field(default=60, ge=1, le=10000)
    daily_budget: float = Field(default=5.0, ge=0, le=100000)

    @field_validator("name", "model", "base_url")
    @classmethod
    def _ne(cls, v: str, info) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError(f"{info.field_name} tidak valid: wajib diisi")
        return v


@ai.get("/profiles")
async def ai_profiles(s=Depends(get_session)):
    rows = (await s.execute(select(AIProfile))).scalars().all()
    return {"items": [{"id": p.id, "name": p.name, "model": p.model} for p in rows]}


@ai.post("/profiles", status_code=201)
async def ai_create(b: AIProfileIn, s=Depends(get_session)):
    p = AIProfile(name=b.name, base_url=b.base_url, model=b.model, rpm=b.rpm, daily_budget=b.daily_budget)
    s.add(p)
    await s.flush()
    if b.api_key:
        p.api_key_enc = encrypt(b.api_key, "ai_profiles.api_key_enc", str(p.id))
    await s.commit()
    return {"id": p.id}


@ai.get("/usage")
async def ai_usage(s=Depends(get_session)):
    rows = (await s.execute(select(AIUsage).order_by(AIUsage.id.desc()).limit(100))).scalars().all()
    return {"items": [{"id": u.id, "tokens": u.tokens, "cost": u.cost} for u in rows]}


@ai.post("/test")
async def ai_test(body: dict):
    if not body.get("api_key"):
        return {"ok": True, "mode": "template-fallback", "badge": "AI nonaktif"}
    return {"ok": True, "mode": "llm"}


@ai.get("/personas")
async def personas(s=Depends(get_session)):
    from thbuzzer.models.all import Persona
    rows = (await s.execute(select(Persona))).scalars().all()
    return {"items": [{"id": p.id, "name": p.name, "group_id": p.group_id} for p in rows]}


@ai.post("/personas", status_code=201)
async def persona_create(body: dict, s=Depends(get_session)):
    from thbuzzer.models.all import Persona
    from thbuzzer.utils.validators import Invalid as _InvP2, fail as _failP2, non_empty as _neP, pos_int as _piP
    try:
        name = _neP(body.get("name"), "name", max_len=100)
        gid = _piP(body.get("group_id"), "group_id") if body.get("group_id") is not None else None
    except _InvP2 as e:
        raise _failP2(str(e))
    p = Persona(name=name, group_id=gid,
                spec_json=json.dumps(body.get("spec", {}), ensure_ascii=False))
    s.add(p)
    await s.commit()
    return {"id": p.id}


@ai.get("/prompts")
async def prompts(s=Depends(get_session)):
    from thbuzzer.models.all import SettingsKV
    row = await s.get(SettingsKV, "ai.prompts")
    return json.loads(row.value) if row and row.value else {}


@ai.post("/prompts")
async def save_prompts(body: dict, s=Depends(get_session)):
    from thbuzzer.models.all import SettingsKV
    from thbuzzer.utils.validators import Invalid as _InvPr, fail as _failPr
    if not isinstance(body, dict):
        raise _failPr("prompts tidak valid: harus objek JSON")
    row = await s.get(SettingsKV, "ai.prompts")
    val = json.dumps(body, ensure_ascii=False)
    if row:
        row.value = val
    else:
        s.add(SettingsKV(key="ai.prompts", value=val))
    await s.commit()
    return {"ok": True}


@ai.post("/generate")
async def ai_generate(body: dict, s=Depends(get_session)):
    """Generate reply/quote_rewrite/thread_caption/campaign_reply (fallback template tanpa key)."""
    from fastapi import HTTPException
    from thbuzzer.security.crypto import decrypt
    from thbuzzer.services.ai import generate
    from thbuzzer.utils.validators import Invalid as _InvG, fail as _failG, one_of as _oneG, pos_int as _piG
    try:
        profile_id = _piG(body.get("profile_id", 0), "profile_id", min=0, max=2**31 - 1)
        account_id = _piG(body.get("account_id", 0), "account_id", min=0, max=2**31 - 1)
        max_chars = _piG(body.get("max_chars", 500), "max_chars", max=500)
        kind = _oneG(body.get("kind", "reply"), "kind",
                     {"reply", "quote_rewrite", "thread_caption", "campaign_reply"})
        stance = _oneG(body.get("stance", "mendukung"), "stance",
                       {"mendukung", "kepo", "testimonial", "reply_komentar_lain"})
        context = str(body.get("context", ""))
        if not context.strip():
            raise _InvG("context tidak valid: wajib diisi")
    except _InvG as e:
        raise _failG(str(e))
    p = await s.get(AIProfile, profile_id)
    prof = {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"}
    if p:
        prof.update({"base_url": p.base_url, "model": p.model})
        if p.api_key_enc:
            try:
                prof["api_key"] = decrypt(p.api_key_enc, "ai_profiles.api_key_enc", str(p.id))
            except Exception:
                pass
    elif profile_id:
        raise HTTPException(404, "profil AI tidak ada")
    return await generate(prof, str(body.get("persona", "")), kind, context, stance, max_chars, account_id)


@settings.get("")
async def get_settings_all(s=Depends(get_session)):
    from thbuzzer.models.all import SettingsKV
    rows = (await s.execute(select(SettingsKV))).scalars().all()
    return {r.key: r.value for r in rows}


@settings.post("")
async def save_settings(body: dict, s=Depends(get_session)):
    from thbuzzer.models.all import SettingsKV
    for k, v in body.items():
        row = await s.get(SettingsKV, k)
        val = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        if row:
            row.value = val
        else:
            s.add(SettingsKV(key=k, value=val))
    await s.commit()
    return {"ok": True}
