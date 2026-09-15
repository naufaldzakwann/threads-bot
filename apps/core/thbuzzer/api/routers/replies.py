"""Replies §10: unified inbox 3-panel + rules + mass-reply + visibility audit (Hidden Replies)."""
from __future__ import annotations

import re
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from thbuzzer.api.deps import get_session
from thbuzzer.models.all import ReplyCampaign, ReplyRule, ThreadConversation, ThreadMessage
from thbuzzer.utils.validators import Invalid, fail, pos_int, thread_target, threads_url

router = APIRouter(prefix="/replies", tags=["replies"])


class RuleIn(BaseModel):
    name: str
    trigger: str = "keyword"  # keyword/regex/any/first_reply/mention/quote/new_follower
    pattern: str = ""
    response_template: str = ""
    enabled: int = 1


@router.get("/conversations")
async def conversations(account_id: int = 0, s=Depends(get_session)):
    q = select(ThreadConversation)
    if account_id:
        q = q.where(ThreadConversation.account_id == account_id)
    rows = (await s.execute(q.limit(200))).scalars().all()
    return {"items": [{"id": c.id, "account_id": c.account_id, "thread_id": c.thread_id, "unread": c.unread} for c in rows]}


@router.get("/conversations/{cid}/messages")
async def messages(cid: int, s=Depends(get_session)):
    rows = (await s.execute(select(ThreadMessage).where(ThreadMessage.conversation_id == cid))).scalars().all()
    return {"items": [{"id": m.id, "author": m.author, "text": m.text,
                       "is_hidden_by_platform": m.is_hidden_by_platform} for m in rows]}


@router.post("/rules", status_code=201)
async def create_rule(b: RuleIn, s=Depends(get_session)):
    import json
    r = ReplyRule(name=b.name, trigger=b.trigger, pattern=b.pattern,
                  response_json=json.dumps({"template": b.response_template}, ensure_ascii=False),
                  enabled=b.enabled)
    s.add(r)
    await s.commit()
    return {"id": r.id}


@router.post("/rules/test")
async def test_rule(body: dict):
    """Regex tester + anti-loop note (3 balasan bot/utas/24 jam §10)."""
    pattern, text = body.get("pattern", ""), body.get("text", "")
    try:
        matched = bool(re.search(pattern, text)) if pattern else True
    except re.error as e:
        return {"matched": False, "error": str(e)}
    return {"matched": matched, "anti_loop": "maks 3 balasan bot/utas/24 jam, skip sesama kelolaan"}


@router.get("/rules")
async def list_rules(s=Depends(get_session)):
    rows = (await s.execute(select(ReplyRule))).scalars().all()
    return {"items": [{"id": r.id, "name": r.name, "trigger": r.trigger,
                       "pattern": r.pattern, "enabled": r.enabled} for r in rows]}


@router.delete("/rules/{rid}")
async def delete_rule(rid: int, s=Depends(get_session)):
    from fastapi import HTTPException
    r = await s.get(ReplyRule, rid)
    if not r:
        raise HTTPException(404, "rule tidak ada")
    await s.delete(r)
    await s.commit()
    return {"ok": True}


@router.post("/send")
async def send_reply(body: dict, s=Depends(get_session)):
    """Balas manual sebagai reply <=30 dtk, prioritas high (§10)."""
    import time as _t
    from fastapi import HTTPException
    from thbuzzer.tasks.queue import enqueue
    from thbuzzer.utils.threads_text import validate_thread
    text = body.get("text", "")
    errs = validate_thread(text)
    if errs:
        raise HTTPException(422, "; ".join(errs))
    try:
        account_id = pos_int(body.get("account_id"), "account_id")
        target = thread_target(body.get("thread_id"), "thread_id")
    except Invalid as e:
        raise fail(str(e))
    job = await enqueue(s, "reply", account_id=account_id, priority="high",
                        payload={"target": target, "text": text},
                        scheduled_at=int(_t.time()),
                        dedup_key=f"manual:{account_id}:{target}:{_t.time_ns()}")
    await s.commit()
    return {"job_id": job.id}


@router.post("/poll-now")
async def poll_now(body: dict, s=Depends(get_session)):
    import time as _t
    from thbuzzer.tasks.queue import enqueue
    try:
        account_id = pos_int(body.get("account_id"), "account_id")
    except Invalid as e:
        from fastapi import HTTPException
        raise fail(str(e))
    job = await enqueue(s, "poll_replies", account_id=account_id, priority="high",
                        payload={}, scheduled_at=int(_t.time()),
                        dedup_key=f"pollnow:{account_id}:{_t.time_ns()}")
    await s.commit()
    return {"job_id": job.id}


@router.post("/campaigns/{cid}/start")
async def start_mass_reply(cid: int, s=Depends(get_session)):
    """Mass-reply: 1 reply/penerima/kampanye, cooldown 14 hari, throttling linear-acak (§10)."""
    import time as _t
    from thbuzzer.tasks.queue import enqueue
    from fastapi import HTTPException
    c = await s.get(ReplyCampaign, cid)
    if not c:
        raise HTTPException(404, "kampanye tidak ada")
    import json as _j
    src = _j.loads(c.source_json or "{}")
    try:
        account_ids = [pos_int(x, "source.account_ids[]") for x in src.get("account_ids", [])]
        targets = [threads_url(t, "source.targets[]") for t in src.get("targets", [])]
    except Invalid as e:
        raise fail(str(e))
    if not account_ids or not targets:
        raise HTTPException(422, "source tidak valid: butuh account_ids + targets (link Threads)")
    c.status = "running"
    n = 0
    for i, aid in enumerate(account_ids):
        await enqueue(s, "reply", account_id=aid, priority="normal",
                      payload={"target": targets[i % len(targets)], "text": c.template,
                               "mass_campaign_id": cid},
                      scheduled_at=int(_t.time()) + i * 120,
                      dedup_key=f"mass{cid}:a{aid}")
        n += 1
    await s.commit()
    return {"ok": True, "queued": n}


@router.post("/campaigns", status_code=201)
async def create_mass_reply(body: dict, s=Depends(get_session)):
    import json
    c = ReplyCampaign(name=body.get("name", ""), source_json=json.dumps(body.get("source", {})),
                      template=body.get("template", ""), status="draft")
    s.add(c)
    await s.commit()
    return {"id": c.id, "note": "1 reply/penerima/kampanye, cooldown 14 hari, throttling linear-acak"}


@router.post("/visibility-check")
async def visibility_check(body: dict, s=Depends(get_session)):
    """Visibility Auditor §10: cek 10-15 mnt setelah publish via scout/unauthenticated.

    Body: {message_id, visible: bool}. visible=False -> hidden_by_platform + soft-warning.
    """
    try:
        mid = pos_int(body.get("message_id"), "message_id")
    except Invalid as e:
        from fastapi import HTTPException
        raise fail(str(e))
    m = await s.get(ThreadMessage, mid)
    if not m:
        return {"ok": False}
    visible = bool(body.get("visible", True))
    m.last_visibility_checked_at = int(time.time())
    if not visible:
        m.is_hidden_by_platform = 1
        await s.commit()
        return {"ok": True, "status": "hidden_by_platform",
                "action": "soft-warning + kurangi frekuensi balasan akun 24 jam"}
    await s.commit()
    return {"ok": True, "status": "visible"}
