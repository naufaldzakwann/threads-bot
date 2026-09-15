"""Validasi input total: URL wajib Threads, angka wajib masuk akal, pesan Indonesia."""
import pytest
from fastapi.testclient import TestClient

from thbuzzer.main import SESSION_TOKEN, create_app
from thbuzzer.utils.validators import Invalid, http_url, pos_int, thread_target, threads_url

app = create_app()


def test_threads_url():
    assert threads_url("https://www.threads.com/@akun/post/ABC123").startswith("https://")
    assert threads_url("threads.com/@a/post/1")  # tanpa skema diterima & dinormalisasi
    assert threads_url("https://threads.net/t/xyz")
    for bad in ["https://instagram.com/p/1", "https://www.threads.com/@akun",
                "https://evil-threads.com/@a/post/1", "bukan url", "", "https://threads.com/"]:
        with pytest.raises(Invalid, match="tidak valid"):
            threads_url(bad)
    try:
        threads_url("https://x.com/y/post/1")
        assert False
    except Invalid as e:
        assert "bukan link Threads" in str(e)


def test_numbers():
    assert pos_int(5, "n") == 5
    assert pos_int("7", "n") == 7
    assert pos_int(0, "n", min=0) == 0
    for bad in [-1, 0, "abc", "", "1.5", 2.5, True, None, [], "  "]:
        with pytest.raises(Invalid, match="tidak valid"):
            pos_int(bad, "n")
    with pytest.raises(Invalid, match="maksimal 6"):
        pos_int(7, "pacing", max=6)


def test_thread_target_and_http():
    assert thread_target("12345") == "12345"  # ID polos boleh
    assert thread_target("https://www.threads.com/@a/post/1")
    with pytest.raises(Invalid, match="bukan link Threads"):
        thread_target("https://x.com/a/post/1")
    assert http_url("example.com/x")
    with pytest.raises(Invalid):
        http_url("notaurl")


def test_api_rejections():
    with TestClient(app) as c:
        H = {"Authorization": f"Bearer {SESSION_TOKEN}"}
        # campaign target bukan Threads
        r = c.post("/campaigns", json={"name": "x", "targets": ["https://instagram.com/p/1"]}, headers=H)
        assert r.status_code == 422 and "bukan link Threads" in r.text
        # campaign target bukan post
        r = c.post("/campaigns", json={"name": "x", "targets": ["https://www.threads.com/@a"]}, headers=H)
        assert r.status_code == 422
        # account_ids negatif
        r = c.post("/campaigns", json={"name": "x", "targets": ["https://www.threads.com/@a/post/1"],
                                       "account_ids": [-1]}, headers=H)
        assert r.status_code == 422 and "tidak valid" in r.text
        # pacing di luar 1-6
        r = c.post("/campaigns", json={"name": "x", "targets": ["https://www.threads.com/@a/post/1"],
                                       "max_target_actions_per_minute": 99}, headers=H)
        assert r.status_code == 422
        # 21 target
        r = c.post("/campaigns", json={"name": "x",
                                       "targets": ["https://www.threads.com/@a/post/1"] * 21}, headers=H)
        assert r.status_code == 422
        # growth target bukan Threads
        aid = c.post("/activities", json={"kind": "growth", "actions": [{"type": "like"}]}, headers=H).json()["id"]
        r = c.post(f"/activities/{aid}/start", json={"targets": ["https://x.com/a"]}, headers=H)
        assert r.status_code == 422 and "bukan link Threads" in r.text
        # replies send: account_id kacau + target non-threads
        r = c.post("/replies/send", json={"account_id": -2, "thread_id": "p1", "text": "hi"}, headers=H)
        assert r.status_code == 422 and "account_id tidak valid" in r.text
        r = c.post("/replies/send", json={"account_id": 1, "thread_id": "https://x.com/a/post/1",
                                          "text": "hi"}, headers=H)
        assert r.status_code == 422 and "bukan link Threads" in r.text
        # quick-thread ids kacau
        r = c.post("/threads-posts/quick-thread", json={"account_ids": [0], "text": "halo"}, headers=H)
        assert r.status_code == 422 and "account_ids tidak valid" in r.text
        # media negatif
        r = c.post("/threads-posts/media/validate",
                   json={"kind": "image", "width": -5, "size_bytes": 10}, headers=H)
        assert r.status_code == 422 and "width tidak valid" in r.text
        # bulk: op ngawur + ids kosong
        r = c.post("/accounts/bulk", json={"ids": [1], "op": "meledak"}, headers=H)
        assert r.status_code == 422 and "op tidak valid" in r.text
        r = c.post("/accounts/bulk", json={"ids": [], "op": "pause"}, headers=H)
        assert r.status_code == 422
        # proxy jelek + port gila
        r = c.post("/proxies", json={"url": "bukan-proxy"}, headers=H)
        assert r.status_code == 422 and "tidak valid" in r.text
        r = c.post("/proxies", json={"url": "127.0.0.1:99999"}, headers=H)
        assert r.status_code == 422
        # oauth redirect bukan URL + scope ngawur
        r = c.post("/engines/oauth/start", json={"app_id": "1", "redirect_uri": "bukan-url"}, headers=H)
        assert r.status_code == 422 and "redirect_uri tidak valid" in r.text
        r = c.post("/engines/oauth/start",
                   json={"app_id": "1", "redirect_uri": "https://x.id/cb", "scopes": ["scope_palsu"]}, headers=H)
        assert r.status_code == 422 and "scopes tidak valid" in r.text
        # AI generate ngawur
        r = c.post("/ai/generate", json={"kind": "ngawur", "context": "x"}, headers=H)
        assert r.status_code == 422 and "kind tidak valid" in r.text
        r = c.post("/ai/generate", json={"kind": "reply", "context": "x", "max_chars": 0}, headers=H)
        assert r.status_code == 422 and "max_chars tidak valid" in r.text
        r = c.post("/ai/generate", json={"kind": "reply", "context": "   "}, headers=H)
        assert r.status_code == 422 and "context tidak valid" in r.text
        # series days gila + snapshot tanpa akun
        r = c.get("/analytics/series/account?account_id=1&days=9999", headers=H)
        assert r.status_code == 422
        r = c.post("/analytics/snapshot-now", json={"account_id": "abc"}, headers=H)
        assert r.status_code == 422 and "account_id tidak valid" in r.text
        # alert webhook bukan URL + quiet hours format salah
        r = c.post("/alerts/settings", json={"alerts.webhook_url": "bukan-url"}, headers=H)
        assert r.status_code == 422 and "webhook_url tidak valid" in r.text
        r = c.post("/alerts/settings", json={"alerts.quiet_hours": "malam-pagi"}, headers=H)
        assert r.status_code == 422 and "quiet_hours tidak valid" in r.text
        # threadstorm tanpa akun + manifest account 0
        r = c.post("/threads-posts/threadstorm", json={"account_id": 0, "text": "x " * 300}, headers=H)
        assert r.status_code == 422 and "account_id tidak valid" in r.text
        csv = "account_id,text_template,topic_tag,reply_control,first_reply,scheduled_at,timezone\n0,halo,t,everyone,,0,Asia/Jakarta\n"
        r = c.post("/threads-posts/import-manifest", json={"csv": csv}, headers=H)
        assert r.json()["imported"] == 0 and len(r.json()["invalid"]) == 1
