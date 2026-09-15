"""Task queue persisten §14: jobs + job_runs, tick 1 dtk, guard kuota, retry E-*, DLQ, kill 3 lapis."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thbuzzer.models.all import Job, JobRun
from thbuzzer.utils.errors import backoff_minutes, is_retryable

PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}
DLQ_TYPES = {"reply", "like", "follow", "quote", "repost", "campaign_reply"}
JOB_TYPES = ["publish_thread", "publish_carousel", "publish_video", "first_reply", "reply", "repost",
             "quote", "hide_reply", "delete_thread", "poll_replies", "snapshot", "health_check",
             "campaign_reply", "warmup_tick", "login", "verify_oauth", "refresh_oauth", "recurring",
             "oauth_refresh", "quota_reset", "resolve_checkpoint"]


@dataclass
class KillSwitch:
    global_kill: bool = False
    group_kill: set[int] = field(default_factory=set)
    account_kill: set[int] = field(default_factory=set)

    def blocked(self, account_id: int | None, group_id: int | None = None) -> bool:
        if self.global_kill:
            return True
        if account_id in self.account_kill:
            return True
        if group_id in self.group_kill:
            return True
        return False


async def enqueue(session: AsyncSession, type: str, account_id: int | None = None, priority: str = "normal",
                 payload: dict | None = None, scheduled_at: int | None = None, dedup_key: str = "",
                 engine_hint: str = "", max_attempts: int = 3) -> Job:
    if dedup_key:
        q = await session.execute(select(Job).where(Job.dedup_key == dedup_key).limit(1))
        existing = q.scalars().first()
        if existing:
            return existing
    job = Job(type=type, account_id=account_id, priority=priority,
              payload_json=json.dumps(payload or {}, ensure_ascii=False),
              scheduled_at=scheduled_at or int(time.time()), dedup_key=dedup_key,
              engine_hint=engine_hint, max_attempts=max_attempts)
    session.add(job)
    await session.flush()
    return job


async def next_job(session: AsyncSession, kill: KillSwitch) -> Job | None:
    q = await session.execute(
        select(Job).where(Job.status.in_(["scheduled", "pending"]))
        .where(Job.scheduled_at <= int(time.time())).limit(50))
    cands = list(q.scalars().all())
    cands.sort(key=lambda j: (PRIORITY_ORDER.get(j.priority, 2), j.scheduled_at))
    for j in cands:
        if kill.blocked(j.account_id):
            continue
        return j
    return None


async def finish(session: AsyncSession, job: Job, success: bool, error_code: str = "", latency_ms: int = 0) -> None:
    session.add(JobRun(job_id=job.id, success=1 if success else 0, error_code=error_code, latency_ms=latency_ms))
    if success:
        job.status = "completed"
        return
    job.attempt += 1
    if error_code in ("E-LIMIT-QUOTA",):
        job.status = "held"  # antre besok, bukan gagal (§14 guard + §3.5 tanpa pengurang health)
        job.scheduled_at = int(time.time()) + 86400
        return
    if is_retryable(error_code) and job.attempt < job.max_attempts:
        job.status = "pending"
        job.scheduled_at = int(time.time()) + backoff_minutes(job.attempt, error_code) * 60
        return
    if job.type in DLQ_TYPES:
        job.status = "dead_letter"
    else:
        job.status = "failed"
