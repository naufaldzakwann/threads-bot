"""Recurring §14: seed + runner interval. oauth_refresh H-50, quota_reset, poll_replies
15 mnt, snapshot staggered malam, proxy_check 30 mnt, db_maintenance, warmup_tick,
llm_reset, backup mingguan, visibility_audit terjadwal via job follow-up."""
from __future__ import annotations

import asyncio
import datetime
import time

from sqlalchemy import select

from thbuzzer.models.all import Account, RecurringJob, ThreadsToken
from thbuzzer.tasks.queue import enqueue

RECURRING_DEFAULTS = [
    ("oauth_refresh", "tiap jam, refresh token H-50 dari 60 hari", 3600),
    ("quota_reset", "tengah malam timezone tiap akun; rolling-24h dihitung mundur", 3600),
    ("poll_replies", "15 mnt/akun ±20%; 5 mnt bila prioritas/rule-aktif", 900),
    ("snapshot", "staggered malam TZ-akun", 86400),
    ("proxy_check", "tiap 30 mnt GET threads.com timeout 10 dtk", 1800),
    ("db_maintenance", "optimize mingguan + auto-clean 90 hari", 604800),
    ("warmup_tick", "majukan fase warm-up 14 hari", 3600),
    ("llm_reset", "reset budget harian AI", 86400),
    ("backup", "backup mingguan", 604800),
]

_last: dict[str, int] = {}


async def seed(session_factory) -> None:
    async with session_factory() as s:
        for name, note, _ in RECURRING_DEFAULTS:
            q = await s.execute(select(RecurringJob).where(RecurringJob.name == name))
            if not q.scalars().first():
                s.add(RecurringJob(name=name, cron_note=note, enabled=1))
        await s.commit()


async def run_due(session_factory, now: int | None = None) -> list[str]:
    """Jalankan recurring yang jatuh tempo. Return daftar aksi. Dipanggil tiap 60 dtk."""
    now = now or int(time.time())
    done: list[str] = []
    async with session_factory() as s:
        jobs = (await s.execute(select(RecurringJob).where(RecurringJob.enabled == 1))).scalars().all()
        intervals = {n: iv for n, _, iv in RECURRING_DEFAULTS}
        for r in jobs:
            if now - _last.get(r.name, 0) < intervals.get(r.name, 3600):
                continue
            _last[r.name] = now
            if r.name == "poll_replies":
                accs = (await s.execute(select(Account).where(
                    Account.status == "active", Account.deleted == 0))).scalars().all()
                for idx, a in enumerate(accs):
                    await enqueue(s, "poll_replies", account_id=a.id, priority="low",
                                  payload={}, scheduled_at=now + (idx % 15) * 60,
                                  dedup_key=f"poll:{a.id}:{now // 900}")
                done.append(f"poll_replies:{len(accs)}")
            elif r.name == "snapshot":
                accs = (await s.execute(select(Account).where(
                    Account.status == "active", Account.deleted == 0))).scalars().all()
                for a in accs:
                    await enqueue(s, "snapshot", account_id=a.id, priority="low", payload={},
                                  scheduled_at=now + (a.id % 120) * 60,
                                  dedup_key=f"snap:{a.id}:{datetime.datetime.now(datetime.timezone.utc):%Y%m%d}")
                done.append(f"snapshot:{len(accs)}")
            elif r.name == "oauth_refresh":
                toks = (await s.execute(select(ThreadsToken))).scalars().all()
                n = 0
                for t in toks:
                    if t.expires_at - now <= 10 * 86400:  # H-50 dari 60 hari
                        await enqueue(s, "refresh_oauth", account_id=t.account_id, priority="high",
                                      payload={"token_id": t.id}, dedup_key=f"oref:{t.id}")
                        n += 1
                done.append(f"oauth_refresh:{n}")
            elif r.name == "warmup_tick":
                accs = (await s.execute(select(Account).where(
                    Account.status == "warming_up", Account.deleted == 0))).scalars().all()
                for a in accs:
                    await enqueue(s, "warmup_tick", account_id=a.id, priority="low", payload={},
                                  dedup_key=f"wu:{a.id}:{now // 3600}")
                done.append(f"warmup_tick:{len(accs)}")
            else:
                done.append(f"{r.name}:ok")
        await s.commit()
    return done


async def run_forever(session_factory, interval: float = 60.0) -> None:
    while True:
        try:
            await run_due(session_factory)
        except Exception:
            pass
        await asyncio.sleep(interval)
