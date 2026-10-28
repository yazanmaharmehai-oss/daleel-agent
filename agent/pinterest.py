"""Optional: create a Pinterest pin for each published article (API v5)."""
from __future__ import annotations

import requests

from .core import env, log


def enabled(cfg: dict) -> bool:
    return bool(cfg.get("pinterest", {}).get("enabled") and env("PINTEREST_TOKEN") and cfg["pinterest"].get("board_id"))


def pin(cfg: dict, draft: dict, article_url: str, image_url: str) -> None:
    if not enabled(cfg):
        return
    post = draft["post"]
    r = requests.post("https://api.pinterest.com/v5/pins", timeout=60,
                      headers={"Authorization": f"Bearer {env('PINTEREST_TOKEN')}"},
                      json={"board_id": cfg["pinterest"]["board_id"], "title": post["pinterest_title"][:100],
                            "description": (post["pinterest_description"] + " #إعلان")[:500], "link": article_url,
                            "media_source": {"source_type": "image_url", "url": image_url}})
    if r.status_code >= 300:
        log.warning("pinterest failed %s: %s", r.status_code, r.text[:300])
