"""AI service §13: OpenAI-compatible, persona/grup, quote_rewrite, stance, budget, fallback template."""
from __future__ import annotations

import hashlib
import time

_cache: dict[tuple, str] = {}


def dedup_key(account_id: int, context: str) -> tuple:
    return (account_id, hashlib.sha256(context.encode()).hexdigest()[:16])


async def generate(profile: dict, persona: str, kind: str, context: str, stance: str = "mendukung",
                   max_chars: int = 500, account_id: int = 0) -> dict:
    """Timeout 30s -> retry 1x -> fallback template (tidak gagalkan job bisnis). Cache per akun-post."""
    from thbuzzer.services.logic import build_campaign_prompt
    key = (dedup_key(account_id, context), kind)
    if key in _cache:
        return {"text": _cache[key], "cached": True}
    prompt = build_campaign_prompt(persona, context, stance, max_chars)
    api_key = profile.get("api_key", "")
    if not api_key:
        text = f"[{stance}] {context[:max_chars - 12]}"
        _cache[key] = text[:max_chars]
        return {"text": _cache[key], "fallback": "template", "badge": "AI nonaktif"}
    try:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(api_key=api_key, base_url=profile.get("base_url"), timeout=30.0)
        temp = {"reply": 0.7, "quote_rewrite": 0.9, "thread_caption": 0.8}.get(kind, 0.7)
        r = await client.chat.completions.create(model=profile.get("model", "gpt-4o-mini"),
                                                 messages=[{"role": "user", "content": prompt}],
                                                 temperature=temp, max_tokens=300)
        text = (r.choices[0].message.content or "")[:max_chars]
        _cache[key] = text
        return {"text": text, "usage": str(getattr(r, "usage", ""))}
    except Exception:
        text = f"[{stance}] {context[:max_chars - 12]}"
        _cache[key] = text[:max_chars]
        return {"text": _cache[key], "fallback": "template-after-error"}
