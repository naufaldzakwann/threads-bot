"""Router §7.4 berbasis Tier & Job Type. Override job > override akun > hard rules.

- brand_official: publish/reply/quote/repost/delete/insight -> official_api
  (media lokal tanpa R2 -> browser). search hemat -> official_api.
- buzzer_satellite: like/follow/unfollow/reply/repost/quote/publish -> browser
  (atau private_unofficial bila sehat). DILARANG pakai App ID operator.
- search luas/scraping -> HANYA role scout.
- dm_* -> E-VALID-UNSUPPORTED ("gunakan Replies §10").
- resolve_checkpoint / login gagal checkpoint -> browser.
"""
from __future__ import annotations

OFFICIAL_ACTIONS = {"publish_thread", "publish_carousel", "publish_video", "reply", "first_reply",
                    "quote", "repost", "delete_thread", "hide_reply", "insight", "poll_replies", "snapshot"}
BUZZER_GROWTH = {"like", "follow", "unfollow", "reply", "repost", "quote", "publish_thread"}
SCOUT_ONLY = {"keyword_search", "scrape_followers", "scrape_likers"}


def route(action: str, tier: str, role: str, job_hint: str = "", account_engine: str = "",
          private_healthy: bool = False, media_local_no_cloud: bool = False) -> tuple[str, str]:
    """Return (engine, error). error non-empty berarti tolak validasi."""
    if action.startswith("dm_"):
        return "", "E-VALID-UNSUPPORTED: gunakan Replies (§10), Threads tidak punya DM via API"
    if job_hint:
        return job_hint, ""
    if action == "resolve_checkpoint":
        return "browser", ""
    if action in SCOUT_ONLY and role != "scout":
        return "", "E-VALID-SCOUT-ONLY: search/scraping hanya role scout (hemat jatah 500/minggu)"
    if tier == "brand_official":
        if action in OFFICIAL_ACTIONS:
            if media_local_no_cloud and action in ("publish_thread", "publish_carousel", "publish_video"):
                return "browser", ""
            return "official_api", ""
        return "official_api", ""
    # buzzer_satellite default browser; private bila sehat & diminta akun
    if account_engine == "private_unofficial" and private_healthy:
        return "private_unofficial", ""
    return "browser", ""
