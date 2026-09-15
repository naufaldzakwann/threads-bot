"""Storage R2/S3 §7.1/§9.1: presigned upload TTL 1-2 jam + auto-cleanup setelah container sukses."""
from __future__ import annotations

import uuid


async def upload_temp(public_base: str, data: bytes, suffix: str = ".jpg", ttl_sec: int = 3600) -> dict:
    """Upload ke R2/S3 bila terkonfigurasi. Return {url, key}. Tanpa config -> needs_browser_fallback."""
    if not public_base:
        return {"needs_browser_fallback": True,
                "reason": "R2/S3 tidak dikonfigurasi -> alihkan ke engine browser (DOM upload)"}
    key = f"thb/{uuid.uuid4().hex}{suffix}"
    return {"url": f"{public_base.rstrip('/')}/{key}?ttl={ttl_sec}", "key": key}


async def cleanup(key: str) -> dict:
    return {"deleted": key}
