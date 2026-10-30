"""Which AI writes: Gemini (free tier, default) or Claude (paid, better). Plus Gemini voice."""
from __future__ import annotations

import time

from .core import env, log


def provider(cfg: dict) -> str:
    """config ai.provider: "auto" picks Claude when its key exists, else Gemini."""
    p = cfg["ai"].get("provider", "auto")
    if p == "auto":
        return "claude" if env("ANTHROPIC_API_KEY") else "gemini"
    return p


def has_key(cfg: dict) -> bool:
    return bool(env("ANTHROPIC_API_KEY") if provider(cfg) == "claude" else env("GEMINI_API_KEY"))


def _gemini():
    from google import genai
    return genai.Client(api_key=env("GEMINI_API_KEY"))


def _transient(e: Exception) -> bool:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    return code in (429, 500, 503) or "RESOURCE_EXHAUSTED" in str(e) or "UNAVAILABLE" in str(e)


def _try_models(models: list[str], call):
    """Free-tier model names change; try each in order, retrying short rate limits."""
    last = None
    for model in models:
        for attempt in range(3):
            try:
                return model, call(model)
            except Exception as e:  # noqa: BLE001 - provider errors vary by SDK version
                last = e
                if _transient(e) and attempt < 2:
                    wait = 20 * (attempt + 1)
                    log.warning("%s busy (%s), retrying in %ss", model, str(e)[:120], wait)
                    time.sleep(wait)
                    continue
                log.warning("%s failed: %s", model, str(e)[:300])
                break
    raise RuntimeError(f"all Gemini models failed: {last}")


def gemini_json(system: str, user: str, schema, cfg: dict) -> dict:
    from google.genai import types

    client = _gemini()

    def call(model):
        resp = client.models.generate_content(
            model=model, contents=user,
            config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                               response_schema=schema),
        )
        parsed = resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate_json(resp.text)
        return parsed, resp.usage_metadata

    model, (parsed, usage) = _try_models(cfg["ai"]["gemini_models"], call)
    log.info("gemini model=%s usage=%s", model, usage)
    out = parsed.model_dump()
    out["model"] = model
    return out


def ask_text(prompt: str, cfg: dict) -> str:
    if provider(cfg) == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
        resp = client.messages.create(model=cfg["ai"]["claude_model"], max_tokens=4000,
                                      messages=[{"role": "user", "content": prompt}])
        return next((b.text for b in resp.content if b.type == "text"), "")
    client = _gemini()
    _, text = _try_models(cfg["ai"]["gemini_models"],
                          lambda m: client.models.generate_content(model=m, contents=prompt).text)
    return text or ""


def gemini_speech(text: str, voice: str, style: str, models: list[str]) -> bytes:
    """Returns raw 24 kHz mono 16-bit PCM."""
    from google.genai import types

    client = _gemini()

    def call(model):
        resp = client.models.generate_content(
            model=model, contents=f"{style}: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))),
            ),
        )
        return resp.candidates[0].content.parts[0].inline_data.data

    _, pcm = _try_models(models, call)
    return pcm
