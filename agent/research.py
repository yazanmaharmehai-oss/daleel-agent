"""Product research with Tavily: facts come from the official site and recent reviews, never from memory."""
from __future__ import annotations

from .core import env, log


def _client():
    from tavily import TavilyClient
    return TavilyClient(api_key=env("TAVILY_API_KEY"))


def research_product(product: dict, cfg: dict) -> dict:
    """Return {"notes": str, "sources": [url]} for the writer."""
    if not env("TAVILY_API_KEY"):
        log.warning("TAVILY_API_KEY missing: using product notes only")
        return {"notes": f"لا يوجد بحث. المعلومات المتاحة: {product}", "sources": [product.get("official_url", "")]}

    client = _client()
    rc = cfg.get("research", {})
    name = product["name"]
    notes, sources = [], []

    # 1) official page: features and pricing
    if product.get("official_url"):
        try:
            ex = client.extract(urls=[product["official_url"]], query=f"{name} features pricing free plan",
                                chunks_per_source=4)
            for item in ex.get("results", []):
                notes.append(f"[مصدر رسمي] {item['url']}\n{item['raw_content'][:4000]}")
                sources.append(item["url"])
        except Exception as e:  # noqa: BLE001 - research is best effort
            log.warning("extract failed: %s", e)

    # 2) pricing + reviews + Arabic demand
    queries = [
        f"{name} pricing plans free trial",
        f"{name} review pros cons",
        f"{name} بالعربي شرح",
    ]
    for q in queries:
        try:
            res = client.search(q, search_depth="advanced", max_results=rc.get("max_results", 6),
                                exclude_domains=rc.get("exclude_domains", []), time_range="year")
        except Exception as e:  # noqa: BLE001
            log.warning("search failed for %r: %s", q, e)
            continue
        for r in res.get("results", []):
            if r.get("score", 0) < 0.4:
                continue
            notes.append(f"[{q}] {r['title']} | {r['url']}\n{r['content'][:1200]}")
            sources.append(r["url"])

    return {"notes": "\n\n".join(notes)[:30000], "sources": list(dict.fromkeys(sources))}


def discover_products(cfg: dict, known: list[str]) -> str:
    """Weekly: look for AI tools with affiliate programs that Gulf users search for."""
    if not env("TAVILY_API_KEY"):
        return ""
    client = _client()
    res = client.search(
        "best AI tools affiliate program recurring commission 2026",
        search_depth="advanced", max_results=10, include_answer="advanced", time_range="month",
    )
    lines = [res.get("answer") or ""]
    for r in res.get("results", []):
        lines.append(f"- {r['title']} | {r['url']}\n{r['content'][:500]}")
    return "\n".join(lines)[:15000] + f"\n\nمنتجات عندنا أصلاً: {', '.join(known)}"
