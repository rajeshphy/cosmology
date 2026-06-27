from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone

try:
    from .common import API_KEY_ENV, DATA, DEFAULT_GEMINI_MODEL, GEMINI_API_ROOT, Item, clean_text, now_ist
    from .filter import score_item
except ImportError:
    from common import API_KEY_ENV, DATA, DEFAULT_GEMINI_MODEL, GEMINI_API_ROOT, Item, clean_text, now_ist
    from filter import score_item

QUOTA_FILE = DATA / "quota.json"


def load_quota() -> dict:
    if not QUOTA_FILE.exists():
        return {"day": "", "count": 0, "last_call": 0.0}
    try:
        return json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"day": "", "count": 0, "last_call": 0.0}


def reserve_gemini_call(max_daily_calls: int = 20, min_interval_seconds: int = 12) -> None:
    DATA.mkdir(exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    quota = load_quota()
    if quota.get("day") != today:
        quota = {"day": today, "count": 0, "last_call": 0.0}
    if int(quota.get("count", 0)) >= max_daily_calls:
        raise RuntimeError(f"Daily Gemini call limit reached: {max_daily_calls}")
    elapsed = time.time() - float(quota.get("last_call", 0.0))
    if elapsed < min_interval_seconds:
        time.sleep(min_interval_seconds - elapsed)
    quota["count"] = int(quota.get("count", 0)) + 1
    quota["last_call"] = time.time()
    QUOTA_FILE.write_text(json.dumps(quota, indent=2), encoding="utf-8")


def candidate_block(items: list[Item], settings: dict) -> str:
    lines: list[str] = []
    for section, heading in (("news", "Cosmology News"), ("jobs", "Cosmology Jobs and Fellowships")):
        lines.append(f"SECTION CANDIDATES: {heading}")
        section_items = [i for i in items if i.section == section]
        for item in section_items[:25]:
            lines.append(f"[{item.item_id}] score={score_item(item, settings)} date={item.published} source={item.source} kind={item.kind}")
            lines.append(f"TITLE: {item.title}")
            if item.summary:
                lines.append(f"SUMMARY: {item.summary[:240]}")
        if not section_items:
            lines.append("No candidates found.")
    return "\n".join(lines)


def gemini_digest(items: list[Item], api_key: str, settings: dict) -> str:
    reserve_gemini_call()
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    url = f"{GEMINI_API_ROOT}/{model}:generateContent?key={api_key}"
    news_points = int(settings.get("final_news_points", 5))
    jobs_points = int(settings.get("final_jobs_points", 5))
    today = now_ist().strftime("%Y-%m-%d")
    prompt = f"""
Create a concise English cosmology digest for researchers and physics students.
Current IST date: {today}

Output exactly this plain-text structure:
TITLE: short title
SUMMARY: one homepage line under 160 characters
SECTION: Cosmology News
- **Topic:** one factual sentence on the discovery/result/mission/paper and why it matters. Sources: [N1]
SECTION: Jobs and Fellowships
- **Role/program:** what it is, where/which source, and why it is relevant to cosmology researchers. Sources: [J1]

Rules:
- Use only the supplied candidates.
- Produce at most {news_points} bullets in Cosmology News and at most {jobs_points} bullets in Jobs and Fellowships.
- Prefer fewer bullets over weak or duplicate bullets.
- Every bullet must end with source ids in the exact format: Sources: [N1], [N2] or Sources: [J1]
- Do not invent deadlines, eligibility, salary, location, or application details unless present in the title/summary.
- For job pages that are general portals, say “current opportunities page” rather than inventing a specific vacancy.
- Keep the tone academic, clean, and useful.

Candidates:
{candidate_block(items, settings)}
""".strip()
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2200}}
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"]


def fallback_digest(items: list[Item], settings: dict) -> str:
    title = "Cosmology Brief"
    summary = "Latest cosmology research signals and academic opportunity links from configured sources."
    lines = [f"TITLE: {title}", f"SUMMARY: {summary}"]
    for section, heading, max_points in (("news", "Cosmology News", int(settings.get("final_news_points", 5))), ("jobs", "Jobs and Fellowships", int(settings.get("final_jobs_points", 5)))):
        lines.append(f"SECTION: {heading}")
        section_items = [i for i in items if i.section == section][:max_points]
        if not section_items:
            lines.append("- **No strong items found:** Check the configured sources manually for updates. Sources: []")
            continue
        for item in section_items:
            topic = clean_text(item.title).rstrip(".")
            if section == "news":
                lines.append(f"- **{item.source}:** {topic}. Sources: [{item.item_id}]")
            else:
                lines.append(f"- **{item.source}:** {topic}. Sources: [{item.item_id}]")
    return "\n".join(lines)
