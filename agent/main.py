"""Entry point. Run: python -m agent <daily|approvals|build|weekly> [options]"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time

from . import llm, pinterest, research, site, telegram, video, voice, writer
from .core import (CONTENT_DIR, STATE, all_drafts, draft_dir, env, load_config, load_draft, load_products, log,
                   now, read_json, save_draft, setup_logging, write_json)

HISTORY = STATE / "history.json"
PENDING_EDITS = STATE / "pending_edits.json"


# --- choosing what to promote today --------------------------------------------

def pick_product(products: list[dict], cfg: dict, forced: str = "") -> dict:
    if forced:
        return next(p for p in products if p["id"] == forced)
    usable = [p for p in products if p.get("status") in ("ready", "needs_link")]
    if not usable:
        raise SystemExit("products.yaml فيه ولا منتج جاهز")
    last = {}
    for h in read_json(HISTORY, []):
        last[h["product_id"]] = max(last.get(h["product_id"], ""), h["date"])
    cooldown = (now() - dt.timedelta(days=cfg["schedule"]["product_cooldown_days"])).isoformat()
    # ready links first, then the one we used longest ago
    usable.sort(key=lambda p: (p.get("status") != "ready", last.get(p["id"], "")))
    fresh = [p for p in usable if last.get(p["id"], "") < cooldown]
    return (fresh or usable)[0]


def recent_hooks(n: int = 10) -> list[str]:
    hooks = []
    for d in sorted(all_drafts(), key=lambda d: d["created_at"], reverse=True)[:n]:
        hooks += [h["text"] for h in d.get("hooks", []) if h.get("best")]
    return hooks


def unique_slug(slug: str, draft_id: str) -> str:
    base, i = slug, 2
    while (CONTENT_DIR / f"{slug}.json").exists() and read_json(CONTENT_DIR / f"{slug}.json", {}).get("draft_id") != draft_id:
        slug, i = f"{base}-{i}", i + 1
    return slug


# --- daily: research, write, voice, render, ask for approval --------------------

def daily(args, cfg: dict) -> None:
    products = load_products()
    feedback, version = args.feedback or "", 1
    if args.draft_id:
        old = load_draft(args.draft_id)
        product, draft_id, version = old["product"], old["id"], old.get("version", 1) + 1
    else:
        product = pick_product(products, cfg, args.product)
        draft_id = f"{now():%Y-%m-%d}-{product['id']}"
    log.info("product: %s  draft: %s", product["name"], draft_id)

    if not args.dry_run and not llm.has_key(cfg):
        msg = ("⚠️ ما قدرت أجهز مسودة اليوم: ما في مفتاح ذكاء اصطناعي.\n"
               "روح على aistudio.google.com واعمل مفتاح مجاني، وحطه بـ GitHub باسم GEMINI_API_KEY "
               "(Settings ← Secrets and variables ← Actions).")
        telegram.send(msg)
        log.error(msg)
        sys.exit(0 if telegram.enabled() else 1)

    if args.dry_run:
        notes = {"notes": "", "sources": []}
        content = writer.sample_draft(product)
    else:
        notes = research.research_product(product, cfg)
        content = writer.write_draft(product, notes, cfg, feedback, recent_hooks())

    draft = {"id": draft_id, "version": version, "status": "pending", "created_at": now().isoformat(),
             "product": product, "sources": notes["sources"], "feedback": feedback, **content}
    draft["article"]["slug"] = unique_slug(draft["article"]["slug"], draft_id)

    media = draft_dir(draft_id) / "media"
    draft["voiced"] = voice.voice_scenes(draft["scenes"], media, cfg)
    mp4 = video.render_video(draft, media, cfg)
    draft["cover"] = video.render_cover(draft, cfg)
    save_draft(draft)
    history = read_json(HISTORY, [])
    history.append({"product_id": product["id"], "draft_id": draft_id, "date": now().isoformat(), "status": "pending"})
    write_json(HISTORY, history)

    ask_approval(draft, mp4)
    if args.auto_approve:
        approve(draft, cfg)
    elif not args.dry_run:
        # GitHub runs the scheduled approvals job hours late, so wait here for the buttons
        listen(cfg, cfg["schedule"].get("approval_wait_minutes", 0), draft_id)


def cfg_voice_engine() -> str:
    return load_config().get("voice", {}).get("engine", "edge")


def ask_approval(draft: dict, mp4) -> None:
    p, post = draft["product"], draft["post"]
    warn = []
    if not p.get("affiliate_url"):
        warn.append("⚠️ ما في رابط عمولة لهالمنتج لسا. الزر رح يودي على الموقع الرسمي بدون عمولة. سجّل بالبرنامج وحط الرابط بـ products.yaml")
    if not draft.get("voiced"):
        warn.append("⚠️ الفيديو بدون صوت (خدمة الصوت ما اشتغلت هالمرة)")
    elif draft["voiced"] == "edge" and cfg_voice_engine() == "gemini":
        warn.append("ℹ️ صوت جوجل ما اشتغل، استعملت الصوت الاحتياطي")
    if draft.get("missing_facts"):
        warn.append("تأكد من: " + "، ".join(draft["missing_facts"]))
    caption = f"{post['caption']}\n\n{' '.join(post['hashtags'])}"
    telegram.send_video(mp4, caption)
    best = [h["text"] for h in draft["hooks"] if h.get("best")]
    text = "\n".join([
        f"📝 مسودة اليوم: {p['name']} (نسخة {draft['version']})",
        "",
        f"المقال: {draft['article']['title']}",
        f"الهوك: {best[0] if best else draft['scenes'][0]['title']}",
        "",
        *warn,
        "",
        "إذا وافقت: المقال بينزل على الموقع، وببعتلك الكابشن جاهز تنسخه مع الفيديو.",
    ])
    telegram.send(text, buttons=[[("✅ وافق", f"ok:{draft['id']}"), ("✏️ عدّل", f"edit:{draft['id']}"),
                                  ("❌ ارفض", f"no:{draft['id']}")]])


# --- approvals: read buttons, publish ---------------------------------------------

def approve(draft: dict, cfg: dict) -> None:
    rec = site.save_article(draft, draft.get("cover", ""), now().isoformat())
    draft["status"] = "approved"
    draft["published_at"] = now().isoformat()
    save_draft(draft)
    _set_history(draft["id"], "approved")
    base = cfg["brand"]["site_url"].rstrip("/")
    url = f"{base}/a/{rec['slug']}/"
    pinterest.pin(cfg, draft, url, f"{base}/{rec['cover']}")
    post = draft["post"]
    telegram.send("✅ تمام. المقال رح يكون على الموقع خلال دقايق:\n" + url)
    telegram.send("انسخ هاد مع الفيديو 👇\n\n" + post["caption"] + "\n\n" + " ".join(post["hashtags"]))
    telegram.send("\n".join([
        f"📌 تعليق مثبّت: {post['pinned_comment']}",
        f"🕘 وقت النشر: {post['posting_time']}",
        f"🔗 رابط البايو: {base}/links/",
        "شغّل خيار المحتوى المدفوع/الإعلان بالمنصة كمان.",
    ]))


def _set_history(draft_id: str, status: str) -> None:
    history = read_json(HISTORY, [])
    for h in history:
        if h["draft_id"] == draft_id:
            h["status"] = status
    write_json(HISTORY, history)


def regenerate(draft_id: str, feedback: str) -> None:
    if os.environ.get("GITHUB_ACTIONS"):
        subprocess.run(["gh", "workflow", "run", "daily.yml", "-f", f"draft_id={draft_id}", "-f", f"feedback={feedback}"], check=True)
    else:
        subprocess.run([sys.executable, "-m", "agent", "daily", "--draft-id", draft_id, "--feedback", feedback], check=True)


def _output_publish(published: bool) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"publish={'true' if published else 'false'}\n")


def approvals(args, cfg: dict) -> None:
    _output_publish(process_updates(cfg))


def listen(cfg: dict, minutes: int, draft_id: str) -> None:
    """Handle button presses as they come, until this draft is decided or time runs out.
    Stops right after an edit request so the re-write run (same concurrency group) can start."""
    if not telegram.enabled() or minutes <= 0:
        return
    deadline = time.time() + minutes * 60
    published = False
    log.info("waiting up to %s min for approval", minutes)
    while time.time() < deadline:
        published |= process_updates(cfg, wait=25)
        waiting_edit = draft_id in read_json(PENDING_EDITS, {}).values()
        if load_draft(draft_id)["status"] != "pending" and not waiting_edit:
            break
    _output_publish(published)


def process_updates(cfg: dict, wait: int = 0) -> bool:
    published = False
    pending = read_json(PENDING_EDITS, {})
    for u in telegram.updates(wait):
        cb = u.get("callback_query")
        if cb:
            action, _, draft_id = (cb.get("data") or "").partition(":")
            draft = load_draft(draft_id)
            if not draft:
                telegram.answer(cb["id"], "المسودة مش موجودة")
                continue
            if draft["status"] != "pending":
                telegram.answer(cb["id"], "هالمسودة انحسمت قبل")
                continue
            if action == "ok":
                telegram.answer(cb["id"], "تم ✅")
                approve(draft, cfg)
                published = True
            elif action == "no":
                draft["status"] = "rejected"
                save_draft(draft)
                _set_history(draft_id, "rejected")
                telegram.answer(cb["id"], "انرفضت")
                telegram.send(f"❌ رفضت مسودة {draft['product']['name']}. بكرا منجرب منتج تاني.")
            elif action == "edit":
                telegram.answer(cb["id"])
                mid = telegram.send("✏️ ردّ على هالرسالة واكتب شو بدك يتغير (مثلاً: الهوك أقوى، أقصر، ركّز على السعر).",
                                    force_reply=True)
                pending[str(mid)] = draft_id
            continue

        msg = u.get("message") or {}
        text = (msg.get("text") or "").strip()
        reply_to = str((msg.get("reply_to_message") or {}).get("message_id", ""))
        if reply_to in pending and text:
            draft_id = pending.pop(reply_to)
            draft = load_draft(draft_id)
            draft["status"] = "editing"
            save_draft(draft)
            telegram.send("👍 وصلت الملاحظة. عم جهّز نسخة جديدة، بتوصلك خلال 10 دقايق تقريباً.")
            regenerate(draft_id, text)
        elif text.startswith("/new"):
            telegram.send("👍 عم جهّز مسودة جديدة هسا.")
            if os.environ.get("GITHUB_ACTIONS"):
                subprocess.run(["gh", "workflow", "run", "daily.yml"], check=True)
        elif text.startswith("/status"):
            telegram.send(status_text())
    write_json(PENDING_EDITS, pending)
    return published


def status_text() -> str:
    ds = all_drafts()
    by = {}
    for d in ds:
        by[d["status"]] = by.get(d["status"], 0) + 1
    names = {"pending": "بانتظارك", "approved": "منشورة", "rejected": "مرفوضة", "editing": "عم تتعدل"}
    return "📊 الحالة:\n" + "\n".join(f"{names.get(k, k)}: {v}" for k, v in by.items()) if by else "لسا ما في مسودات."


# --- weekly report ------------------------------------------------------------------

def weekly(args, cfg: dict) -> None:
    since = (now() - dt.timedelta(days=7)).isoformat()
    week = [d for d in all_drafts() if d["created_at"] >= since]
    approved = [d for d in week if d["status"] == "approved"]
    products = load_products()
    no_link = [p["name"] for p in products if p.get("status") != "paused" and not p.get("affiliate_url")]
    lines = [
        "📈 تقرير الأسبوع",
        f"مسودات: {len(week)} · منشورة: {len(approved)} · مرفوضة: {sum(d['status'] == 'rejected' for d in week)}",
        "المنشور: " + ("، ".join(d["product"]["name"] for d in approved) or "ولا شي"),
        "",
        "شغلك هالأسبوع:",
        "• افتح لوحة Arabclicks/Admitad وشوف الضغطات والمبيعات، وابعتلي الأرقام برسالة.",
        "• شوف أي فيديو جاب أكتر مشاهدات بتيك توك، منكرر نفس نوع الهوك.",
    ]
    if no_link:
        lines.append("• منتجات بدون رابط عمولة: " + "، ".join(no_link))
    telegram.send("\n".join(lines))

    if args.dry_run or not llm.has_key(cfg):
        return
    found = research.discover_products(cfg, [p["name"] for p in products])
    if not found:
        return
    text = llm.ask_text(
        "من نتائج البحث التالية، اقترح 3 أدوات رقمية جديدة إلها برنامج عمولة ممكن ننشر عنها لجمهور الخليج. "
        "لكل وحدة: الاسم، ليش بتنفع للجمهور، نوع العمولة كما هو مذكور بالمصدر (أو 'غير واضح')، ورابط المصدر. "
        "بالعربي البسيط، بدون مبالغة، ولا تخترع نسب.\n\n" + found, cfg)
    if text:
        telegram.send("💡 اقتراحات منتجات جديدة:\n\n" + text)


# --- voice samples --------------------------------------------------------------------

SAMPLE_TEXT = "هل ما زلت تدفع لمصمم على كل منشور؟ مع كانفا برو، تختار قالبا جاهزا وتغير الكلام والألوان خلال دقائق."
EDGE_VOICES = ["ar-SA-HamedNeural", "ar-SA-ZariyahNeural", "ar-AE-HamdanNeural", "ar-JO-TaimNeural", "ar-EG-ShakirNeural"]
GEMINI_VOICES = ["Charon", "Kore", "Puck", "Orus"]


def voices(args, cfg: dict) -> None:
    """Same sentence in several voices, so the owner can pick by ear."""
    out = STATE.parent / "samples"
    out.mkdir(exist_ok=True)
    vc = cfg["voice"]
    made = []
    for v in EDGE_VOICES:
        path = out / f"edge-{v}.mp3"
        try:
            voice.edge_say(SAMPLE_TEXT, path, v, vc.get("rate", "-5%"))
            made.append((path, f"Edge: {v}"))
        except Exception as e:  # noqa: BLE001
            log.warning("edge %s: %s", v, e)
    if env("GEMINI_API_KEY"):
        for v in GEMINI_VOICES:
            path = out / f"gemini-{v}.wav"
            try:
                voice.gemini_say(SAMPLE_TEXT, path, {**vc, "gemini_voice": v})
                made.append((path, f"Google: {v}"))
            except Exception as e:  # noqa: BLE001
                log.warning("gemini %s: %s", v, e)
    log.info("samples: %s", [str(p) for p, _ in made])
    for path, label in made:
        telegram.send_audio(path, label)


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser(prog="agent")
    ap.add_argument("command", choices=["daily", "approvals", "build", "weekly", "voices"])
    ap.add_argument("--product", default="")
    ap.add_argument("--draft-id", default="")
    ap.add_argument("--feedback", default="")
    ap.add_argument("--dry-run", action="store_true", help="no API calls; sample content")
    ap.add_argument("--auto-approve", action="store_true", help="testing: publish the draft right away")
    args = ap.parse_args()
    cfg = load_config()
    if args.command == "daily":
        daily(args, cfg)
    elif args.command == "approvals":
        approvals(args, cfg)
    elif args.command == "build":
        out = site.build(cfg, load_products())
        log.info("site built: %s", out)
    elif args.command == "weekly":
        weekly(args, cfg)
    elif args.command == "voices":
        voices(args, cfg)
