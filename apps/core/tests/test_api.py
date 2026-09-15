"""API integration: CRUD akun, validator, topic-set, campaign pacing, visibility audit."""
from fastapi.testclient import TestClient

from thbuzzer.main import SESSION_TOKEN, create_app

app = create_app()


def hdr():
    return {"Authorization": f"Bearer {SESSION_TOKEN}"}


def test_accounts_crud_and_status():
    with TestClient(app) as c:
        H = hdr()
        r = c.post("/accounts", json={"username": "uji_threads", "account_tier": "buzzer_satellite",
                                      "account_role": "scout"}, headers=H)
        assert r.status_code == 201, r.text
        aid = r.json()["id"]
        r = c.get("/accounts", headers=H)
        assert any(i["username"] == "uji_threads" for i in r.json()["items"])
        r = c.post(f"/accounts/{aid}/status", json={"status": "active"}, headers=H)
        assert r.json()["status"] == "active"


def test_thread_validator_and_sanitizer():
    with TestClient(app) as c:
        H = hdr()
        r = c.post("/threads-posts", json={"account_id": 1, "text": "x" * 501}, headers=H)
        assert r.status_code == 422
        r = c.post("/threads-posts", json={"account_id": 1, "text": "#inovasi #teknologi keren"}, headers=H)
        assert r.status_code == 201 and r.json()["topic_tag"] == "inovasi"


def test_quick_thread_and_campaign_pacing():
    with TestClient(app) as c:
        H = hdr()
        a1 = c.post("/accounts", json={"username": "q1"}, headers=H).json()["id"]
        a2 = c.post("/accounts", json={"username": "q2"}, headers=H).json()["id"]
        for aid in (a1, a2):
            c.post(f"/accounts/{aid}/status", json={"status": "active"}, headers=H)
        r = c.post("/threads-posts/quick-thread", json={"account_ids": [a1, a2], "text": "halo dunia"}, headers=H)
        assert len(r.json()["scheduled"]) == 2
        r = c.post("/campaigns", json={"name": "amp", "targets": ["https://www.threads.com/@x/post/123"],
                                       "actions": [{"type": "reply"}], "account_ids": [a1, a2],
                                       "spread_minutes": 180, "max_target_actions_per_minute": 3}, headers=H)
        cid = r.json()["id"]
        r = c.post(f"/campaigns/{cid}/start", headers=H)
        assert r.json()["ok"] is True


def test_replies_rules_and_visibility():
    with TestClient(app) as c:
        H = hdr()
        r = c.post("/replies/rules", json={"name": "sapa", "trigger": "keyword", "pattern": "halo",
                                           "response_template": "halo juga!"}, headers=H)
        assert r.status_code == 201
        r = c.post("/replies/rules/test", json={"pattern": "halo", "text": "halo kak"}, headers=H)
        assert r.json()["matched"] is True


def test_system_and_proxies():
    with TestClient(app) as c:
        H = hdr()
        assert c.get("/system/info", headers=H).json()["app"] == "THBuzzer"
        r = c.post("/proxies", json={"url": "127.0.0.1:8080", "country": "ID"}, headers=H)
        assert r.status_code == 201
        r = c.post("/proxies/auto-assign", json={}, headers=H)
        assert "proxy_id" in r.json()
