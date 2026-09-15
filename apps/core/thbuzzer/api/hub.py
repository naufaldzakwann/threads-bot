"""WS hub (§16): job.updated, activity.created, account.status_changed, reply.new_message,
campaign.progress, import.progress, alert.raised, system.stats, thread.updated."""
from __future__ import annotations

from fastapi import WebSocket

WS_CLIENTS: set[WebSocket] = set()


async def broadcast(event: str, payload: dict) -> None:
    dead = []
    for ws in list(WS_CLIENTS):
        try:
            await ws.send_json({"event": event, **payload})
        except Exception:
            dead.append(ws)
    for ws in dead:
        WS_CLIENTS.discard(ws)
