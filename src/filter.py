from __future__ import annotations

import re
import urllib.parse
from datetime import timedelta, timezone

try:
    from .common import IST, Item, clean_text, config_bool, csv_keywords, now_ist
except ImportError:
    from common import IST, Item, clean_text, config_bool, csv_keywords, now_ist


def keyword_set(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{3,}", clean_text(text).lower())
    stop = {"jobs", "news", "latest", "today", "with", "from", "that", "this", "research", "physics", "astronomy", "astrophysics", "position", "positions", "opportunity", "opportunities"}
    return {w for w in words if w not in stop}


def normalized_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def is_fresh(item: Item, settings: dict) -> bool:
    if item.section == "news":
        require_today = config_bool(settings.get("require_ist_today"), False)
        allow_unknown = config_bool(settings.get("allow_unknown_dates_news"), True)
        max_age_hours = int(settings.get("max_age_hours_news", 168))
    else:
        allow_unknown = config_bool(settings.get("allow_unknown_dates_jobs"), True)
        require_today = False
        max_age_hours = int(settings.get("max_age_hours_jobs", 720))
    if not item.published_at:
        return allow_unknown
    published_ist = item.published_at.astimezone(IST)
    if require_today and published_ist.date() != now_ist().date():
        return False
    return now_ist() - published_ist <= timedelta(hours=max_age_hours)


def relevant(item: Item, settings: dict) -> bool:
    haystack = f"{item.title} {item.summary} {item.source}".lower()
    exclude = csv_keywords(settings.get("exclude_keywords"))
    if any(word in haystack for word in exclude):
        return False
    key = "news_keywords" if item.section == "news" else "job_keywords"
    keywords = csv_keywords(settings.get(key))
    if item.section == "jobs" and item.kind in {"fellowship", "institute"}:
        # Fellowship/institute pages may not expose detailed titles on listing pages.
        return True
    return any(word in haystack for word in keywords)


def score_item(item: Item, settings: dict) -> int:
    text = f"{item.title} {item.summary} {item.source}".lower()
    keywords = csv_keywords(settings.get("news_keywords" if item.section == "news" else "job_keywords"))
    score = max(1, int(item.source_weight))
    score += min(8, sum(1 for word in keywords if word in text))
    if item.section == "jobs":
        for term in ("postdoc", "postdoctoral", "research associate", "visiting fellow", "fellowship", "research scientist", "assistant professor", "faculty", "tenure"):
            if term in text:
                score += 3
        if any(term in text for term in ("cosmology", "dark matter", "dark energy", "cmb", "astrophysics", "astronomy", "gravitation")):
            score += 5
        india_terms = csv_keywords(settings.get("india_priority_keywords"))
        if any(term.lower() in text for term in india_terms):
            score += 8
        if any(term in text for term in ("region: india", "indian citizen", "indian citizens", "india-relevant", "india-resident")):
            score += 10
        if any(term in text for term in ("us citizen", "permanent resident", "citizenship required")):
            score -= 12
    else:
        if any(term in text for term in ("dark energy", "dark matter", "cmb", "hubble tension", "early universe", "inflation", "large-scale structure", "cosmology")):
            score += 5
    if item.published_at:
        age = now_ist() - item.published_at.astimezone(IST)
        if age <= timedelta(hours=24):
            score += 4
        elif age <= timedelta(hours=72):
            score += 2
    return score


def dedupe(items: list[Item]) -> list[Item]:
    out: list[Item] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for item in items:
        url_key = normalized_url(item.url)
        title_key = " ".join(sorted(keyword_set(item.title)))
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        out.append(item)
    return out


def assign_ids(section: str, items: list[Item]) -> list[Item]:
    prefix = "N" if section == "news" else "J"
    for idx, item in enumerate(items, 1):
        item.item_id = f"{prefix}{idx}"
    return items


def select_items(items: list[Item], settings: dict) -> list[Item]:
    selected: list[Item] = []
    for section in ("news", "jobs"):
        limit = int(settings.get(f"{section}_limit", 40 if section == "news" else 60))
        section_items = [item for item in items if item.section == section and is_fresh(item, settings) and relevant(item, settings)]
        section_items = dedupe(section_items)
        section_items.sort(key=lambda x: (score_item(x, settings), x.published_at.timestamp() if x.published_at else 0.0), reverse=True)
        selected.extend(assign_ids(section, section_items[:limit]))
    return selected
