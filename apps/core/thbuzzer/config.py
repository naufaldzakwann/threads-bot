"""Konfigurasi global THBuzzer (§03, §15, §19, §20). Bahasa kode English, string UI via i18n."""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def app_data_dir() -> Path:
    """%APPDATA%/THBuzzer di Windows, ~/.thbuzzer di dev non-Windows. Hormati portable.flag."""
    base = Path(__file__).resolve()
    # apps/core/thbuzzer/config.py -> repo root = parents[3]
    try:
        root = base.parents[3]
    except IndexError:
        root = Path.cwd()
    if (root / "portable.flag").exists():
        return root / "data"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "THBuzzer"
    return Path.home() / ".thbuzzer"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="THBUZZER_", extra="ignore")

    app_name: str = "THBuzzer"
    version: str = "0.1.0"
    data_dir: Path = Field(default_factory=app_data_dir)
    timezone_default: str = "Asia/Jakarta"
    locale_default: str = "id"

    # Concurrency (§3.3)
    max_concurrent_actions: int = Field(default=64, ge=8, le=512)
    browser_max_contexts: int = Field(default=4, ge=1, le=16)
    per_ip_per_min: int = 6
    global_per_min: int = 120
    reply_poll_minutes: int = 15
    reply_poll_priority_minutes: int = 5

    # Velocity §19.5 (AWAL, dewasa/hari). TIDAK BOLEH copy angka IG. Tidak bisa dimatikan.
    vel_thread_text_safe: int = 5
    vel_thread_text_max: int = 10
    vel_thread_media_safe: int = 3
    vel_thread_media_max: int = 8
    vel_reply_safe: int = 10
    vel_reply_max: int = 20
    vel_repost_safe: int = 10
    vel_repost_max: int = 20
    vel_quote_safe: int = 5
    vel_quote_max: int = 10
    vel_like_safe: int = 50
    vel_like_max: int = 100
    vel_follow_safe: int = 20
    vel_follow_max: int = 50
    vel_unfollow_safe: int = 15
    vel_unfollow_max: int = 30
    delay_min_sec: int = 60
    delay_max_sec: int = 240
    break_every_min: int = 15
    break_every_max: int = 30
    break_minutes_min: int = 15
    break_minutes_max: int = 45
    target_max_actions_per_minute: int = Field(default=4, ge=1, le=6)

    # Official API quotas (runtime config, jangan hard-code di logika — §1.6 D10)
    quota_posts_24h: int = 250
    quota_replies_24h: int = 1000
    quota_deletes_24h: int = 100
    quota_search_7d: int = 500

    # Storage R2/S3 opsional (§7.1)
    storage_provider: str = ""  # "" | "r2" | "s3"
    storage_bucket: str = ""
    storage_endpoint: str = ""
    storage_public_base_url: str = ""
    official_via_proxy: bool = False

    # AI
    llm_rpm_default: int = 60

    # Security
    pin_enabled: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "db" / "thbuzzer.db"

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"

    def ensure_dirs(self) -> None:
        for sub in ["db", "sessions", "media/library", "logs/screenshots", "backups", "config"]:
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
