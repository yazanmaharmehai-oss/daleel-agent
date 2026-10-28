"""Render the short video and the cover image with Remotion (video/src/index.jsx)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .core import SITE, VIDEO, env, log, write_json


def _remotion(args: list[str]) -> None:
    cmd = ["npx", "remotion", *args]
    browser = env("REMOTION_BROWSER")  # local sandbox only; on GitHub Actions Remotion downloads its own
    if browser:
        cmd.append(f"--browser-executable={browser}")
    log.info("render: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=VIDEO, check=True)


def render_video(draft: dict, media_dir: Path, cfg: dict) -> Path:
    audio_rel = f"audio/{draft['id']}"
    audio_dir = VIDEO / "public" / audio_rel
    if audio_dir.exists():
        shutil.rmtree(audio_dir)
    audio_dir.mkdir(parents=True)
    for sc in draft["scenes"]:
        if sc.get("audio"):
            shutil.copy(media_dir / sc["audio"], audio_dir / sc["audio"])

    props = {
        "handle": cfg["brand"]["handle"],
        "audioDir": audio_rel,
        "minSeconds": cfg["video"].get("min_scene_seconds", 2.6),
        "scenes": draft["scenes"],
    }
    props_path = VIDEO / "out" / f"{draft['id']}.json"
    write_json(props_path, props)
    out = media_dir / "video.mp4"
    _remotion(["render", "src/index.jsx", "Promo", str(out), f"--props={props_path}",
               "--concurrency=4", "--crf=20"])
    shutil.rmtree(audio_dir, ignore_errors=True)
    return out


def render_cover(draft: dict, cfg: dict) -> str:
    """Returns the cover path relative to the site root."""
    slug = draft["article"]["slug"]
    rel = f"static/covers/{slug}.jpg"
    props_path = VIDEO / "out" / f"{draft['id']}-cover.json"
    write_json(props_path, {"title": draft["article"]["title"], "productName": draft["product"]["name"],
                            "handle": cfg["brand"]["handle"]})
    (SITE / "static" / "covers").mkdir(parents=True, exist_ok=True)
    _remotion(["still", "src/index.jsx", "Cover", str(SITE / rel), f"--props={props_path}",
               "--image-format=jpeg", "--jpeg-quality=82"])
    return rel
