"""Endpoint eksekusi batch 2: login/bulk/oauth/threadstorm/growth/replies/campaign/analytics/AI."""
import respx
import httpx
from fastapi.testclient import TestClient

from thbuzzer import GRAPH_BASE
from thbuzzer.main import SESSION_TOKEN, create_app

app = create_app()


def hdr():
    return {"Authorization": f"Bearer {SESSION_TOKEN}"}


def test_execution_endpoints():
    with TestClient(app) as c:
        H = hdr()
        a1 = c.post("/accounts", json={"username": "exec1"}, headers=H).json()["id"]
        a2 = c.post("/accounts", json={"username": "exec2"}, headers=H).json()["id"]

        # login + bulk + grup + warmup
        assert c.post(f"/accounts/{a1}/login", headers=H).json()["status"] == "login_pending"
        r = c.post("/accounts/bulk", json={"ids": [a1, a2], "op": "pause"}, headers=H)
        assert r.json()["affected"] == 2
        c.post("/accounts/bulk", json={"ids": [a1, a2], "op": "resume"}, headers=H)
        g = c.post("/accounts/groups", json={"name": "tim-a"}, headers=H).json()["id"]
        assert c.get("/accounts/groups", headers=H).json()["items"]
        c.post(f"/accounts/{a1}/warmup", json={"plan_id": None}, headers=H)
        assert c.get(f"/accounts/{a1}/export", headers=H).json()["username"] == "exec1"
        c.post(f"/accounts/{a2}/status", json={"status": "active"}, headers=H)

        # oauth start
        r = c.post("/engines/oauth/start", json={"app_id": "123", "redirect_uri": "https://x.id/cb"}, headers=H)
        assert "threads.com/oauth/authorize" in r.json()["authorize_url"]

        # threadstorm + media validate + manifest + cancel + queue
        r = c.post("/threads-posts/threadstorm",
                   json={"account_id": a2, "text": ("Kalimat satu. " * 60)}, headers=H)
        assert r.json()["parts"] >= 2
        tid = r.json()["thread_ids"][0]
        assert c.post("/threads-posts/media/validate",
                      json={"kind": "image", "width": 1080, "height": 1080,
                            "size_bytes": 1000}, headers=H).json()["ok"] is True
        r = c.post("/threads-posts/media/validate",
                   json={"kind": "image", "width": 100, "size_bytes": 100}, headers=H)
        assert r.status_code == 422
        csv = ("account_id,text_template,topic_tag,reply_control,first_reply,scheduled_at,timezone\n"
               f'{a2},halo manifest,info,everyone,,0,Asia/Jakarta\n')
        assert c.post("/threads-posts/import-manifest", json={"csv": csv}, headers=H).json()["imported"] == 1
        assert c.post(f"/threads-posts/{tid}/cancel", headers=H).json()["ok"] is True
        assert "items" in c.get("/threads-posts/queue-24h", headers=H).json()

        # growth activity start/stats/pause/resume
        aid = c.post("/activities", json={"kind": "growth", "actions": [{"type": "like"}]},
                     headers=H).json()["id"]
        r = c.post(f"/activities/{aid}/start",
                   json={"filter": {"health_min": 0}, "targets": ["https://www.threads.com/@x/post/1"]}, headers=H)
        assert r.json()["jobs"] >= 1
        assert c.get(f"/activities/{aid}/stats", headers=H).json()["jobs"] >= 1
        c.post(f"/activities/{aid}/pause", headers=H)
        c.post(f"/activities/{aid}/resume", headers=H)

        # replies: rules list/send/poll/mass
        rid = c.post("/replies/rules", json={"name": "r2", "trigger": "any",
                                             "response_template": "hai {x}"}, headers=H).json()["id"]
        assert any(x["id"] == rid for x in c.get("/replies/rules", headers=H).json()["items"])
        assert c.post("/replies/send", json={"account_id": a2, "thread_id": "p1",
                                             "text": "halo!"}, headers=H).status_code == 200
        assert c.post("/replies/poll-now", json={"account_id": a2}, headers=H).status_code == 200
        mc = c.post("/replies/campaigns", json={"name": "m1"}, headers=H).json()["id"]
        r = c.post(f"/replies/campaigns/{mc}/start", headers=H)
        assert r.status_code == 422  # source kosong -> tolak jelas
        assert c.delete(f"/replies/rules/{rid}", headers=H).json()["ok"] is True

        # campaign participants/progress/retry/add
        camp = c.post("/campaigns", json={"name": "c9",
                                          "targets": ["https://www.threads.com/@x/post/2"],
                                          "actions": [], "account_ids": [a2]}, headers=H).json()["id"]
        c.post(f"/campaigns/{camp}/start", headers=H)
        assert c.get(f"/campaigns/{camp}/participants", headers=H).json()["items"]
        assert c.get(f"/campaigns/{camp}/progress", headers=H).json()["total"] >= 1
        assert c.post(f"/campaigns/{camp}/retry-failed", json={}, headers=H).json()["ok"] is True

        # analytics series/snapshot/jobs/recurring
        assert "items" in c.get("/analytics/series/account?account_id=1", headers=H).json()
        assert c.post("/analytics/snapshot-now", json={"account_id": a2}, headers=H).status_code == 200
        jobs = c.get("/analytics/jobs", headers=H).json()["items"]
        assert jobs
        jid = jobs[0]["id"]
        assert c.post(f"/analytics/jobs/{jid}/cancel", headers=H).json()["ok"] is True
        assert c.post(f"/analytics/jobs/{jid}/retry", headers=H).json()["ok"] is True
        assert c.get("/analytics/recurring", headers=H).json()["items"]

        # AI personas/prompts/generate-fallback + alerts settings
        assert c.post("/ai/personas", json={"name": " Survivors ", "spec": {"tone": "santai"}},
                      headers=H).status_code == 201
        assert c.get("/ai/personas", headers=H).json()["items"]
        assert c.post("/ai/prompts", json={"reply": "sapaan ramah"}, headers=H).json()["ok"] is True
        assert c.get("/ai/prompts", headers=H).json() == {"reply": "sapaan ramah"}
        r = c.post("/ai/generate", json={"kind": "reply", "context": "thread viral",
                                         "stance": "kepo"}, headers=H)
        assert r.json()["text"] and r.json().get("fallback") == "template"
        assert c.post("/alerts/settings", json={"alerts.webhook_url": ""}, headers=H).json()["ok"] is True


@respx.mock
def test_oauth_callback_mock():
    respx.post(f"{GRAPH_BASE}/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "short1"}))
    respx.get(f"{GRAPH_BASE}/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "long1", "expires_in": 5184000}))
    respx.get(f"{GRAPH_BASE}/me").mock(
        return_value=httpx.Response(200, json={"id": "999", "username": "exec1"}))
    with TestClient(app) as c:
        H = hdr()
        accs = c.get("/accounts", headers=H).json()["items"]
        aid = next(a["id"] for a in accs if a["username"] == "exec1")
        r = c.post("/engines/oauth/callback",
                   json={"account_id": aid, "code": "CODE", "app_id": "123",
                         "app_secret": "sec", "redirect_uri": "https://x.id/cb"}, headers=H)
        assert r.status_code == 200, r.text
        assert r.json()["threads_user_id"] == "999"
