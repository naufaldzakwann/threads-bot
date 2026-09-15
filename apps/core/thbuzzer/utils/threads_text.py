"""Spintax + validator Threads §9.1 + topic sanitizer + threadstorm splitter."""
from __future__ import annotations

import random
import re

URL_RE = re.compile(r"https?://\S+")
TAG_CLEAN = re.compile(r"[^A-Za-z0-9_]")
REPLY_CONTROLS = {"everyone", "accounts_you_follow", "mentioned_only", "parent_post_author_only", "followers_only"}


def render_spintax(template: str, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    pat = re.compile(r"\{([^{}]*)\}")

    def repl(m: re.Match) -> str:
        return rng.choice(m.group(1).split("|"))

    prev = None
    out = template
    while prev != out:
        prev = out
        out = pat.sub(repl, out)
    return out


def count_links(text: str) -> int:
    return len(URL_RE.findall(text))


def sanitize_topic_tag(raw: str) -> str:
    """Ambil 1 topic_tag resmi: hashtag pertama -> tag, sisanya jadi teks biasa (§9.1)."""
    tags = re.findall(r"#(\S+)", raw)
    first = TAG_CLEAN.sub("", tags[0])[:50] if tags else ""
    return first


def strip_extra_hashes(text: str) -> str:
    return text.replace("#", "")


def validate_thread(text: str, topic_tag: str = "", reply_control: str = "everyone", links_extra: int = 0) -> list[str]:
    errs: list[str] = []
    if len(text) > 500:
        errs.append("E-VALID-TEXT-LIMIT: teks >500 char")
    if count_links(text) + links_extra > 5:
        errs.append("E-VALID-LINK-LIMIT: maks 5 link/post")
    if topic_tag and (len(topic_tag) > 50 or "." in topic_tag or "&" in topic_tag):
        errs.append("E-VALID-TOPIC-TAG: 1-50 char tanpa ./&")
    if reply_control not in REPLY_CONTROLS:
        errs.append("E-VALID-REPLY-CONTROL: nilai tidak dikenal")
    return errs


def split_threadstorm(long_text: str, limit: int = 500) -> list[str]:
    """Pecah per 500 char, prioritas potong antar-kalimat (format Ayrshare)."""
    import re as _re

    sentences = _re.split(r"(?<=[.!?])\s+", long_text.strip())
    parts: list[str] = []
    cur = ""
    for s in sentences:
        if not s:
            continue
        if len(s) > limit:  # potong antar-kata
            if cur:
                parts.append(cur)
                cur = ""
            words = s.split(" ")
            chunk = ""
            for w in words:
                if len(chunk) + len(w) + 1 > limit:
                    parts.append(chunk)
                    chunk = w
                else:
                    chunk = (chunk + " " + w).strip()
            if chunk:
                parts.append(chunk)
        elif len(cur) + len(s) + 1 > limit:
            parts.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        parts.append(cur)
    return parts or [""]
