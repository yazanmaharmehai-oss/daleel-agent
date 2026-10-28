"""Telegram bot: sends each draft for approval and reads the buttons the person pressed."""
from __future__ import annotations

from pathlib import Path

import requests

from .core import STATE, env, log, read_json, write_json

API = "https://api.telegram.org/bot{token}/{method}"
OFFSET_FILE = STATE / "telegram.json"


def enabled() -> bool:
    return bool(env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID"))


def _call(method: str, files=None, **params):
    r = requests.post(API.format(token=env("TELEGRAM_BOT_TOKEN"), method=method), data=params if files else None,
                      json=None if files else params, files=files, timeout=120)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"telegram {method}: {data.get('description')}")
    return data["result"]


def send(text: str, buttons: list[list[tuple[str, str]]] | None = None, reply_to: int | None = None,
         force_reply: bool = False) -> int:
    if not enabled():
        log.info("telegram off, message:\n%s", text)
        return 0
    params = {"chat_id": env("TELEGRAM_CHAT_ID"), "text": text[:4096], "disable_web_page_preview": True}
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
    elif force_reply:
        params["reply_markup"] = {"force_reply": True}
    if reply_to:
        params["reply_parameters"] = {"message_id": reply_to}
    return _call("sendMessage", **params)["message_id"]


def send_video(path: Path, caption: str) -> None:
    if not enabled():
        return
    if path.stat().st_size > 49 * 1024 * 1024:
        send("الفيديو أكبر من 50MB وما بقدر أبعته على تيليغرام. نزّله من GitHub Actions (Artifacts).")
        return
    with path.open("rb") as f:
        _call("sendVideo", files={"video": f}, chat_id=env("TELEGRAM_CHAT_ID"), caption=caption[:1024],
              supports_streaming="true", width="1080", height="1920")


def send_photo(path: Path, caption: str) -> None:
    if not enabled():
        return
    with path.open("rb") as f:
        _call("sendPhoto", files={"photo": f}, chat_id=env("TELEGRAM_CHAT_ID"), caption=caption[:1024])


def answer(callback_id: str, text: str = "") -> None:
    try:
        _call("answerCallbackQuery", callback_query_id=callback_id, text=text)
    except RuntimeError as e:  # old callbacks expire; nothing to do
        log.info("answerCallbackQuery: %s", e)


def updates() -> list[dict]:
    """New button presses and replies from the owner chat only. Advances the stored offset."""
    if not enabled():
        return []
    state = read_json(OFFSET_FILE, {"offset": 0})
    res = _call("getUpdates", offset=state["offset"], timeout=0, allowed_updates=["message", "callback_query"])
    owner = str(env("TELEGRAM_CHAT_ID"))
    out = []
    for u in res:
        state["offset"] = u["update_id"] + 1
        msg = u.get("message") or (u.get("callback_query") or {}).get("message") or {}
        if str(msg.get("chat", {}).get("id")) != owner:
            continue  # ignore anyone else who finds the bot
        out.append(u)
    write_json(OFFSET_FILE, state)
    return out
