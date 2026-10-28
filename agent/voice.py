"""Arabic voice-over per scene with Edge TTS (free). Falls back to silence if the service is unreachable."""
from __future__ import annotations

import asyncio
from pathlib import Path

from .core import log

TICKS = 10_000_000  # edge-tts offsets are in 100 ns units


async def _speak(text: str, out: Path, voice: str, rate: str) -> list[dict]:
    import edge_tts

    words = []
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    with out.open("wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"text": chunk["text"], "start": chunk["offset"] / TICKS,
                              "end": (chunk["offset"] + chunk["duration"]) / TICKS})
    return words


def _duration(path: Path) -> float:
    from mutagen.mp3 import MP3
    return float(MP3(str(path)).info.length)


def voice_scenes(scenes: list[dict], out_dir: Path, cfg: dict) -> bool:
    """Adds audio, seconds and words to each scene. Returns False if no voice was produced."""
    vc = cfg.get("voice", {})
    if not vc.get("enabled", True):
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        for i, sc in enumerate(scenes):
            mp3 = out_dir / f"s{i + 1}.mp3"
            sc["words"] = asyncio.run(_speak(sc["voice"].replace("[تأكد]", ""), mp3, vc["name"], vc.get("rate", "+0%")))
            sc["audio"] = mp3.name
            sc["seconds"] = round(_duration(mp3), 2)
        return True
    except Exception as e:  # noqa: BLE001 - silent video is better than no video
        log.warning("voice failed, rendering silent video: %s", e)
        for sc in scenes:
            sc.pop("audio", None)
            sc.pop("words", None)
            sc.pop("seconds", None)
        return False
