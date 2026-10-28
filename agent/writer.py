"""Claude writes the whole draft in one structured call: hooks, video scenes, article, post pack."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .core import env, log, skill_text


class Hook(BaseModel):
    archetype: str = Field(description="One of the 7 hook archetypes, in Arabic")
    text: str
    best: bool = Field(description="True for the 2 strongest hooks")


class Scene(BaseModel):
    kind: Literal["hook", "problem", "before_after", "feature", "offer", "cta"]
    title: str = Field(description="On-screen text, 3-7 words. Wrap ONE key word in [[ ]] to highlight it.")
    voice: str = Field(description="Spoken line, white Gulf-friendly dialect, max ~14 words")
    before: str = Field(description="before_after only: what a normal person writes/does. Else empty")
    after: str = Field(description="before_after only: the result with the product. Else empty")
    bullets: list[str] = Field(description="feature/offer: up to 3 very short items. Else empty")


class QA(BaseModel):
    q: str
    a: str


class Article(BaseModel):
    title: str
    slug: str = Field(description="latin lowercase words joined by hyphens, max 6 words")
    description: str = Field(description="meta description, max 155 chars, Arabic")
    body_markdown: str = Field(description="600-1000 words Arabic markdown, ## headings, no H1. "
                               "Use {{LINK}} where the affiliate button should go (2 times).")
    faq: list[QA]


class PostPack(BaseModel):
    caption: str
    hashtags: list[str]
    pinned_comment: str
    posting_time: str
    pinterest_title: str
    pinterest_description: str


class Claim(BaseModel):
    fact: str
    source_url: str


class Draft(BaseModel):
    hooks: list[Hook]
    scenes: list[Scene] = Field(description="6-8 scenes: hook, problem, 2-4 demo scenes, offer, cta")
    article: Article
    post: PostPack
    claims: list[Claim] = Field(description="Every factual claim used (price, feature) with its source URL")
    missing_facts: list[str] = Field(description="Facts you could not verify; they are marked [تأكد] in the text")
    next_test: str


SYSTEM = """أنت كاتب محتوى وخبير تسويق بالعمولة لصفحة عربية اسمها "{brand}" ({handle}).
الصفحة بتعرض كل يوم أداة ذكاء اصطناعي أو أداة رقمية بتسهّل الشغل، لجمهور الخليج والعالم العربي.

قواعد ثابتة:
- الحقائق (السعر، الميزات، الخطة المجانية) فقط من ملاحظات البحث المرفقة. لا تخترع أرقام أو مراجعات أو خصومات.
- إذا معلومة ناقصة: اكتب [تأكد] مكانها وحطها بـ missing_facts.
- ما تقول "جرّبت" إلا إذا الملاحظات بتقول إن صاحب الصفحة جرّب. استعمل "لقيت" أو "شفت".
- كل فيديو وكابشن فيهم #إعلان وذكر إنه رابط عمولة.
- الجمهور مش تقني: كلام بسيط، أمثلة من شغل الناس اليومي بالخليج.

## نظام الهوكات والسكربت
{hooks}

## حزمة النشر
{post}
"""


def write_draft(product: dict, research: dict, cfg: dict, feedback: str = "", recent_hooks: list[str] | None = None) -> dict:
    import anthropic

    system = SYSTEM.format(
        brand=cfg["brand"]["name"], handle=cfg["brand"]["handle"],
        hooks=skill_text("arabic-short-video-hooks"), post=skill_text("affiliate-post-pack"),
    )
    user = [
        f"المنتج: {product['name']} ({product.get('category', '')})",
        f"الموقع الرسمي: {product.get('official_url', '')}",
        f"الزاوية المقترحة: {product.get('angle', '')}",
        f"الأسواق: {', '.join(cfg.get('markets', []))}",
        "",
        "## ملاحظات البحث (المصدر الوحيد للحقائق)",
        research["notes"],
    ]
    if recent_hooks:
        user += ["", "## هوكات استعملناها مؤخراً، لا تكررها", *recent_hooks]
    if feedback:
        user += ["", "## ملاحظات صاحب الصفحة على النسخة السابقة، طبّقها", feedback]

    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    resp = client.messages.parse(
        model=cfg["ai"]["model"],
        max_tokens=cfg["ai"].get("max_tokens", 16000),
        system=system,
        messages=[{"role": "user", "content": "\n".join(user)}],
        output_format=Draft,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude refused this draft")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise RuntimeError(f"Draft incomplete (stop_reason={resp.stop_reason})")
    u = resp.usage
    log.info("claude usage: in=%s out=%s", u.input_tokens, u.output_tokens)
    out = resp.parsed_output.model_dump()
    out["usage"] = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens}
    return out


def sample_draft(product: dict) -> dict:
    """Offline draft for --dry-run, so video and site can be tested without API keys."""
    name = product["name"]
    return {
        "hooks": [
            {"archetype": "سؤال الألم", "text": "لسا بتدفع لمصمم على كل بوست؟", "best": True},
            {"archetype": "نتيجة محددة", "text": "10 بوستات لمشروعك بأقل من ساعة", "best": True},
            {"archetype": "نداء للجمهور", "text": "إذا عندك مشروع صغير بالخليج، شوف هاد", "best": False},
        ],
        "scenes": [
            {"kind": "hook", "title": "لسا بتدفع [[لمصمم]] على كل بوست؟", "voice": "لسا بتدفع لمصمم على كل بوست لمشروعك؟", "before": "", "after": "", "bullets": []},
            {"kind": "problem", "title": "كل بوست [[يومين]] انتظار", "voice": "وكل تعديل صغير بياخد يومين، وبتدفع عليه كمان.", "before": "", "after": "", "bullets": []},
            {"kind": "before_after", "title": f"مع [[{name}]] بتخلص بدقايق", "voice": "اختار قالب، غيّر الكلام والألوان، وخلصت.", "before": "صورة منتج على خلفية عادية", "after": "إعلان جاهز بشعارك وألوانك", "bullets": []},
            {"kind": "feature", "title": "قوالب [[جاهزة]] لكل مناسبة", "voice": "في قوالب لرمضان والعيد والعروض، بس بتعدّل عليها.", "before": "", "after": "", "bullets": ["رمضان", "العيد", "العروض"]},
            {"kind": "feature", "title": "شيل الخلفية [[بكبسة]]", "voice": "وبتشيل خلفية الصورة بكبسة وحدة.", "before": "", "after": "", "bullets": []},
            {"kind": "offer", "title": "في نسخة [[مجانية]]", "voice": "في نسخة مجانية تبلش فيها، والمدفوعة [تأكد] بالشهر.", "before": "", "after": "", "bullets": ["مجاني للبداية", "المدفوع: [تأكد]"]},
            {"kind": "cta", "title": "الرابط [[بالبايو]]", "voice": "الرابط بالبايو، واحفظ الفيديو لصاحبك اللي عنده مشروع.", "before": "", "after": "", "bullets": []},
        ],
        "article": {
            "title": f"{name}: كيف تصمم بوستات مشروعك بنفسك بدون مصمم",
            "slug": f"{product['id']}-guide",
            "description": f"شرح بسيط بالعربي لأداة {name}: شو بتعمل، كم سعرها، ولمين بتنفع.",
            "body_markdown": f"## ليش هاد الموضوع مهم\nأغلب المشاريع الصغيرة بالخليج بتدفع على كل تصميم.\n\n{{{{LINK}}}}\n\n## شو بتعمل {name}\n- قوالب جاهزة\n- إزالة الخلفية\n\n## السعر\n[تأكد من السعر]\n\n{{{{LINK}}}}\n",
            "faq": [{"q": f"هل {name} مجانية؟", "a": "في نسخة مجانية، والمدفوعة بميزات أكثر [تأكد]."}],
        },
        "post": {
            "caption": "لسا بتدفع لمصمم على كل بوست؟\nفي أداة بتخليك تصمم بنفسك بدقايق.\nالرابط بالبايو\n#إعلان (رابط عمولة)",
            "hashtags": ["#ذكاء_اصطناعي", "#تصميم", "#مشاريع_صغيرة", "#تسويق", "#السعودية"],
            "pinned_comment": "بدك أشرحلك أداة لشغل معين؟ اكتبلي هون، والرابط بالبايو",
            "posting_time": "8 إلى 11 بالليل بتوقيت السعودية (نبلش فيه ونجرب)",
            "pinterest_title": f"{name} بالعربي: صمم بوستات مشروعك بنفسك",
            "pinterest_description": "شرح بسيط بالعربي للمشاريع الصغيرة.",
        },
        "claims": [],
        "missing_facts": ["السعر الشهري للنسخة المدفوعة"],
        "next_test": "جرّب هوك النتيجة المحددة بدل سؤال الألم",
    }
