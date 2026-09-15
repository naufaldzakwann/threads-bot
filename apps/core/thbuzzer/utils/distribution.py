"""Distribusi drip truncated-exponential deterministik + target-side pacing (§11, tasks/distribution.py)."""
from __future__ import annotations

import math
import random


def drip_schedule(n: int, spread_minutes: int, seed: int = 42) -> list[float]:
    """Offset menit untuk n job dalam window spread. Median ~ spread/2. Deterministik via seed."""
    rng = random.Random(seed)
    out: list[float] = []
    for _ in range(n):
        u = rng.random()
        # truncated exponential lambda=2 pada [0,1] lalu skala
        x = -math.log(1 - u * (1 - math.exp(-2))) / 2
        out.append(round(x * spread_minutes, 2))
    return sorted(out)


def pace_target(offsets: list[float], max_per_minute: int) -> list[float]:
    """Enforce max aksi/menit per URL target (§11 Guard). Geser offset yang melanggar."""
    paced: list[float] = []
    bucket: dict[int, int] = {}
    for o in sorted(offsets):
        m = int(o)
        while bucket.get(m, 0) >= max_per_minute:
            m += 1
        bucket[m] = bucket.get(m, 0) + 1
        paced.append(float(m) + (o - int(o)))
    return sorted(paced)
