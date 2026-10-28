"""Shared paths, config, state files and logging."""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
STATE = ROOT / "state"
SITE = ROOT / "site"
VIDEO = ROOT / "video"
CONTENT_DIR = ROOT / "site" / "content"
SKILLS = ROOT / ".claude" / "skills"

log = logging.getLogger("daleel")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def load_products() -> list[dict]:
    data = yaml.safe_load((ROOT / "products.yaml").read_text(encoding="utf-8")) or {}
    return data.get("products") or []


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def skill_text(name: str) -> str:
    """Body of a SKILL.md without its frontmatter, so prompts share one source of truth."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


# --- drafts -----------------------------------------------------------------
# Each draft lives in drafts/<id>/draft.json. Media (mp3/mp4) go to drafts/<id>/media/
# and are not committed; the video reaches the person through Telegram.

def draft_dir(draft_id: str) -> Path:
    return DRAFTS / draft_id


def load_draft(draft_id: str) -> dict:
    return read_json(draft_dir(draft_id) / "draft.json", None)


def save_draft(draft: dict) -> None:
    draft["updated_at"] = now().isoformat()
    write_json(draft_dir(draft["id"]) / "draft.json", draft)


def all_drafts() -> list[dict]:
    out = []
    for p in sorted(DRAFTS.glob("*/draft.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out
