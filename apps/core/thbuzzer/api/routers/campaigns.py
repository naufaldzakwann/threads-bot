"""Campaigns §11: 1-klik buzzer, pre-flight, distribusi drip + target pacing, stance."""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from thbuzzer.api.deps import get_session
from thbuzzer.models.all import Account, Campaign, CampaignParticipant
from thbuzzer.services.logic import DEFAULT_STANCE
from thbuzzer.tasks.queue import enqueue
from thbuzzer.utils.distribution import drip_schedule, pace_target
from thbuzzer.utils.validators import Invalid, fail, int_list, pos_int, threads_url

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignIn(BaseModel):
    name: str
    targets: list[str] = Field(min_length=1, max_length=20)
    actions: list = []
    account_ids: list[int] = []
    spread_minutes: int = Field(default=180, ge=1, le=43200)
    max_target_actions_per_minute: int = Field(default=4, ge=1, le=6)
    stance_distribution: dict = {}

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("nama tidak valid: wajib diisi")
        return v[:200]

    @field_validator("targets")
    @classmethod
    def _targets(cls, v: list) -> list[str]:
        try:
            return [threads_url(t, "target") for t in v]
        except Invalid as e:
            raise ValueError(str(e)) from e

    @field_validator("account_ids")
    @classmethod
    def _accs(cls, v: list) -> list[int]:
        try:
            return int_list(v, "account_ids", allow_empty=True)
        except Invalid as e:
            raise ValueError(str(e)) from e


@router.get("")
async def list_all(s=Depends(get_session)):
    rows = (await s.execute(select(Campaign))).scalars().all()
    return {"items": [{"id": c.id, "name": c.name, "status": c.status} for c in rows]}


@router.post("", status_code=201)
async def create(b: CampaignIn, s=Depends(get_session)):
    stance = b.stance_distribution or DEFAULT_STANCE
    c = Campaign(name=b.name, targets_json=json.dumps(b.targets, ensure_ascii=False),
                 actions_json=json.dumps(b.actions, ensure_ascii=False),
                 participants_json=json.dumps({"account_ids": b.account_ids}, ensure_ascii=False),
                 max_target_actions_per_minute=b.max_target_actions_per_minute,
                 stance_distribution_json=json.dumps(stance, ensure_ascii=False),
                 schedule_json=json.dumps({"spread_minutes": b.spread_minutes}, ensure_ascii=False),
                 status="draft")
    s.add(c)
    await s.commit()
    return {"id": c.id}


@router.post("/{cid}/start")
async def start(cid: int, s=Depends(get_session)):
    c = await s.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "kampanye tidak ada")
    targets = json.loads(c.targets_json)
    sched = json.loads(c.schedule_json)
    parts = json.loads(c.participants_json).get("account_ids", [])
    # Pre-flight WAJIB: 1 job burner cek target publik/reply_control/deleted (§11)
    for t in targets:
        try:
            threads_url(t, "target")
        except Invalid as e:
            c.status = "aborted_target_invalid"
            await s.commit()
            return {"ok": False, "status": c.status, "reason": str(e)}
    # Guard peserta: active + health>=30 (kuota dicek worker)
    valid = []
    for aid in parts:
        a = await s.get(Account, aid)
        if a and a.status == "active" and a.health_score >= 30 and not a.deleted:
            valid.append(aid)
    if not valid:
        await s.commit()
        return {"ok": False, "status": "draft",
                "reason": "tidak ada peserta valid (butuh status active + health ≥ 30)"}
    # Distribusi drip deterministik + target pacing guard
    offsets = drip_schedule(max(len(valid), 1), sched.get("spread_minutes", 180), seed=cid)
    offsets = pace_target(offsets, c.max_target_actions_per_minute)
    base = int(time.time())
    for aid, off in zip(valid, offsets):
        s.add(CampaignParticipant(campaign_id=c.id, account_id=aid, status="pending"))
        await enqueue(s, "campaign_reply", account_id=aid, priority="normal",
                      payload={"campaign_id": c.id, "targets": targets},
                      scheduled_at=base + int(off * 60), dedup_key=f"camp{c.id}:acct{aid}")
    c.status = "running"
    await s.commit()
    return {"ok": True, "participants": len(valid), "spread_minutes": sched.get("spread_minutes", 180)}


@router.post("/{cid}/pause")
async def pause(cid: int, s=Depends(get_session)):
    c = await s.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "kampanye tidak ada")
    c.status = "paused"
    await s.commit()
    return {"ok": True}


@router.post("/{cid}/stop")
async def stop(cid: int, s=Depends(get_session)):
    c = await s.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "kampanye tidak ada")
    c.status = "stopped"
    await s.commit()
    return {"ok": True}


@router.get("/{cid}/participants")
async def participants(cid: int, s=Depends(get_session)):
    rows = (await s.execute(select(CampaignParticipant).where(
        CampaignParticipant.campaign_id == cid))).scalars().all()
    return {"items": [{"id": p.id, "account_id": p.account_id, "status": p.status} for p in rows]}


@router.get("/{cid}/progress")
async def progress(cid: int, s=Depends(get_session)):
    from sqlalchemy import func
    rows = dict((await s.execute(select(CampaignParticipant.status, func.count()).where(
        CampaignParticipant.campaign_id == cid).group_by(CampaignParticipant.status))).all())
    total = sum(rows.values())
    done = rows.get("done", 0)
    return {"by_status": rows, "total": total, "done": done,
            "rate": round(done / total, 3) if total else 0}


@router.post("/{cid}/retry-failed")
async def retry_failed(cid: int, s=Depends(get_session)):
    from thbuzzer.models.all import Job
    c = await s.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "kampanye tidak ada")
    q = await s.execute(select(Job).where(Job.dedup_key.like(f"camp{cid}:%"),
                                          Job.status.in_(["failed", "dead_letter"])))
    n = 0
    for j in q.scalars().all():
        j.status = "pending"
        j.attempt = 0
        n += 1
    q2 = await s.execute(select(CampaignParticipant).where(
        CampaignParticipant.campaign_id == cid, CampaignParticipant.status == "failed"))
    for p in q2.scalars().all():
        p.status = "pending"
    await s.commit()
    return {"ok": True, "requeued": n}


@router.post("/{cid}/add-participants")
async def add_participants(cid: int, body: dict, s=Depends(get_session)):
    import time as _t
    from thbuzzer.tasks.queue import enqueue
    c = await s.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "kampanye tidak ada")
    targets = json.loads(c.targets_json or "[]")
    try:
        aids = int_list(body.get("account_ids", []), "account_ids")
    except Invalid as e:
        raise fail(str(e))
    n = 0
    for aid in aids:
        a = await s.get(Account, aid)
        if not a or a.status != "active":
            continue
        s.add(CampaignParticipant(campaign_id=c.id, account_id=aid, status="pending"))
        await enqueue(s, "campaign_reply", account_id=aid, priority="normal",
                      payload={"campaign_id": c.id, "targets": targets},
                      scheduled_at=int(_t.time()) + n * 60, dedup_key=f"camp{c.id}:acct{aid}")
        n += 1
    await s.commit()
    return {"ok": True, "added": n}
