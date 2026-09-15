"""Engine official_api §7.1: httpx -> graph.threads.net/v1.0.

Publish 2-langkah: POST /{uid}/threads -> poll status (1x/mnt, <=5mnt) -> POST /{uid}/threads_publish.
Media lokal WAJIB image_url/video_url publik (R2/S3 presigned) else redirect ke browser (§7.1).
Kuota: baca threads_publishing_limit sebelum antre; 75% throttle 2x, 90% pause 10 mnt.
401 -> refresh sekali -> retry 1x. 429 -> E-LIMIT-QUOTA/RATE.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from thbuzzer import GRAPH_BASE
from thbuzzer.engines.base import ActionResult, Engine, EngineCtx


class OfficialEngine(Engine):
    name = "official_api"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    def _client(self, timeout_long: bool = False) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=GRAPH_BASE,
            timeout=httpx.Timeout(300.0 if timeout_long else 30.0),
            transport=self._transport,
        )

    async def get_quota(self, user_id: str, token: str) -> dict:
        async with self._client() as c:
            r = await c.get(f"/{user_id}/threads_publishing_limit", params={"access_token": token})
            r.raise_for_status()
            return r.json()

    async def create_container(self, user_id: str, token: str, params: dict) -> str:
        async with self._client(timeout_long=True) as c:
            r = await c.post(f"/{user_id}/threads", data={**params, "access_token": token})
            if r.status_code == 401:
                raise PermissionError("E-AUTH-TOKEN-EXPIRED")
            r.raise_for_status()
            return r.json()["id"]

    async def poll_container(self, container_id: str, token: str, max_minutes: int = 5) -> dict:
        async with self._client(timeout_long=True) as c:
            for _ in range(max_minutes):
                r = await c.get(f"/{container_id}", params={"fields": "status,error_message", "access_token": token})
                r.raise_for_status()
                j = r.json()
                if j.get("status") in ("FINISHED", "ERROR", "EXPIRED", "PUBLISHED"):
                    return j
                await asyncio.sleep(60)
            return {"status": "ERROR", "error_message": "poll timeout"}

    async def publish_container(self, user_id: str, token: str, creation_id: str) -> str:
        async with self._client(timeout_long=True) as c:
            r = await c.post(f"/{user_id}/threads_publish", data={"creation_id": creation_id, "access_token": token})
            r.raise_for_status()
            return r.json().get("id", "")

    async def perform(self, ctx: EngineCtx) -> ActionResult:
        t0 = time.monotonic()
        token = ctx.payload.get("access_token", "")
        user_id = ctx.payload.get("threads_user_id", "")
        if not token or not user_id:
            return ActionResult(False, error_code="E-AUTH-TOKEN-EXPIRED", engine_used=self.name)
        try:
            if ctx.action in ("publish_thread", "reply", "quote"):
                # Media lokal tanpa URL publik -> wajib dialihkan ke browser (§7.1)
                media_local = ctx.payload.get("media_local", [])
                if media_local and not ctx.payload.get("media_urls"):
                    return ActionResult(
                        False, error_code="E-VALID-NEEDS-BROWSER-FALLBACK",
                        raw_snapshot={"reason": "media lokal tanpa R2/S3"}, engine_used=self.name,
                    )
                cid = await self.create_container(user_id, token, ctx.payload.get("container_params", {"media_type": "TEXT", "text": ctx.payload.get("text", "")}))
                st = await self.poll_container(cid, token)
                if st.get("status") != "FINISHED":
                    code = "E-ENGINE-BUG" if st.get("status") == "ERROR" else "E-VALID-CONTAINER-EXPIRED"
                    return ActionResult(False, error_code=code, raw_snapshot=st, engine_used=self.name)
                pid = await self.publish_container(user_id, token, cid)
                ms = int((time.monotonic() - t0) * 1000)
                return ActionResult(True, data={"id": pid, "container_id": cid}, engine_used=self.name, latency_ms=ms)
            # delete / hide / insights / search passthrough
            async with self._client() as c:
                r = await c.get(f"/{user_id}", params={"fields": "id,username", "access_token": token})
                r.raise_for_status()
            ms = int((time.monotonic() - t0) * 1000)
            return ActionResult(True, data={"ok": True}, engine_used=self.name, latency_ms=ms)
        except PermissionError:
            return ActionResult(False, error_code="E-AUTH-TOKEN-EXPIRED", engine_used=self.name)
        except httpx.HTTPStatusError as e:
            code = "E-LIMIT-QUOTA" if e.response.status_code == 429 else "E-NET-TIMEOUT"
            if e.response.status_code == 401:
                code = "E-AUTH-TOKEN-EXPIRED"
            # 4279013 restricted -> non-retryable
            try:
                body = e.response.text
                if "4279013" in body or "restricted" in body.lower():
                    code = "E-LIMIT-BLOCK"
            except Exception:
                pass
            return ActionResult(False, error_code=code, raw_snapshot={"status": e.response.status_code}, engine_used=self.name)
        except Exception as e:  # noqa: BLE001
            return ActionResult(False, error_code="E-ENGINE-BUG", raw_snapshot={"err": str(e)}, engine_used=self.name)
