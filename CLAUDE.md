# daleel-agent

Affiliate-marketing agent for an Arabic brand page ("دليل الذكي", @daleel.ai). Owner: Yazan, Jordan, complete beginner; reply to them in simple Levantine Arabic, blunt, no flattery.

## Architecture
- `python -m agent daily`: pick product (products.yaml) → Tavily research → Claude structured draft (`agent/writer.py`, pydantic `Draft`) → Edge TTS per scene → Remotion render (`video/src/index.jsx`, composition `Promo`, props from the draft) + `Cover` still → Telegram approval buttons.
- `python -m agent approvals`: reads Telegram updates (owner chat only), approve → `site/content/<slug>.json`; edit → re-dispatches daily.yml with feedback.
- `python -m agent build`: static RTL site in `site/_build` (GitHub Pages via approvals.yml).
- State is committed to git (`state/`, `drafts/*/draft.json`, `site/content/`). Media (`drafts/*/media/`) is not; videos reach the owner via Telegram and Actions artifacts.
- All workflows share concurrency group `daleel-state` so state commits never race.

## Rules
- Prompts load `.claude/skills/arabic-short-video-hooks` and `affiliate-post-pack` at runtime: edit the skills, not copies in code.
- Never invent prices/features; unknowns are `[تأكد]` and listed in `missing_facts`.
- Every video/caption/article keeps `#إعلان` and the affiliate disclosure.
- Remotion is the video designer (priority). Keep text inside the SAFE zone (no bottom 20%, no right edge).
- Secrets only in GitHub Secrets: ANTHROPIC_API_KEY, TAVILY_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PINTEREST_TOKEN.
- Local test without keys: `python -m agent daily --dry-run --product canva` (set REMOTION_BROWSER if Chrome download is blocked).
