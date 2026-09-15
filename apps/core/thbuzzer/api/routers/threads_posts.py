"""Threads-posts §09+§16: CRUD + quick-thread + publishing-limit + topic-sets + validators."""
from __future__ import annotations

import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from thbuzzer import GRAPH_BASE
from thbuzzer.api.deps import get_session
from thbuzzer.models.all import Account, ScheduledThread, ThreadsToken, TopicSet
from thbuzzer.security.crypto import decrypt
from thbuzzer.utils.threads_text import (sanitize_topic_tag, split_threadstorm,
                                         strip_extra_hashes, validate_thread)
from thbuzzer.utils.validators import Invalid, http_url, pos_int

router = APIRouter(prefix="/threads-posts", tags=["threads"])


class ThreadIn(BaseModel):
    account_id: int
    text: str
    topic_tag: str = ""
    reply_control: str = "everyone"
    link_urls: list[str] = []
    media: list = []
    scheduled_at: int = 0
    first_reply: str = ""

    @field_validator("account_id")
    @classmethod
    def _acc(cls, v: object) -> int:
        try:
            return pos_int(v, "account_id")
        except Invalid as e:
            raise ValueError(str(e)) from e

    @field_validator("link_urls")
    @classmethod
    def _links(cls, v: list) -> list[str]:
        try:
            return [http_url(u, "link_urls[]") for u in (v or [])]
        except Invalid as e:
            raise ValueError(str(e)) from e

    @field_validator("scheduled_at")
    @classmethod
    def _sched(cls, v: object) -> int:
        try:
            return pos_int(v, "scheduled_at", min=0, max=4102444800)
        except Invalid as e:
            raise ValueError(str(e)) from e


@router.get("")
async def list_threads(account_id: int = 0, s=Depends(get_session)):
    q = select(ScheduledThread)
    if account_id:
        q = q.where(ScheduledThread.account_id == account_id)
    rows = (await s.execute(q.limit(200))).scalars().all()
    return {"items": [{"id": t.id, "account_id": t.account_id, "status": t.status,
                       "topic_tag": t.topic_tag, "scheduled_at": t.scheduled_at} for t in rows]}


@router.post("", status_code=201)
async def create_thread(b: ThreadIn, s=Depends(get_session)):
    # Auto-sanitizer: #a #b #c -> tag=a, teks bersih (§9.1)
    tag = b.topic_tag or sanitize_topic_tag(b.text)
    text = strip_extra_hashes(b.text) if "#" in b.text and not b.topic_tag else b.text
    errs = validate_thread(text, tag, b.reply_control, len(b.link_urls))
    if errs:
        raise HTTPException(422, "; ".join(errs))
    # Text attachment 10k char: v1 TIDAK didukung API -> tolak jelas (§9.1)
    if len(text) > 500:
        raise HTTPException(422, "E-VALID-TEXT-LIMIT")
    t = ScheduledThread(account_id=b.account_id, text_rendered=text, topic_tag=tag,
                        reply_control=b.reply_control,
                        link_urls_json=json.dumps(b.link_urls[:5], ensure_ascii=False),
                        media_json=json.dumps(b.media, ensure_ascii=False),
                        status="scheduled", scheduled_at=b.scheduled_at or int(time.time()))
    s.add(t)
    await s.flush()
    # Antre eksekusi scheduled_at ±jitter 0-15 mnt (§9.2)
    import random
    from thbuzzer.tasks.queue import enqueue
    job = await enqueue(s, "publish_thread", account_id=b.account_id, priority="normal",
                        payload={"scheduled_thread_id": t.id, "first_reply": b.first_reply,
                                 "media_local": [m for m in b.media if isinstance(m, str) and not m.startswith("http")]},
                        scheduled_at=max(int(time.time()), t.scheduled_at) + random.Random(t.id).randint(0, 900),
                        dedup_key=f"pub:thread:{t.id}")
    await s.commit()
    # threadstorm preview bila >500 char input mentah (dipecah otomatis)
    parts = split_threadstorm(b.text) if len(b.text) > 500 else [text]
    return {"id": t.id, "job_id": job.id, "topic_tag": tag, "parts": len(parts)}


@router.post("/quick-thread")
async def quick_thread(body: dict, s=Depends(get_session)):
    """Stagger 1-8 mnt/akun (§9.2)."""
    from thbuzzer.utils.validators import Invalid as _Inv, fail as _fail, int_list as _il
    try:
        account_ids = _il(body.get("account_ids", []), "account_ids")
    except _Inv as e:
        raise _fail(str(e))
    text: str = body.get("text", "")
    tag = sanitize_topic_tag(text)
    errs = validate_thread(strip_extra_hashes(text), tag)
    if errs:
        raise HTTPException(422, "; ".join(errs))
    ids = []
    base = int(time.time())
    import random
    from thbuzzer.tasks.queue import enqueue
    rng = random.Random(42)
    for i, aid in enumerate(account_ids):
        t = ScheduledThread(account_id=aid, text_rendered=strip_extra_hashes(text), topic_tag=tag,
                            status="scheduled", scheduled_at=base + rng.randint(60, 480) + i * 60)
        s.add(t)
        await s.flush()
        await enqueue(s, "publish_thread", account_id=aid, priority="normal",
                      payload={"scheduled_thread_id": t.id},
                      scheduled_at=t.scheduled_at, dedup_key=f"pub:thread:{t.id}")
        ids.append(t.id)
    await s.commit()
    return {"scheduled": ids}


@router.post("/threadstorm", status_code=201)
async def create_threadstorm(body: dict, s=Depends(get_session)):
    """Pecah teks panjang per 500 char -> rantai linear reply_to (§9.2 + failure recovery)."""
    from thbuzzer.tasks.queue import enqueue
    from thbuzzer.utils.validators import Invalid as _Inv2, fail as _fail2, pos_int as _pi
    try:
        account_id = _pi(body.get("account_id"), "account_id")
    except _Inv2 as e:
        raise _fail2(str(e))
    parts = split_threadstorm(body.get("text", ""))
    if len(parts) < 2:
        raise HTTPException(422, "teks <=500 char; pakai POST /threads-posts biasa")
    tag = body.get("topic_tag", "") or sanitize_topic_tag(parts[0])
    ids: list[int] = []
    prev_id = 0
    base = int(time.time())
    for i, p in enumerate(parts):
        errs = validate_thread(p, tag if i == 0 else "")
        if errs:
            raise HTTPException(422, "; ".join(errs))
        t = ScheduledThread(account_id=account_id, text_rendered=p, topic_tag=tag if i == 0 else "",
                            reply_control=body.get("reply_control", "everyone"),
                            status="scheduled", scheduled_at=base + i * 300)
        s.add(t)
        await s.flush()
        await enqueue(s, "publish_thread", account_id=account_id, priority="normal",
                      payload={"scheduled_thread_id": t.id,
                               **({"prev_scheduled_id": prev_id} if prev_id else {})},
                      scheduled_at=t.scheduled_at, dedup_key=f"pub:thread:{t.id}")
        ids.append(t.id)
        prev_id = t.id
    await s.commit()
    return {"thread_ids": ids, "parts": len(parts)}


@router.post("/media/validate")
async def validate_media(body: dict):
    """Validasi §9.1: gambar JPG/PNG <=8MB 320-1440px aspek<=10:1; video <=1GB <=300dtk."""
    from thbuzzer.utils.validators import Invalid as _Inv3, fail as _fail3, pos_int as _pi3
    kind = body.get("kind", "image")
    if kind not in ("image", "video"):
        raise _fail3("kind tidak valid: 'image' — pilihan: image, video")
    try:
        size = _pi3(body.get("size_bytes", 0), "size_bytes", min=0, max=2 * 1024 ** 3)
        w = _pi3(body.get("width", 0), "width", min=0, max=8192)
        h = _pi3(body.get("height", 0), "height", min=0, max=8192)
        dur = _pi3(body.get("duration_sec", 0), "duration_sec", min=0, max=36000)
    except _Inv3 as e:
        raise _fail3(str(e))
    errs = []
    if kind == "image":
        if size > 8 * 1024 * 1024:
            errs.append("E-VALID-MEDIA-SIZE: gambar <=8 MB")
        if not (320 <= w <= 1440):
            errs.append("E-VALID-MEDIA-WIDTH: lebar 320-1440 px")
        if h and max(w, h) / max(min(w, h), 1) > 10:
            errs.append("E-VALID-MEDIA-ASPECT: aspek <=10:1")
    else:  # video
        if size > 1024 ** 3:
            errs.append("E-VALID-MEDIA-SIZE: video <=1 GB")
        if dur > 300:
            errs.append("E-VALID-MEDIA-DURATION: video <=300 dtk")
    if errs:
        raise HTTPException(422, "; ".join(errs))
    # Tanpa R2/S3 -> fallback browser DOM upload (§7.1)
    from thbuzzer.config import get_settings
    cloud = bool(get_settings().storage_public_base_url)
    return {"ok": True, "via": "official_api(R2/S3)" if cloud else "browser(DOM upload)"}


@router.post("/import-manifest")
async def import_manifest(body: dict, s=Depends(get_session)):
    """CSV manifest: media_path,account_filter_group,text_template,topic_tag,reply_control,first_reply,scheduled_at,timezone."""
    import csv
    import io
    from thbuzzer.utils.validators import Invalid as _Inv4, pos_int as _pi4
    reader = csv.DictReader(io.StringIO(body.get("csv", "")))
    ok, bad = 0, []
    for i, row in enumerate(reader, 1):
        try:
            try:
                aid = _pi4(row.get("account_id"), "account_id")
                sched = _pi4(row.get("scheduled_at") or 0, "scheduled_at", min=0, max=4102444800)
            except _Inv4 as e:
                raise ValueError(str(e)) from e
            text = (row.get("text_template") or "")[:2000]
            tag = row.get("topic_tag") or sanitize_topic_tag(text)
            errs = validate_thread(strip_extra_hashes(text), tag,
                                   row.get("reply_control") or "everyone")
            if errs:
                raise ValueError("; ".join(errs))
            s.add(ScheduledThread(account_id=aid,
                                  text_rendered=strip_extra_hashes(text), topic_tag=tag,
                                  reply_control=row.get("reply_control") or "everyone",
                                  status="scheduled", scheduled_at=sched or int(time.time())))
            ok += 1
        except Exception as e:  # noqa: BLE001
            bad.append({"row": i, "error": str(e)[:200]})
    await s.commit()
    return {"imported": ok, "invalid": bad}


@router.post("/{tid}/cancel")
async def cancel_thread(tid: int, s=Depends(get_session)):
    from thbuzzer.models.all import Job
    t = await s.get(ScheduledThread, tid)
    if not t:
        raise HTTPException(404, "thread tidak ada")
    t.status = "cancelled"
    q = await s.execute(select(Job).where(Job.status.in_(["scheduled", "pending"])))
    n = 0
    for j in q.scalars().all():
        try:
            import json as _j
            if _j.loads(j.payload_json or "{}").get("scheduled_thread_id") == tid:
                j.status = "cancelled"
                n += 1
        except Exception:
            pass
    await s.commit()
    return {"ok": True, "jobs_cancelled": n}


@router.get("/queue-24h")
async def queue_24h(s=Depends(get_session)):
    from thbuzzer.models.all import Job
    now = int(time.time())
    q = await s.execute(select(Job).where(Job.type.like("publish_%"),
                                          Job.scheduled_at <= now + 86400,
                                          Job.status.in_(["scheduled", "pending", "running"]))
                        .order_by(Job.scheduled_at).limit(500))
    return {"items": [{"id": j.id, "type": j.type, "account_id": j.account_id,
                       "status": j.status, "scheduled_at": j.scheduled_at} for j in q.scalars().all()]}


@router.get("/publishing-limit")
async def publishing_limit(account_id: int = Query(ge=1), s=Depends(get_session)):
    a = await s.get(Account, account_id)
    if not a or not a.oauth_token_id:
        raise HTTPException(404, "akun/token tidak ada")
    t = await s.get(ThreadsToken, a.oauth_token_id)
    token = decrypt(t.access_token_enc, "threads_tokens.access_token_enc", str(t.id))  # type: ignore
    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as c:
        r = await c.get(f"/{a.threads_user_id or 'me'}/threads_publishing_limit", params={"access_token": token})
        r.raise_for_status()
        j = r.json()
    # Throttle guidance §2.4: >75% throttle 2x, >90% pause 10 mnt
    usage = j.get("quota_usage", 0)
    config = j.get("config", {}) or {}
    pct = (usage / config) if isinstance(config, (int, float)) and config else 0
    advice = "ok" if pct <= 0.75 else ("throttle-2x" if pct <= 0.9 else "pause-10m")
    return {"quota": j, "advice": advice}


@router.get("/topic-sets")
async def topic_sets(s=Depends(get_session)):
    rows = (await s.execute(select(TopicSet))).scalars().all()
    return {"items": [{"id": t.id, "name": t.name} for t in rows]}


@router.post("/topic-sets", status_code=201)
async def create_topic_set(body: dict, s=Depends(get_session)):
    t = TopicSet(name=body.get("name", ""), items_json=json.dumps(body.get("items", []), ensure_ascii=False))
    s.add(t)
    await s.commit()
    return {"id": t.id}
