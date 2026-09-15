"""Activities growth CRUD + preview (§08). Aksi like/follow/unfollow/reply/repost/quote."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from thbuzzer.api.deps import get_session
from thbuzzer.models.all import Activity
from thbuzzer.utils.validators import Invalid, fail, one_of, pos_int, threads_url

router = APIRouter(prefix="/activities", tags=["activities"])
ACTIONS = {"like", "follow", "unfollow", "reply", "repost", "quote"}


class ActivityIn(BaseModel):
    kind: str = "growth"
    account_filter: dict = {}
    actions: list = []


@router.get("")
async def list_all(s=Depends(get_session)):
    rows = (await s.execute(select(Activity))).scalars().all()
    return {"items": [{"id": a.id, "kind": a.kind, "status": a.status} for a in rows]}


@router.post("", status_code=201)
async def create(b: ActivityIn, s=Depends(get_session)):
    for ac in b.actions:
        if ac.get("type") not in ACTIONS:
            return {"error": f"aksi {ac.get('type')} tidak dikenal"}
    a = Activity(kind=b.kind, account_filter_json=json.dumps(b.account_filter, ensure_ascii=False),
                 actions_json=json.dumps(b.actions, ensure_ascii=False), status="draft")
    s.add(a)
    await s.commit()
    return {"id": a.id}


@router.post("/{aid}/preview-targets")
async def preview(aid: int, body: dict, s=Depends(get_session)):
    """Preview WAJIB tampilkan estimasi jatah search mingguan bila pakai official search (§08)."""
    from thbuzzer.utils.validators import Invalid as _InvPv, fail as _failPv, pos_int as _piPv
    try:
        count = _piPv(body.get("count", 100), "count", max=100000)
    except _InvPv as e:
        raise _failPv(str(e))
    search_official = bool(body.get("use_official_search"))
    est = {"targets": count, "official_search_used": 1 if search_official else 0,
           "weekly_search_quota": 500, "weekly_search_remaining_est": 500 - (1 if search_official else 0)}
    return est


@router.post("/{aid}/start")
async def start(aid: int, body: dict, s=Depends(get_session)):
    """Jalankan growth: filter armada (grup/tag/health/locale) -> job per akun per aksi, delay 60-240 dtk."""
    import random
    import time
    from sqlalchemy import or_
    from thbuzzer.models.all import Account
    from thbuzzer.tasks.queue import enqueue
    from thbuzzer.utils.threads_text import render_spintax
    a = await s.get(Activity, aid)
    if not a:
        from fastapi import HTTPException
        raise HTTPException(404, "activity tidak ada")
    f = {**json.loads(a.account_filter_json or "{}"), **(body.get("filter") or {})}
    q = select(Account).where(Account.status == "active", Account.deleted == 0)
    try:
        if f.get("group_id") is not None:
            q = q.where(Account.group_id == pos_int(f.get("group_id"), "filter.group_id"))
        if f.get("tier"):
            q = q.where(Account.account_tier == one_of(f.get("tier"), "filter.tier",
                                                       {"brand_official", "buzzer_satellite"}))
        if f.get("health_min") is not None:
            q = q.where(Account.health_score >= pos_int(f.get("health_min"), "filter.health_min", min=0, max=100))
    except Invalid as e:
        from fastapi import HTTPException
        raise fail(str(e))
    accs = (await s.execute(q.limit(2000))).scalars().all()
    if f.get("count") is not None:
        try:
            cnt = pos_int(f.get("count"), "filter.count", max=2000)
        except Invalid as e:
            from fastapi import HTTPException
            raise fail(str(e))
        accs = random.Random(aid).sample(accs, min(cnt, len(accs)))
    actions = body.get("actions") or json.loads(a.actions_json or "[]")
    for ac in actions:
        try:
            one_of(ac.get("type"), "actions[].type", ACTIONS)
        except Invalid as e:
            from fastapi import HTTPException
            raise fail(str(e))
    try:
        targets = [threads_url(t, "targets[]") for t in body.get("targets", [])]
    except Invalid as e:
        from fastapi import HTTPException
        raise fail(str(e))
    rng = random.Random(aid)
    base = int(time.time())
    n = 0
    for i, acc in enumerate(accs):
        for k, ac in enumerate(actions):
            text = render_spintax(ac.get("template", ""), rng)[:500] if ac.get("template") else ""
            await enqueue(s, ac.get("type", "like"), account_id=acc.id, priority="normal",
                          payload={"activity_id": aid, "target": targets[(i + k) % len(targets)] if targets else "",
                                   "text": text},
                          scheduled_at=base + i * rng.randint(60, 240) + k * 60,
                          dedup_key=f"act{aid}:a{acc.id}:{ac.get('type')}:{k}")
            n += 1
    a.status = "running"
    await s.commit()
    return {"ok": True, "accounts": len(accs), "jobs": n}


@router.post("/{aid}/pause")
async def pause(aid: int, s=Depends(get_session)):
    from thbuzzer.models.all import Job
    a = await s.get(Activity, aid)
    if not a:
        from fastapi import HTTPException
        raise HTTPException(404, "activity tidak ada")
    a.status = "paused"
    q = await s.execute(select(Job).where(Job.dedup_key.like(f"act{aid}:%"),
                                          Job.status.in_(["scheduled", "pending"])))
    n = 0
    for j in q.scalars().all():
        j.status = "held"
        n += 1
    await s.commit()
    return {"ok": True, "held": n}


@router.post("/{aid}/resume")
async def resume(aid: int, s=Depends(get_session)):
    from thbuzzer.models.all import Job
    a = await s.get(Activity, aid)
    if not a:
        from fastapi import HTTPException
        raise HTTPException(404, "activity tidak ada")
    a.status = "running"
    q = await s.execute(select(Job).where(Job.dedup_key.like(f"act{aid}:%"), Job.status == "held"))
    n = 0
    for j in q.scalars().all():
        j.status = "pending"
        n += 1
    await s.commit()
    return {"ok": True, "resumed": n}


@router.get("/{aid}/stats")
async def stats(aid: int, s=Depends(get_session)):
    from sqlalchemy import func
    from thbuzzer.models.all import Job, JobRun
    ids = [r[0] for r in (await s.execute(select(Job.id).where(Job.dedup_key.like(f"act{aid}:%")))).all()]
    ok = total = 0
    if ids:
        total = len(ids)
        ok = (await s.execute(select(func.count()).select_from(JobRun).where(
            JobRun.job_id.in_(ids), JobRun.success == 1))).scalar() or 0
    return {"jobs": total, "success": ok, "rate": round(ok / total, 3) if total else 0}
