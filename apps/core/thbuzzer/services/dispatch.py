"""Dispatch: eksekusi 1 job via Engine Router + efek samping (§3.5, §5.9, §14).

Alur: guard kuota lokal -> route tier/role -> rakit payload engine
(token OAuth dekrip / storageState dekrip / proxy) -> perform -> catat
(kuota, interactions, health, status_history, logs, alerts, WS) -> follow-up
(first_reply, visibility_audit). Tanpa retry buta; retry diatur tasks/queue.
"""
from __future__ import annotations

import datetime
import json
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thbuzzer import GRAPH_BASE
from thbuzzer.api.hub import broadcast
from thbuzzer.engines.base import ActionResult, EngineCtx
from thbuzzer.engines.browser.engine import BrowserEngine
from thbuzzer.engines.official.client import OfficialEngine
from thbuzzer.engines.private_unofficial.adapter import PrivateUnofficialEngine
from thbuzzer.engines.router import route
from thbuzzer.models.all import (Account, AccountStatusHistory, ActivityLog, AlertHistory,
                                 Campaign, CampaignParticipant, CheckpointEvent, Interaction, Job, QuotaUsage,
                                 ScheduledThread, ThreadConversation, ThreadMessage,
                                 AccountStatsSnapshot, ThreadsToken)
from thbuzzer.security.crypto import decrypt, encrypt
from thbuzzer.tasks.queue import enqueue

REGISTRY = {
    "official_api": OfficialEngine(),
    "private_unofficial": PrivateUnofficialEngine(),
    "browser": BrowserEngine(),
}

PUBLISH_TYPES = {"publish_thread", "publish_carousel", "publish_video"}
REPLY_TYPES = {"reply", "first_reply", "campaign_reply"}
GROWTH_TYPES = {"like", "follow", "unfollow", "repost", "quote"} | REPLY_TYPES


def _today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


async def _quota_row(s: AsyncSession, account_id: int) -> QuotaUsage:
    q = await s.execute(select(QuotaUsage).where(
        QuotaUsage.account_id == account_id, QuotaUsage.day == _today()))
    row = q.scalars().first()
    if not row:
        row = QuotaUsage(account_id=account_id, day=_today())
        s.add(row)
        await s.flush()
    return row


async def _set_status(s: AsyncSession, a: Account, to: str, reason: str = "") -> None:
    if a.status == to:
        return
    old = a.status
    a.status = to
    a.updated_at = int(time.time())
    s.add(AccountStatusHistory(account_id=a.id, old_status=old, new_status=to, reason=reason))
    await broadcast("account.status_changed", {"account_id": a.id, "status": to})


async def _alert(s: AsyncSession, kind: str, message: str, account_id: int | None = None) -> None:
    s.add(AlertHistory(kind=kind, message=message))
    await broadcast("alert.raised", {"kind": kind, "message": message, "account_id": account_id})
    from thbuzzer.models.all import SettingsKV
    row = await s.get(SettingsKV, "alerts.webhook_url")
    if row and row.value:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(row.value, json={"kind": kind, "message": message})
        except Exception:
            pass
    tg_token = await s.get(SettingsKV, "alerts.telegram_bot_token")
    tg_chat = await s.get(SettingsKV, "alerts.telegram_chat_id")
    if tg_token and tg_token.value and tg_chat and tg_chat.value:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(f"https://api.telegram.org/bot{tg_token.value}/sendMessage",
                             json={"chat_id": tg_chat.value, "text": f"[THBuzzer:{kind}] {message}"[:4000]})
        except Exception:
            pass


async def _apply_reply_rules(s: AsyncSession, a: Account, job: Job) -> None:
    """Auto-reply §10: keyword/regex/any + anti-loop 3/24 jam + skip sesama kelolaan."""
    import re
    from thbuzzer.models.all import ReplyRule
    from thbuzzer.utils.threads_text import render_spintax
    rules = (await s.execute(select(ReplyRule).where(ReplyRule.enabled == 1))).scalars().all()
    if not rules:
        return
    managed = {r[0].lower() for r in (await s.execute(select(Account.username))).all()}
    since = int(time.time()) - 86400
    for r in rules:
        try:
            spec = json.loads(r.response_json or "{}")
        except Exception:
            spec = {}
        convs = (await s.execute(select(ThreadConversation).where(
            ThreadConversation.account_id == a.id))).scalars().all()
        for conv in convs:
            msgs = (await s.execute(select(ThreadMessage).where(
                ThreadMessage.conversation_id == conv.id).order_by(ThreadMessage.id.desc()).limit(10)
            )).scalars().all()
            if not msgs:
                continue
            last = msgs[0]
            if last.author.lower() in managed or (a.username or "").lower() == last.author.lower():
                continue  # skip sesama kelolaan + diri sendiri
            bot_count = sum(1 for m in msgs if m.author == a.username and m.created_at >= since)
            if bot_count >= 3:
                continue  # anti-loop 3/24 jam
            hit = (r.trigger == "any" or
                   (r.trigger == "keyword" and r.pattern.lower() in (last.text or "").lower()) or
                   (r.trigger == "regex" and bool(re.search(r.pattern, last.text or ""))))
            if hit:
                text = render_spintax(spec.get("template", ""))[:500]
                if text:
                    await enqueue(s, "reply", account_id=a.id, priority="high",
                                  payload={"target": conv.thread_id, "text": text, "rule_id": r.id},
                                  dedup_key=f"rule{r.id}:c{conv.id}:m{last.id}")
        await s.flush()


def _engine_payload(a: Account, token: ThreadsToken | None, proxy_url: str) -> dict[str, Any]:
    p: dict[str, Any] = {"proxy": proxy_url, "threads_user_id": a.threads_user_id or ""}
    if token:
        try:
            p["access_token"] = decrypt(token.access_token_enc, "threads_tokens.access_token_enc", str(token.id))
        except Exception:
            p["access_token"] = ""
    if a.storage_state_enc:
        try:
            p["storage_state"] = json.loads(decrypt(a.storage_state_enc, "accounts.storage_state_enc", str(a.id)))
        except Exception:
            p["storage_state"] = None
    return p


async def execute_job(s: AsyncSession, job: Job, engines: dict | None = None) -> ActionResult:
    engines = engines or REGISTRY
    try:
        payload = json.loads(job.payload_json or "{}")
    except Exception:
        payload = {}
    a: Account | None = await s.get(Account, job.account_id) if job.account_id else None

    # 0. Job pemeliharaan tanpa engine
    if job.type == "refresh_oauth":
        tid = int(payload.get("token_id", (a.oauth_token_id if a and a.oauth_token_id else 0) or 0))
        r = await refresh_oauth_token(s, tid)
        return ActionResult(bool(r.get("ok")), data=r,
                            error_code="" if r.get("ok") else "E-AUTH-TOKEN-EXPIRED",
                            engine_used="official_api")
    if job.type in ("quota_reset", "warmup_tick", "health_check"):
        return ActionResult(True, data={"noop": job.type}, engine_used="")

    # 1. Guard kuota lokal (rolling-24h sederhana per hari UTC) — habis -> held besok (§14)
    bucket = None
    if job.type in PUBLISH_TYPES:
        bucket = "posts"
    elif job.type in REPLY_TYPES:
        bucket = "replies"
    elif job.type == "delete_thread":
        bucket = "deletes"
    if bucket and a:
        row = await _quota_row(s, a.id)
        limits = {"posts": 250, "replies": 1000, "deletes": 100}
        if getattr(row, bucket) >= limits[bucket]:
            await s.commit()
            return ActionResult(False, error_code="E-LIMIT-QUOTA", engine_used="",
                                raw_snapshot={"bucket": bucket})
        if getattr(row, bucket) + 1 >= int(limits[bucket] * 0.9):
            await _alert(s, "threads_quota_90", f"kuota {bucket} akun {a.username} >90%", a.id)

    # 2. Routing (dm_* ditolak, scout-only ditegakkan)
    tier = a.account_tier if a else "buzzer_satellite"
    role = a.account_role if a else "actor"
    engine_name, err = route(job.type, tier, role, job_hint=job.engine_hint,
                             account_engine=a.default_engine if a else "",
                             private_healthy=PrivateUnofficialEngine._consec_bug < 3,
                             media_local_no_cloud=bool(payload.get("media_local")))
    if err:
        return ActionResult(False, error_code=err.split(":")[0], engine_used="", raw_snapshot={"err": err})
    engine = engines.get(engine_name)
    if engine is None:
        return ActionResult(False, error_code="E-ENGINE-BUG", engine_used=engine_name,
                            raw_snapshot={"err": "engine missing"})

    # 3. Rakit parameter aksi
    base: dict[str, Any] = {}
    if a:
        tok = await s.get(ThreadsToken, a.oauth_token_id) if a.oauth_token_id else None
        base = _engine_payload(a, tok, payload.get("proxy", ""))
    params: dict[str, Any] = {**base, **payload}
    action = job.type
    if job.type in PUBLISH_TYPES and payload.get("scheduled_thread_id"):
        t = await s.get(ScheduledThread, payload["scheduled_thread_id"])
        if t:
            if t.published_threads_id:  # guard dobel-publish (§9.2)
                return ActionResult(True, data={"id": t.published_threads_id, "dedup": True}, engine_used=engine_name)
            # Threadstorm linear: segmen N butuh segmen N-1 terbit; gagal -> interrupted (§9.2)
            if payload.get("prev_scheduled_id"):
                prev = await s.get(ScheduledThread, payload["prev_scheduled_id"])
                if not prev or not prev.published_threads_id:
                    t.status = "threadstorm_interrupted"
                    await s.commit()
                    return ActionResult(False, error_code="E-VALID-THREADSTORM",
                                        engine_used=engine_name,
                                        raw_snapshot={"prev": payload.get("prev_scheduled_id")})
                params["reply_to_id"] = prev.published_threads_id
                params["container_params"]["reply_to_id"] = prev.published_threads_id
            links = json.loads(t.link_urls_json or "[]")
            media = json.loads(t.media_json or "[]")
            params.update({"text": t.text_rendered, "topic_tag": t.topic_tag,
                           "reply_control": t.reply_control, "link_urls": links,
                           "container_params": {"media_type": "TEXT" if not media else "IMAGE",
                                                "text": t.text_rendered}})
            if payload.get("media_urls"):
                params["media_urls"] = payload["media_urls"]
                params["container_params"] = {"media_type": "IMAGE", "text": t.text_rendered,
                                              "image_url": payload["media_urls"][0]}
            if payload.get("media_local") and not payload.get("media_urls"):
                params["media_local"] = payload["media_local"]

    t0 = time.monotonic()
    try:
        res = await engine.perform(EngineCtx(a.id if a else 0, action, params, job.engine_hint))
    except Exception as e:  # noqa: BLE001 isolasi total
        res = ActionResult(False, error_code="E-ENGINE-BUG", engine_used=engine_name,
                           raw_snapshot={"err": str(e)[:300]})
    res.latency_ms = res.latency_ms or int((time.monotonic() - t0) * 1000)

    # 4. Efek samping
    if job.type == "visibility_audit":
        m = await s.get(ThreadMessage, int(payload.get("message_id", 0)))
        if m:
            m.last_visibility_checked_at = int(time.time())
            vis = (res.data or {}).get("visible", True)
            if vis is False:
                m.is_hidden_by_platform = 1
                s.add(ActivityLog(account_id=a.id if a else None, action="visibility_audit",
                                  status="hidden_by_platform",
                                  message=f"reply {payload.get('reply_id')} masuk Hidden Replies"))
                await _alert(s, "reply.hidden", "balasan masuk Hidden Replies; frekuensi dikurangi 24 jam",
                             a.id if a else None)
            await s.commit()
        return ActionResult(True, data={"audited": True}, engine_used=res.engine_used)
    if a:
        s.add(ActivityLog(account_id=a.id, action=job.type,
                          status="ok" if res.success else res.error_code,
                          message=(res.data.get("id", "") if res.data else "")[:200]))
        if res.success:
            if bucket:
                row = await _quota_row(s, a.id)
                setattr(row, bucket, getattr(row, bucket) + 1)
            if job.type in GROWTH_TYPES:
                s.add(Interaction(account_id=a.id, action=job.type,
                                  target=str(payload.get("target", payload.get("thread_id", "")))[:300]))
            if payload.get("campaign_id"):
                q = await s.execute(select(CampaignParticipant).where(
                    CampaignParticipant.campaign_id == int(payload["campaign_id"]),
                    CampaignParticipant.account_id == a.id))
                for cp in q.scalars().all():
                    cp.status = "done"
                    cp.detail_json = json.dumps({"last_job": job.id, "ok": True})
            if job.type in PUBLISH_TYPES and payload.get("scheduled_thread_id"):
                t = await s.get(ScheduledThread, payload["scheduled_thread_id"])
                if t and res.data.get("id"):
                    t.published_threads_id = res.data["id"]
                    t.status = "published"
                    await broadcast("thread.updated", {"thread_id": t.id, "status": "published"})
                    if payload.get("first_reply"):
                        await enqueue(s, "first_reply", account_id=a.id, priority="low",
                                      payload={"target": res.data["id"], "text": payload["first_reply"]},
                                      scheduled_at=int(time.time()) + 60 * (1 + (a.id % 5)))
            if job.type in REPLY_TYPES and res.data.get("id"):
                await enqueue(s, "visibility_audit", account_id=a.id, priority="low",
                              payload={"message_id": payload.get("message_id", 0),
                                       "reply_id": res.data["id"]},
                              scheduled_at=int(time.time()) + 600)
            if job.type == "login":
                await _set_status(s, a, "active", "login sukses")
                if res.data.get("session_blob"):
                    a.session_blob_enc = encrypt(res.data["session_blob"], "accounts.session_blob_enc", str(a.id))
                if res.data.get("storage_state"):
                    a.storage_state_enc = encrypt(json.dumps(res.data["storage_state"]),
                                                  "accounts.storage_state_enc", str(a.id))
            if job.type == "resolve_checkpoint":
                await _set_status(s, a, "active", "checkpoint resolved; limit 50% 24 jam")
            if job.type == "snapshot" and res.data:
                d = res.data
                s.add(AccountStatsSnapshot(account_id=a.id, followers=int(d.get("followers", 0)),
                                           following=int(d.get("following", 0)),
                                           thread_count=int(d.get("thread_count", 0)),
                                           views=int(d.get("views", 0)), likes=int(d.get("likes", 0)),
                                           replies=int(d.get("replies", 0)), reposts=int(d.get("reposts", 0)),
                                           quotes=int(d.get("quotes", 0))))
            if job.type == "poll_replies" and isinstance(res.data.get("replies"), list):
                for r in res.data["replies"][:50]:
                    q = await s.execute(select(ThreadConversation).where(
                        ThreadConversation.account_id == a.id,
                        ThreadConversation.thread_id == str(r.get("thread_id", ""))))
                    conv = q.scalars().first()
                    if not conv:
                        conv = ThreadConversation(account_id=a.id, thread_id=str(r.get("thread_id", "")))
                        s.add(conv)
                        await s.flush()
                    s.add(ThreadMessage(conversation_id=conv.id, author=str(r.get("author", "")),
                                        text=str(r.get("text", ""))[:500]))
                    await broadcast("reply.new_message",
                                    {"account_id": a.id, "thread_id": conv.thread_id})
                await _apply_reply_rules(s, a, job)
        else:
            code = res.error_code
            if code == "E-LIMIT-BLOCK":
                a.health_score = max(0, a.health_score - 30)
                await _set_status(s, a, "restricted", "4279013/restricted tanpa retry; cooldown 24 jam")
                s.add(CheckpointEvent(account_id=a.id, kind="restricted", status="open"))
                await _alert(s, "account.restricted", f"akun {a.username} restricted", a.id)
            elif code == "E-AUTH-CHECKPOINT":
                a.health_score = max(0, a.health_score - 15)
                await _set_status(s, a, "checkpoint", "challenge Meta")
                s.add(CheckpointEvent(account_id=a.id, kind="checkpoint", status="open"))
                await _alert(s, "account.checkpoint", f"akun {a.username} checkpoint", a.id)
            elif code == "E-AUTH-TOKEN-EXPIRED":
                a.needs_reauth = 1
                await _alert(s, "oauth.needs_reauth", f"token {a.username} kadaluarsa", a.id)
            elif code == "E-AUTH-LOGIN":
                await _set_status(s, a, "wrong_password", "login gagal")
            elif code == "E-AUTH-2FA":
                await _set_status(s, a, "two_factor_required", "butuh kode 2FA")
            elif job.type == "login" and code in (
                    "E-ENGINE-BUG", "E-NET-PROXY", "E-NET-TIMEOUT", "E-INTERNAL", "E-LIMIT-RATE"):
                # Gagal infrastruktur (bukan salah akun) -> jangan macet di login_pending
                if a.status == "login_pending":
                    await _set_status(s, a, "new",
                                      f"login gagal infrastruktur ({code}); silakan login ulang")
                    await _alert(s, "login.failed", f"login {a.username} gagal: {code}", a.id)
            if payload.get("campaign_id"):
                q = await s.execute(select(CampaignParticipant).where(
                    CampaignParticipant.campaign_id == int(payload["campaign_id"]),
                    CampaignParticipant.account_id == a.id))
                for cp in q.scalars().all():
                    cp.status = "failed"
                    cp.detail_json = json.dumps({"last_job": job.id, "error": code})
        await s.flush()
    await s.commit()
    return res


async def refresh_oauth_token(s: AsyncSession, token_id: int, http=None) -> dict:
    """Refresh long-lived 60 hari via GET /refresh_access_token (mock-able)."""
    tok = await s.get(ThreadsToken, token_id)
    if not tok:
        return {"ok": False}
    old = decrypt(tok.access_token_enc, "threads_tokens.access_token_enc", str(tok.id))
    client = http or httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30)
    close = http is None
    try:
        r = await client.get("/refresh_access_token",
                             params={"grant_type": "th_refresh_token", "access_token": old})
        if r.status_code == 200:
            tok.access_token_enc = encrypt(r.json()["access_token"],
                                           "threads_tokens.access_token_enc", str(tok.id))
            tok.expires_at = int(time.time()) + 60 * 86400
            tok.last_refreshed_at = int(time.time())
            await s.commit()
            return {"ok": True, "expires_at": tok.expires_at}
        acc = await s.get(Account, tok.account_id)
        if acc:
            acc.needs_reauth = 1
            await s.commit()
        return {"ok": False, "status": r.status_code}
    finally:
        if close:
            await client.aclose()
