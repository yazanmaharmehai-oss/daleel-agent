# daleel-agent

Affiliate-marketing agent for an Arabic brand page ("دليل الذكي", @daleel.ai). Owner: Yazan, Jordan, complete beginner; reply to them in simple Levantine Arabic, blunt, no flattery.

## Architecture
- `python -m agent daily`: pick product (products.yaml) → Tavily research → structured draft (`agent/writer.py`, pydantic `Draft`; `agent/llm.py` picks Gemini free tier by default, Claude when ANTHROPIC_API_KEY exists) → voice per scene (Gemini TTS, fallback Edge TTS) → Remotion render (`video/src/index.jsx`, composition `Promo`, props from the draft) + `Cover` still → Telegram approval buttons → the same job long-polls Telegram for `approval_wait_minutes` (GitHub delays cron by hours) and dispatches approvals.yml to deploy.
- `python -m agent approvals`: reads Telegram updates (owner chat only), approve → `site/content/<slug>.json`; edit → re-dispatches daily.yml with feedback.
- `python -m agent build`: static RTL site in `site/_build` (GitHub Pages via approvals.yml).
- State is committed to git (`state/`, `drafts/*/draft.json`, `site/content/`). Media (`drafts/*/media/`) is not; videos reach the owner via Telegram and Actions artifacts.
- daily.yml and approvals.yml have separate concurrency groups; approvals skips while a daily run is in progress (the daily job reads Telegram itself while waiting). State pushes use `git pull --rebase`.

## Rules
- Prompts load `.claude/skills/arabic-short-video-hooks` and `affiliate-post-pack` at runtime: edit the skills, not copies in code.
- Never invent prices/features; unknowns are `[تأكد]` and listed in `missing_facts`.
- Every video/caption/article keeps `#إعلان` and the affiliate disclosure.
- Remotion is the video designer (priority). Keep text inside the SAFE zone (no bottom 20%, no right edge).
- Voice lines (`Scene.voice`) are simple near-fusha Arabic with brand names in Arabic letters: TTS mispronounces dialect and Latin words. On-screen titles stay in white dialect.
- Free-tier Gemini model names change: keep fallbacks in `config.yaml` (`ai.gemini_models`, `voice.gemini_models`).
- Secrets only in GitHub Secrets: GEMINI_API_KEY, ANTHROPIC_API_KEY (optional), TAVILY_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PINTEREST_TOKEN.
- Local test without keys: `python -m agent daily --dry-run --product canva` (set REMOTION_BROWSER if Chrome download is blocked).
