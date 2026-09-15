"""Worker adaptif §3.3 + §14: tick 1 dtk, AccountExecutionGuard, limiter 3 lapis, kill 3 lapis."""
from __future__ import annotations

import asyncio

import psutil

from thbuzzer.tasks.limiter import TripleLimiter
from thbuzzer.tasks.queue import KillSwitch, finish, next_job

_guard: set[int] = set()
kill = KillSwitch()
limiter = TripleLimiter()
_slow_streak = 0


async def tick(session_factory, executor=None) -> str:
    """Satu tick: ambil next_job -> guard/limiter/kill -> executor -> finish. Return status."""
    from thbuzzer.services.dispatch import execute_job
    executor = executor or execute_job
    try:
        cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
        global _slow_streak
        _slow_streak = _slow_streak + 1 if (cpu > 85 or ram > 90) else 0
    except Exception:
        pass
    async with session_factory() as s:
        job = await next_job(s, kill)
        if not job:
            return "idle"
        if (job.account_id or 0) in _guard:
            return "guarded"
        ok, _ = limiter.check(job.account_id or 0, "default-ip", 20)
        if not ok:
            return "limited"
        _guard.add(job.account_id or 0)
        try:
            job.status = "running"
            await s.commit()
            res = await executor(s, job)
            await finish(s, job, res.success, res.error_code, res.latency_ms)
            await s.commit()
            try:
                from thbuzzer.api.hub import broadcast
                await broadcast("job.updated", {"job_id": job.id, "status": job.status})
            except Exception:
                pass
            return f"done:{job.type}:{job.status}"
        finally:
            _guard.discard(job.account_id or 0)


async def run_forever(session_factory, interval: float = 1.0) -> None:
    while True:
        try:
            await tick(session_factory)
        except Exception:
            pass
        await asyncio.sleep(interval)
