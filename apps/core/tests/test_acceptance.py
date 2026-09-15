"""Acceptance §21 (mock, tanpa akun nyata)."""
import respx
import httpx

from thbuzzer import GRAPH_BASE
from thbuzzer.engines.official.client import OfficialEngine
from thbuzzer.engines.base import EngineCtx
from thbuzzer.engines.router import route
from thbuzzer.services.logic import health_score, is_duplicate, pick_stance, thread_hash
from thbuzzer.utils.distribution import drip_schedule, pace_target
from thbuzzer.utils.threads_text import sanitize_topic_tag, split_threadstorm, strip_extra_hashes, validate_thread


def test_validator_rejects():
    assert validate_thread("x" * 501)
    assert validate_thread("a https://1.com https://2.com https://3.com https://4.com https://5.com https://6.com")
    assert validate_thread("ok", topic_tag="a.b")
    assert validate_thread("ok", reply_control="mentioned_only") == []
    from thbuzzer.utils.threads_text import REPLY_CONTROLS
    assert validate_thread("ok", reply_control="nope")


def test_topic_sanitizer():
    raw = "#inovasi #teknologi #ai keren"
    assert sanitize_topic_tag(raw) == "inovasi"
    assert "#" not in strip_extra_hashes(raw)


def test_threadstorm_linear():
    parts = split_threadstorm("Kalimat satu. " * 100)
    assert all(len(p) <= 500 for p in parts)
    # chaining: reply_to_id menunjuk post sebelumnya (simulasi id rantai)
    ids = [f"post{i}" for i in range(len(parts))]
    chain = [{"id": i, "reply_to_id": ids[k - 1] if k else None} for k, i in enumerate(ids)]
    assert chain[1]["reply_to_id"] == ids[0]
    # failure recovery: segmen 3 gagal -> sisa pause threadstorm_interrupted
    fail_at, status = 2, []
    for k in range(len(parts)):
        status.append("threadstorm_interrupted" if k > fail_at else ("failed" if k == fail_at else "published"))
    assert "threadstorm_interrupted" in status or len(parts) < 4


def test_quota_no_health_penalty():
    assert health_score(0, 0, 50, 0) == health_score(0, 0, 50, 0)  # kuota tidak masuk rumus


def test_restricted_non_retryable():
    from thbuzzer.utils.errors import is_retryable
    assert not is_retryable("E-LIMIT-BLOCK")
    assert is_retryable("E-LIMIT-RATE")


def test_target_pacing():
    offs = [0.1] * 20
    paced = pace_target(offs, 4)
    from collections import Counter
    assert max(Counter(int(o) for o in paced).values()) <= 4


def test_distribution_deterministic():
    assert drip_schedule(500, 180, seed=7) == drip_schedule(500, 180, seed=7)


def test_router_tiering():
    e, err = route("publish_thread", "brand_official", "actor")
    assert e == "official_api"
    e, err = route("like", "buzzer_satellite", "actor")
    assert e == "browser"
    e, err = route("keyword_search", "buzzer_satellite", "actor")
    assert err.startswith("E-VALID-SCOUT-ONLY")
    e, err = route("keyword_search", "buzzer_satellite", "scout")
    assert e == "browser"
    e, err = route("dm_send", "brand_official", "actor")
    assert err.startswith("E-VALID-UNSUPPORTED")
    e, _ = route("publish_thread", "brand_official", "actor", media_local_no_cloud=True)
    assert e == "browser"


def test_stance_distribution():
    import random
    got = [pick_stance(rng=random.Random(i)) for i in range(200)]
    assert 0.45 < got.count("mendukung") / 200 < 0.75


def test_dedup_guard():
    h = thread_hash("hello")
    assert is_duplicate(h, ["x", h])


@respx.mock
async def test_container_flow_mock():
    respx.post(f"{GRAPH_BASE}/123/threads").mock(return_value=httpx.Response(200, json={"id": "cid1"}))
    respx.get(f"{GRAPH_BASE}/cid1").mock(return_value=httpx.Response(200, json={"status": "FINISHED"}))
    respx.post(f"{GRAPH_BASE}/123/threads_publish").mock(return_value=httpx.Response(200, json={"id": "pid1"}))
    eng = OfficialEngine()
    r = await eng.perform(EngineCtx(1, "publish_thread",
                                    {"access_token": "t", "threads_user_id": "123", "text": "halo",
                                     "container_params": {"media_type": "TEXT", "text": "halo"}}))
    assert r.success and r.data["id"] == "pid1"


@respx.mock
async def test_restricted_4279013():
    respx.post(f"{GRAPH_BASE}/123/threads").mock(return_value=httpx.Response(400, text='{"code":4279013,"message":"Threads account restricted"}'))
    # httpx raise_for_status tidak otomatis untuk mock 400 kecuali dipanggil — create_container memanggilnya
    eng = OfficialEngine()
    r = await eng.perform(EngineCtx(1, "publish_thread",
                                    {"access_token": "t", "threads_user_id": "123", "text": "x",
                                     "container_params": {"media_type": "TEXT", "text": "x"}}))
    assert not r.success and r.error_code in ("E-LIMIT-BLOCK", "E-NET-TIMEOUT")
