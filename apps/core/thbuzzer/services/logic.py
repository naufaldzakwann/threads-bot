"""Services: account health (§5.9), proxy, storage R2/S3 presigned, thread guard-dobel, AI stance."""
from __future__ import annotations

import hashlib
import json
import random


def health_score(checkpoint_7h: int, restricted_7h: int, fail_pct: float, streak_days: int) -> int:
    """E-LIMIT-QUOTA/429-kuota TIDAK mengurangi skor (§3.5)."""
    return max(0, min(100, int(round(100 - 15 * checkpoint_7h - 30 * restricted_7h - 2 * fail_pct + min(streak_days, 14)))))


def health_category(score: int) -> str:
    if score >= 80:
        return "sehat"
    if score >= 50:
        return "waspada"
    if score >= 20:
        return "kritis"
    return "bahaya"


# --- proxy utils §06 ---
def parse_proxy(line: str) -> dict:
    line = line.strip()
    if "://" in line:
        proto, rest = line.split("://", 1)
    else:
        proto, rest = "http", line
    parts = rest.split(":")
    if len(parts) == 2:
        host, port = parts
        return {"protocol": proto, "host": host, "port": int(port), "username": "", "password": ""}
    if len(parts) == 4:
        host, port, user, pwd = parts
        return {"protocol": proto, "host": host, "port": int(port), "username": user, "password": pwd}
    raise ValueError(f"format proxy tidak dikenal: {line}")


# --- storage presigned §7.1/§9.1: R2/S3 TTL 1-2 jam + auto-cleanup setelah publish ---
def presigned_url(public_base: str, key: str, ttl_sec: int = 3600) -> str:
    return f"{public_base.rstrip('/')}/{key}?ttl={ttl_sec}"


# --- guard dobel-publish §9.2: cek published_threads_id + hash 6 post terakhir ---
def thread_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def is_duplicate(new_hash: str, recent_hashes: list[str]) -> bool:
    return new_hash in recent_hashes[-6:]


# --- AI stance distribution §13: 60/20/10/10 default, editable per kampanye ---
DEFAULT_STANCE = {"mendukung": 0.6, "kepo": 0.2, "testimonial": 0.1, "reply_komentar_lain": 0.1}


def pick_stance(dist: dict[str, float] | None = None, rng: random.Random | None = None) -> str:
    d = dist or DEFAULT_STANCE
    rng = rng or random.Random()
    r = rng.random()
    acc = 0.0
    for k, v in d.items():
        acc += v
        if r <= acc:
            return k
    return next(iter(d))


def build_campaign_prompt(persona: str, context: str, stance: str, max_chars: int = 500) -> str:
    stance_id = {
        "mendukung": "Mendukung/afirmatif: kuatkan narasi thread.",
        "kepo": "Kepo/bertanya: pancing percakapan lanjutan.",
        "testimonial": "Testimonial: cerita personal singkat nyata.",
        "reply_komentar_lain": "Tanggapi komentar lain di utas.",
    }.get(stance, stance)
    return (f"Persona: {persona}\nKonteks: {context}\nSudut pandang: {stance_id}\n"
            f"Tulis balasan Threads ≤{max_chars} char, tanpa markdown, tanpa URL kecuali diminta.")


# --- warmup 14 hari §5.6 ---
WARMUP_DEFAULT = {
    "days_1_2": "browse 3-8 sesi, view 5-15 thread, tanpa tulis",
    "days_3_5": "+ like 10-20, lengkapi profil sekali",
    "days_6_10": "+ follow 5-10, like 15-30",
    "days_11_14": "+ reply 1-3, repost 1-3",
    "day_15_plus": "naik 25%/hari ke 100% (hari 21 full)",
}


def warmup_day_cap(day: int, base: int) -> int:
    if day <= 0:
        return 0
    if day >= 21:
        return base
    if day >= 15:
        return max(1, int(base * (0.5 + 0.25 * (day - 14) / 7 * 2)))
    return max(1, int(base * 0.3))
