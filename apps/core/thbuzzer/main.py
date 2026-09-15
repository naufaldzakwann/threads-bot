"""FastAPI app + handshake THBUZZER_READY (§3.1). 127.0.0.1 saja, 1 worker."""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import socket
import sys

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import text

from thbuzzer import HANDSHAKE, __version__
from thbuzzer.api.hub import WS_CLIENTS, broadcast  # noqa: F401  (dipakai router via hub)
from thbuzzer.api.routers import (accounts, activities, ai, alerts, analytics, campaigns,
                                  engines, proxies, replies, settings, system, threads_posts)
from thbuzzer.config import get_settings
from thbuzzer.db.base import PRAGMAS, Base, create_engine, session_factory

SESSION_TOKEN = secrets.token_hex(32)
CORE_PORT = 0  # diisi main() sebelum uvicorn jalan


def _write_connection_file() -> None:
    """Auto-connect dev: tulis port+token agar UI tersambung tanpa input manual."""
    import os
    if CORE_PORT == 0 or os.environ.get("THBUZZER_NO_WORKER") == "1":
        return  # jangan timpa connection.json dev saat test
    try:
        from pathlib import Path
        ui_public = Path(__file__).resolve().parents[3] / "apps" / "ui" / "public"
        ui_public.mkdir(parents=True, exist_ok=True)
        (ui_public / "connection.json").write_text(
            json.dumps({"base": f"http://127.0.0.1:{CORE_PORT}", "token": SESSION_TOKEN}))
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="THBuzzer", version=__version__)
    # UI dev (5173) panggil core lintas-port -> izinkan origin localhost saja.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_local(request, call_next):
        if request.method == "OPTIONS":  # preflight CORS tanpa Authorization
            return await call_next(request)
        if request.url.path in ("/healthz", "/openapi.json", "/docs"):
            return await call_next(request)
        if request.url.path == "/ws":
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {SESSION_TOKEN}" and request.url.path != "/":
            return JSONResponse({"error": {"code": "E-AUTH", "message": "unauthorized"}}, status_code=401)
        return await call_next(request)

    for r in (system, accounts, proxies, engines, activities,
              threads_posts, replies, campaigns, analytics,
              alerts, ai, settings):
        app.include_router(r)

    @app.get("/")
    async def root():
        return {"app": "THBuzzer", "version": __version__}

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(ws: WebSocket):
        await ws.accept()
        WS_CLIENTS.add(ws)
        try:
            while True:
                await ws.receive_text()
        except Exception:
            WS_CLIENTS.discard(ws)

    @app.on_event("startup")
    async def startup():
        s = get_settings()
        s.ensure_dirs()
        eng = create_engine(s.db_url)
        async with eng.connect() as conn:
            for p in PRAGMAS:
                await conn.execute(text(p))
            await conn.run_sync(Base.metadata.create_all)  # dev-bootstrap; prod via Alembic §3.6
            await conn.commit()
        app.state.engine = eng
        app.state.sessions = session_factory(eng)
        from thbuzzer.tasks import recurring, worker
        await recurring.seed(app.state.sessions)
        _write_connection_file()
        if __import__("os").environ.get("THBUZZER_NO_WORKER") != "1":
            app.state.worker_task = asyncio.create_task(worker.run_forever(app.state.sessions))
            app.state.recurring_task = asyncio.create_task(recurring.run_forever(app.state.sessions))
        logger.info("THBuzzer core started, db={}", s.db_path)

    @app.on_event("shutdown")
    async def shutdown():
        for t in (getattr(app.state, "worker_task", None), getattr(app.state, "recurring_task", None)):
            if t:
                t.cancel()

    return app


app = create_app()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args()
    with socket.socket() as so:
        so.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        so.bind(("127.0.0.1", args.port or 0))
        port = so.getsockname()[1]
    global CORE_PORT
    CORE_PORT = port
    import uvicorn

    print(json.dumps({"_handshake": HANDSHAKE, "port": port, "token": SESSION_TOKEN,
                      "pid": __import__("os").getpid(), "version": __version__}), flush=True)
    # Baris handshake murni (Electron memindai THBUZZER_READY):
    sys.stdout.write(f'{HANDSHAKE} {json.dumps({"port": port, "token": SESSION_TOKEN, "pid": __import__("os").getpid(), "version": __version__})}\n')
    sys.stdout.flush()
    uvicorn.run(app, host="127.0.0.1", port=port, workers=1, log_level="warning")


if __name__ == "__main__":
    main()
