"""Arabic voice-over per scene: Google Gemini voice (clearer) or Edge TTS (free, no key). Falls back to silence."""
from __future__ import annotations

import asyncio
import wave
from pathlib import Path

from .core import env, log

TICKS = 10_000_000  # edge-tts offsets are in 100 ns units
RATE = 24_000  # Gemini returns 24 kHz mono 16-bit PCM


async def _edge(text: str, out: Path, voice: str, rate: str) -> list[dict]:
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


def _mp3_seconds(path: Path) -> float:
    from mutagen.mp3 import MP3
    return float(MP3(str(path)).info.length)


def edge_say(text: str, out: Path, voice: str, rate: str) -> tuple[list[dict], float]:
    words = asyncio.run(_edge(text, out, voice, rate))
    return words, round(_mp3_seconds(out), 2)


def gemini_say(text: str, out: Path, vc: dict) -> float:
    from . import llm

    pcm = llm.gemini_speech(text, vc.get("gemini_voice", "Charon"), vc.get("gemini_style", ""), vc["gemini_models"])
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return round(len(pcm) / (RATE * 2), 2)


def _clean(text: str) -> str:
    return text.replace("[تأكد]", "").replace("[[", "").replace("]]", "").strip()


def voice_scenes(scenes: list[dict], out_dir: Path, cfg: dict) -> str:
    """Adds audio, seconds and words to each scene. Returns the engine used, or "" for a silent video."""
    vc = cfg.get("voice", {})
    if not vc.get("enabled", True):
        return ""
    out_dir.mkdir(parents=True, exist_ok=True)
    engines = ["gemini", "edge"] if vc.get("engine") == "gemini" and env("GEMINI_API_KEY") else ["edge"]
    for engine in engines:
        try:
            for i, sc in enumerate(scenes):
                text = _clean(sc["voice"])
                if engine == "gemini":
                    path = out_dir / f"s{i + 1}.wav"
                    sc["seconds"] = gemini_say(text, path, vc)
                    sc["words"] = []  # no word timings: captions are spread evenly
                else:
                    path = out_dir / f"s{i + 1}.mp3"
                    sc["words"], sc["seconds"] = edge_say(text, path, vc["name"], vc.get("rate", "+0%"))
                sc["audio"] = path.name
            return engine
        except Exception as e:  # noqa: BLE001 - try the next engine, silent video is the last resort
            log.warning("%s voice failed: %s", engine, str(e)[:300])
            for sc in scenes:
                for k in ("audio", "words", "seconds"):
                    sc.pop(k, None)
    return ""
