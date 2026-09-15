"""Validator input pusat (§23 konservatif): URL wajib Threads, angka wajib masuk akal.

Semua pesan Bahasa Indonesia, format: "<kolom> tidak valid: <alasan>".
Dipakai backend (422) dan dicerminkan di form UI.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from fastapi import HTTPException

THREADS_HOSTS = {"threads.com", "www.threads.com", "threads.net", "www.threads.net"}
# Path post Threads: /@user/post/ID atau /t/ID
POST_PATH = re.compile(r"(/post/|/t/)", re.IGNORECASE)
QUIET_RE = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")


class Invalid(ValueError):
    pass


def fail(msg: str) -> HTTPException:
    return HTTPException(422, msg)


def threads_url(value: object, field: str = "URL") -> str:
    """Wajib link Threads (threads.com / threads.net) menunjuk post. Return URL ternormalisasi."""
    s = str(value or "").strip()
    if not s:
        raise Invalid(f"{field} tidak valid: wajib diisi link Threads (contoh https://www.threads.com/@akun/post/ABC)")
    if "://" not in s:
        s = "https://" + s
    try:
        u = urlparse(s)
    except Exception:
        raise Invalid(f"{field} tidak valid: '{value}' bukan URL") from None
    if u.scheme not in ("http", "https") or not u.netloc:
        raise Invalid(f"{field} tidak valid: '{value}' bukan URL")
    if u.netloc.lower() not in THREADS_HOSTS:
        raise Invalid(f"{field} tidak valid: '{value}' bukan link Threads — harus dari threads.com/threads.net")
    if not POST_PATH.search(u.path or ""):
        raise Invalid(f"{field} tidak valid: '{value}' bukan link postingan Threads (/…/post/…)")
    return s


def http_url(value: object, field: str = "URL") -> str:
    s = str(value or "").strip()
    if not s:
        raise Invalid(f"{field} tidak valid: wajib diisi URL http(s)")
    if "://" not in s:
        s = "https://" + s
    try:
        u = urlparse(s)
    except Exception:
        raise Invalid(f"{field} tidak valid: '{value}' bukan URL") from None
    if u.scheme not in ("http", "https") or not u.netloc or "." not in u.netloc:
        raise Invalid(f"{field} tidak valid: '{value}' bukan URL http(s)")
    return s


def thread_target(value: object, field: str = "target") -> str:
    """Target reply: boleh ID post ATAU link — tapi bila link, wajib link Threads."""
    s = str(value or "").strip()
    if not s:
        raise Invalid(f"{field} tidak valid: wajib diisi ID postingan atau link Threads")
    if "://" in s or s.lower().startswith("threads."):
        return threads_url(s, field)
    if len(s) > 300:
        raise Invalid(f"{field} tidak valid: terlalu panjang")
    return s


def pos_int(value: object, field: str, min: int = 1, max: int | None = None) -> int:
    """Angka bulat masuk akal: tolak non-angka, pecahan, bool, negatif/nol (default min 1)."""
    if isinstance(value, bool):
        raise Invalid(f"{field} tidak valid: harus angka bulat")
    if isinstance(value, float):
        if not value.is_integer():
            raise Invalid(f"{field} tidak valid: '{value}' bukan angka bulat")
        value = int(value)
    if isinstance(value, int):
        n = value
    elif isinstance(value, str):
        s = value.strip()
        if not re.fullmatch(r"-?\d+", s):
            raise Invalid(f"{field} tidak valid: '{value}' bukan angka")
        n = int(s)
    else:
        raise Invalid(f"{field} tidak valid: harus angka")
    if n < min:
        raise Invalid(f"{field} tidak valid: minimal {min} (diterima {n})")
    if max is not None and n > max:
        raise Invalid(f"{field} tidak valid: maksimal {max} (diterima {n})")
    return n


def int_list(values: object, field: str, min: int = 1, max: int | None = None, allow_empty: bool = False) -> list[int]:
    if not isinstance(values, (list, tuple)):
        raise Invalid(f"{field} tidak valid: harus daftar angka")
    out = [pos_int(v, field, min, max) for v in values]
    if not out and not allow_empty:
        raise Invalid(f"{field} tidak valid: minimal 1 item")
    return out


def non_empty(value: object, field: str, max_len: int = 200) -> str:
    s = str(value or "").strip()
    if not s:
        raise Invalid(f"{field} tidak valid: wajib diisi")
    if len(s) > max_len:
        raise Invalid(f"{field} tidak valid: maksimal {max_len} karakter")
    return s


def one_of(value: object, field: str, allowed: set[str]) -> str:
    s = str(value or "")
    if s not in allowed:
        raise Invalid(f"{field} tidak valid: '{s}' — pilihan: {', '.join(sorted(allowed))}")
    return s
