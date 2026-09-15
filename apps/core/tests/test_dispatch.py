"""Eksekusi end-to-end via FakeEngine + sqlite memory (§21 ganda: guard dobel, kuota, restricted)."""
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from thbuzzer.db.base import Base
from thbuzzer.engines.base import ActionResult, Engine
from thbuzzer.models.all import Account, Interaction, Job, QuotaUsage, ScheduledThread
from thbuzzer.services.dispatch import execute_job
from thbuzzer.tasks.queue import enqueue, finish
from thbuzzer.tasks import worker


class Fake(Engine):
    def __init__(self, name, result):
        self.name = name
        self._r = result
        self.calls = 0

    async def perform(self, ctx):
        self.calls += 1
        return self._r


def fakes(result):
    ok = Fake("x", result)
    return {"official_api": ok, "private_unofficial": ok, "browser": ok}


@pytest.fixture
async def sf():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False},
                              poolclass=StaticPool)
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    return async_sessionmaker(eng, expire_on_commit=False)


async def mk_account(s, tier="brand_official", status="active", health=100):
    a = Account(username=f"u{time_ns()}", status=status, health_score=health,
                account_tier=tier, account_role="actor", default_engine="official_api")
    s.add(a)
    await s.flush()
    return a


def time_ns():
    import time
    return time.time_ns()


async def test_publish_success_marks_thread_and_quota(sf):
    async with sf() as s:
        a = await mk_account(s)
        t = ScheduledThread(account_id=a.id, text_rendered="halo", status="scheduled")
        s.add(t)
        await s.flush()
        job = await enqueue(s, "publish_thread", account_id=a.id,
                            payload={"scheduled_thread_id": t.id}, dedup_key=f"p{t.id}")
        await s.commit()
        res = await execute_job(s, job, fakes(ActionResult(True, data={"id": "pid9"}, engine_used="official_api")))
        assert res.success
        await finish(s, job, res.success, res.error_code, 0)
        assert job.status == "completed"
        t2 = await s.get(ScheduledThread, t.id)
        assert t2.published_threads_id == "pid9" and t2.status == "published"
        q = (await s.execute(select(QuotaUsage).where(QuotaUsage.account_id == a.id))).scalars().first()
        assert q.posts == 1


async def test_publish_dedup_guard_skips_engine(sf):
    async with sf() as s:
        a = await mk_account(s)
        t = ScheduledThread(account_id=a.id, text_rendered="x", status="published", published_threads_id="pid1")
        s.add(t)
        await s.flush()
        job = await enqueue(s, "publish_thread", account_id=a.id, payload={"scheduled_thread_id": t.id})
        await s.commit()
        boom = Fake("x", ActionResult(True, data={"id": "SHOULD-NOT-HAPPEN"}))
        res = await execute_job(s, job, {"official_api": boom, "private_unofficial": boom, "browser": boom})
        assert res.success and res.data.get("dedup") is True and boom.calls == 0


async def test_quota_full_holds_without_engine_call(sf):
    async with sf() as s:
        a = await mk_account(s)
        from thbuzzer.services import dispatch as D
        real_today, D._today = D._today, lambda: "2099-01-01"
        try:
            s.add(QuotaUsage(account_id=a.id, day=D._today(), posts=250))
            await s.flush()
            job = await enqueue(s, "publish_thread", account_id=a.id, payload={"text": "x"})
            await s.commit()
            boom = Fake("x", ActionResult(True, data={"id": "NO"}))
            res = await execute_job(s, job, {"official_api": boom, "private_unofficial": boom, "browser": boom})
            assert res.error_code == "E-LIMIT-QUOTA" and boom.calls == 0
            await finish(s, job, False, res.error_code, 0)
            assert job.status == "held"
        finally:
            D._today = real_today


async def test_restricted_no_retry_and_quarantine(sf):
    async with sf() as s:
        a = await mk_account(s)
        job = await enqueue(s, "reply", account_id=a.id, payload={"target": "t", "text": "hi"})
        await s.commit()
        res = await execute_job(s, job, fakes(ActionResult(False, error_code="E-LIMIT-BLOCK", engine_used="browser")))
        assert res.error_code == "E-LIMIT-BLOCK"
        await finish(s, job, False, res.error_code, 0)
        assert job.status == "dead_letter"  # tanpa retry
        a2 = await s.get(Account, a.id)
        assert a2.status == "restricted" and a2.health_score == 70


async def test_reply_logs_interaction_and_schedules_audit(sf):
    async with sf() as s:
        a = await mk_account(s, tier="buzzer_satellite")
        job = await enqueue(s, "reply", account_id=a.id, payload={"target": "post1", "text": "keren"})
        await s.commit()
        res = await execute_job(s, job, fakes(ActionResult(True, data={"id": "r1"}, engine_used="browser")))
        assert res.success
        inter = (await s.execute(select(Interaction).where(Interaction.account_id == a.id))).scalars().all()
        assert len(inter) == 1 and inter[0].action == "reply"
        audit = (await s.execute(select(Job).where(Job.type == "visibility_audit"))).scalars().all()
        assert len(audit) == 1


async def test_scout_only_and_dm_rejected(sf):
    async with sf() as s:
        a = await mk_account(s, tier="buzzer_satellite")
        j1 = await enqueue(s, "keyword_search", account_id=a.id, payload={})
        r1 = await execute_job(s, j1, fakes(ActionResult(True)))
        assert r1.error_code == "E-VALID-SCOUT-ONLY"
        j2 = await enqueue(s, "dm_send", account_id=a.id, payload={})
        r2 = await execute_job(s, j2, fakes(ActionResult(True)))
        assert r2.error_code == "E-VALID-UNSUPPORTED"


async def test_worker_tick_executes_pending_job(sf):
    async with sf() as s:
        a = await mk_account(s)
        await enqueue(s, "health_check", account_id=a.id, payload={})
        await s.commit()
    st = await worker.tick(sf, executor=lambda s, j: execute_job(
        s, j, fakes(ActionResult(True, data={"ok": 1}, engine_used="browser"))))
    assert st.startswith("done:health_check")
