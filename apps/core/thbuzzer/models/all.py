"""Skema DB §15. Konvensi: INTEGER PK, unixepoch UTC, bool 0/1, JSON TEXT, _enc ciphertext."""
from __future__ import annotations

import time

from sqlalchemy import BigInteger, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from thbuzzer.db.base import Base


def now() -> int:
    return int(time.time())


class SettingsKV(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class AccountGroup(Base):
    __tablename__ = "account_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, unique=True)  # Threads handle, unik case-insensitive (app layer)
    password_enc: Mapped[str] = mapped_column(Text, default="")
    email: Mapped[str] = mapped_column(Text, default="")
    email_password_enc: Mapped[str] = mapped_column(Text, default="")
    imap_host: Mapped[str] = mapped_column(Text, default="")
    totp_secret_enc: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="new")
    needs_password: Mapped[int] = mapped_column(Integer, default=0)
    needs_reauth: Mapped[int] = mapped_column(Integer, default=0)
    health_score: Mapped[int] = mapped_column(Integer, default=100)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    priority: Mapped[str] = mapped_column(Text, default="normal")
    timezone: Mapped[str] = mapped_column(Text, default="Asia/Jakarta")
    locale: Mapped[str] = mapped_column(Text, default="id")
    country: Mapped[str] = mapped_column(Text, default="ID")
    device_params_json: Mapped[str] = mapped_column(Text, default="{}")
    session_blob_enc: Mapped[str] = mapped_column(Text, default="")
    storage_state_enc: Mapped[str] = mapped_column(Text, default="")
    threads_user_id: Mapped[str] = mapped_column(Text, default="")
    oauth_token_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_engine: Mapped[str] = mapped_column(Text, default="browser")
    account_tier: Mapped[str] = mapped_column(Text, default="buzzer_satellite")
    account_role: Mapped[str] = mapped_column(Text, default="actor")
    daily_limit_overrides_json: Mapped[str] = mapped_column(Text, default="{}")
    warmup_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proxy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now)
    deleted: Mapped[int] = mapped_column(Integer, default=0)


class AccountTag(Base):
    __tablename__ = "account_tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    tag: Mapped[str] = mapped_column(Text)


class AccountStatusHistory(Base):
    __tablename__ = "account_status_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    old_status: Mapped[str] = mapped_column(Text, default="")
    new_status: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class AccountStatsSnapshot(Base):
    __tablename__ = "account_stats_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    followers: Mapped[int] = mapped_column(Integer, default=0)
    following: Mapped[int] = mapped_column(Integer, default=0)
    thread_count: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    reposts: Mapped[int] = mapped_column(Integer, default=0)
    quotes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class WarmupPlan(Base):
    __tablename__ = "warmup_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, default="default-14d")
    spec_json: Mapped[str] = mapped_column(Text, default="{}")


class Proxy(Base):
    __tablename__ = "proxies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol: Mapped[str] = mapped_column(Text, default="http")
    host: Mapped[str] = mapped_column(Text)
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(Text, default="")
    password_enc: Mapped[str] = mapped_column(Text, default="")
    country: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="alive")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cooling_down: Mapped[int] = mapped_column(Integer, default=0)
    rotation_url: Mapped[str] = mapped_column(Text, default="")
    last_rotated_at: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class ThreadsToken(Base):
    __tablename__ = "threads_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    app_id: Mapped[str] = mapped_column(Text, default="")
    scopes_json: Mapped[str] = mapped_column(Text, default="[]")
    access_token_enc: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[int] = mapped_column(BigInteger, default=0)
    last_refreshed_at: Mapped[int] = mapped_column(BigInteger, default=0)


class MediaItem(Base):
    __tablename__ = "media_library"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(Text, default="image")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[float] = mapped_column(Float, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class ScheduledThread(Base):
    __tablename__ = "scheduled_threads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    text_rendered: Mapped[str] = mapped_column(Text, default="")
    topic_tag: Mapped[str] = mapped_column(Text, default="")
    reply_control: Mapped[str] = mapped_column(Text, default="everyone")
    link_urls_json: Mapped[str] = mapped_column(Text, default="[]")
    media_json: Mapped[str] = mapped_column(Text, default="[]")
    container_id: Mapped[str] = mapped_column(Text, default="")
    published_threads_id: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="scheduled")
    scheduled_at: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text)  # growth kind
    account_filter_json: Mapped[str] = mapped_column(Text, default="{}")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(Text, default="draft")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class ActivityCursor(Base):
    __tablename__ = "activity_cursors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    cursor: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now)


class Interaction(Base):
    __tablename__ = "interactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Text)  # like/follow/unfollow/reply/repost/quote
    target: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="done")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, default="")
    targets_json: Mapped[str] = mapped_column(Text, default="[]")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    participants_json: Mapped[str] = mapped_column(Text, default="{}")
    max_target_actions_per_minute: Mapped[int] = mapped_column(Integer, default=4)
    stance_distribution_json: Mapped[str] = mapped_column(Text, default="{}")
    schedule_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(Text, default="draft")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class CampaignParticipant(Base):
    __tablename__ = "campaign_participants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="pending")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")


class ThreadConversation(Base):
    __tablename__ = "thread_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    thread_id: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(Text, default="threads_reply")
    unread: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now)


class ThreadMessage(Base):
    __tablename__ = "thread_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(Integer)
    author: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    is_hidden_by_platform: Mapped[int] = mapped_column(Integer, default=0)
    last_visibility_checked_at: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class ReplyRule(Base):
    __tablename__ = "reply_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(Text, default="keyword")
    pattern: Mapped[str] = mapped_column(Text, default="")
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[int] = mapped_column(Integer, default=1)


class ReplyCampaign(Base):
    __tablename__ = "reply_campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, default="")
    source_json: Mapped[str] = mapped_column(Text, default="{}")
    template: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="draft")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(Text)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[str] = mapped_column(Text, default="normal")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    engine_hint: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="scheduled")
    scheduled_at: Mapped[int] = mapped_column(BigInteger, default=now)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    dedup_key: Mapped[str] = mapped_column(Text, default="")
    idempotency: Mapped[str] = mapped_column(Text, default="safe")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer)
    success: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class RecurringJob(Base):
    __tablename__ = "recurring_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    cron_note: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[int] = mapped_column(Integer, default=1)


class QuotaUsage(Base):
    __tablename__ = "quota_usage"
    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[str] = mapped_column(Text, primary_key=True)
    posts: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    deletes: Mapped[int] = mapped_column(Integer, default=0)
    searches: Mapped[int] = mapped_column(Integer, default=0)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class AlertHistory(Base):
    __tablename__ = "alerts_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class AIProfile(Base):
    __tablename__ = "ai_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, default="default")
    base_url: Mapped[str] = mapped_column(Text, default="https://api.openai.com/v1")
    model: Mapped[str] = mapped_column(Text, default="gpt-4o-mini")
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    rpm: Mapped[int] = mapped_column(Integer, default=60)
    daily_budget: Mapped[float] = mapped_column(Float, default=5.0)


class AIUsage(Base):
    __tablename__ = "ai_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    day: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class Persona(Base):
    __tablename__ = "personas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(Text, default="")
    spec_json: Mapped[str] = mapped_column(Text, default="{}")


class CheckpointEvent(Base):
    __tablename__ = "checkpoint_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text, default="checkpoint")
    status: Mapped[str] = mapped_column(Text, default="open")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now)


class TopicSet(Base):
    __tablename__ = "topic_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, default="")
    items_json: Mapped[str] = mapped_column(Text, default="[]")
