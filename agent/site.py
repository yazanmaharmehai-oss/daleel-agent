"""Static Arabic RTL site: one page per approved article, a link-in-bio page, and /go/ redirects for affiliate links."""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

import markdown

from .core import SITE, read_json, write_json

BUILD = SITE / "_build"
CONTENT = SITE / "content"
DISCLOSURE = ("بعض الروابط بهالموقع روابط عمولة. إذا اشتريت منها بناخد نسبة صغيرة، "
              "وما بيزيد عليك السعر ولا قرش.")

e = html.escape


def _page(cfg: dict, title: str, body: str, depth: int, description: str = "", extra_head: str = "",
          path: str = "") -> str:
    b = cfg["brand"]
    root = "../" * depth or "./"
    canonical = f'{b["site_url"].rstrip("/")}/{path}'
    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description or b["tagline"])}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description or b["tagline"])}">
<link rel="stylesheet" href="{root}static/style.css">
{extra_head}
</head><body>
<header class="top"><div class="wrap"><a class="logo" href="{root}">{e(b["name"].split()[0])} <span>{e(" ".join(b["name"].split()[1:]) or "AI")}</span></a>
<nav><a href="{root}links/">الروابط</a><a href="{root}about/">عن الموقع</a></nav></div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap">{e(DISCLOSURE)}<br>{e(b["name"])} · {e(b["handle"])}</div></footer>
</body></html>"""


def save_article(draft: dict, cover: str, date: str) -> dict:
    """Called when a draft is approved: freeze the article into site/content/<slug>.json."""
    a = draft["article"]
    rec = {
        "slug": a["slug"], "title": a["title"], "description": a["description"],
        "body_markdown": a["body_markdown"], "faq": a["faq"],
        "product": {k: draft["product"].get(k, "") for k in ("id", "name", "category", "official_url", "affiliate_url")},
        "cover": cover, "date": date, "draft_id": draft["id"],
    }
    write_json(CONTENT / f"{a['slug']}.json", rec)
    return rec


def _articles() -> list[dict]:
    items = [read_json(p, None) for p in CONTENT.glob("*.json")]
    return sorted([i for i in items if i], key=lambda r: r["date"], reverse=True)


def _cta(rec: dict, root: str) -> str:
    p = rec["product"]
    return (f'<div class="cta"><div><b>{e(p["name"])}</b><div class="meta">{e(p.get("category", ""))} · رابط عمولة</div></div>'
            f'<a class="btn" rel="sponsored nofollow" href="{root}go/{e(p["id"])}/">جرّبها</a></div>')


def _article_html(rec: dict, cfg: dict) -> str:
    root = "../../"
    md = html.escape(rec["body_markdown"], quote=False)  # no raw HTML from the model
    body = markdown.markdown(md, extensions=["extra"]).replace("{{LINK}}", _cta(rec, root))
    faq = "".join(f"<details><summary>{e(q['q'])}</summary><p>{e(q['a'])}</p></details>" for q in rec["faq"])
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in rec["faq"]]}
    head = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
    if rec.get("cover"):
        head += f'<meta property="og:image" content="{e(cfg["brand"]["site_url"].rstrip("/") + "/" + rec["cover"])}">'
    cover = f'<img class="cover" src="{root}{e(rec["cover"])}" alt="{e(rec["title"])}">' if rec.get("cover") else ""
    content = (f'<article><h1>{e(rec["title"])}</h1><div class="meta">{e(rec["date"][:10])}</div>'
               f'<p class="disc">{e(DISCLOSURE)}</p>{cover}{body}'
               f'{_cta(rec, root)}<section class="faq"><h2>أسئلة شائعة</h2>{faq}</section></article>')
    return _page(cfg, rec["title"], content, 2, rec["description"], head, f"a/{rec['slug']}/")


def _redirect_html(product: dict) -> str:
    url = product.get("affiliate_url") or product.get("official_url") or "../../"
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow"><meta http-equiv="refresh" content="0;url={e(url)}">
<title>جاري التحويل</title></head><body><p>جاري التحويل إلى <a rel="sponsored nofollow" href="{e(url)}">{e(product["name"])}</a></p></body></html>"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(cfg: dict, products: list[dict]) -> Path:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    shutil.copytree(SITE / "static", BUILD / "static")
    arts = _articles()
    b = cfg["brand"]

    cards = "".join(
        f'<a class="card" href="a/{e(r["slug"])}/">'
        + (f'<img loading="lazy" src="{e(r["cover"])}" alt="">' if r.get("cover") else "")
        + f'<div><h3>{e(r["title"])}</h3><p>{e(r["description"])}</p></div></a>' for r in arts)
    empty = "" if arts else '<p class="lead">أول مقال رح ينزل قريباً.</p>'
    _write(BUILD / "index.html", _page(cfg, b["name"], f'<h1>{e(b["name"])}</h1><p class="lead">{e(b["tagline"])}</p>'
                                       f'<p class="disc">{e(DISCLOSURE)}</p>{empty}<div class="cards">{cards}</div>', 0))

    # link-in-bio page: newest first, this is what goes in TikTok/Snap/Instagram bio
    links = "".join(f'<a href="../a/{e(r["slug"])}/">{e(r["product"]["name"])}<small>{e(r["title"])}</small></a>' for r in arts[:20])
    _write(BUILD / "links" / "index.html", _page(cfg, f'روابط {b["name"]}', f'<h1>الروابط</h1><p class="lead">كل الأدوات اللي حكينا عنها بالفيديوهات. الأحدث فوق.</p>'
                                                   f'<p class="disc">{e(DISCLOSURE)}</p><div class="links">{links}</div>', 1, path="links/"))

    _write(BUILD / "about" / "index.html", _page(cfg, f'عن {b["name"]}', f'<h1>عن الموقع</h1><p>{e(b["tagline"])}. منشرح كل أداة بالعربي وبكلام بسيط: '
                                                   'شو بتعمل، كم سعرها، ولمين بتنفع.</p><h2>الإفصاح</h2>'
                                                   f'<p>{e(DISCLOSURE)} منكتب رأينا بصراحة، والمعلومات من مواقع الأدوات الرسمية بتاريخ نشر كل مقال.</p>', 1, path="about/"))

    for r in arts:
        _write(BUILD / "a" / r["slug"] / "index.html", _article_html(r, cfg))
    # redirects use the live products.yaml link, so adding a link later fixes old articles too
    by_id = {p["id"]: p for p in products}
    for r in arts:
        p = {**r["product"], **{k: v for k, v in by_id.get(r["product"]["id"], {}).items() if v}}
        _write(BUILD / "go" / p["id"] / "index.html", _redirect_html(p))

    base = b["site_url"].rstrip("/")
    urls = [f"{base}/", f"{base}/links/", f"{base}/about/"] + [f"{base}/a/{r['slug']}/" for r in arts]
    _write(BUILD / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(f"<url><loc>{e(u)}</loc></url>" for u in urls) + "</urlset>\n")
    _write(BUILD / "robots.txt", f"User-agent: *\nDisallow: /go/\nSitemap: {base}/sitemap.xml\n")
    _write(BUILD / "404.html", _page(cfg, "الصفحة مش موجودة", '<h1>الصفحة مش موجودة</h1><p><a href="/">ارجع للرئيسية</a></p>', 0))
    (BUILD / ".nojekyll").touch()
    return BUILD
