from __future__ import annotations

import html
import json
import re

try:
    from .common import Item, POSTS, clean_text, now_ist
except ImportError:
    from common import Item, POSTS, clean_text, now_ist


def parse_ai_output(text: str) -> tuple[str, str, list[tuple[str, list[str]]]]:
    title = "Cosmology Brief"
    summary = "Daily cosmology research news and academic opportunities."
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_lines
        if current_heading:
            sections.append((current_heading, current_lines))
        current_heading = None
        current_lines = []

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("TITLE:"):
            title = clean_text(line.split(":", 1)[1]) or title
        elif line.startswith("SUMMARY:"):
            summary = clean_text(line.split(":", 1)[1]) or summary
        elif line.startswith("SECTION:"):
            flush()
            current_heading = clean_text(line.split(":", 1)[1])
        elif line.strip():
            current_lines.append(line)
    flush()
    return title, summary, sections


def item_lookup(items: list[Item]) -> dict[str, Item]:
    return {item.item_id: item for item in items}


def safe_yaml(value: str) -> str:
    return json.dumps(clean_text(value), ensure_ascii=False)


def strip_source_ids(text: str) -> tuple[str, list[str]]:
    ids: list[str] = []
    match = re.search(r"\s*Sources?:\s*((?:\[[NJ]\d+\]\s*,?\s*)+)$", text, flags=re.I)
    if match:
        ids = [x.upper() for x in re.findall(r"\[([NJ]\d+)\]", match.group(1), flags=re.I)]
        text = text[:match.start()].rstrip()
    return clean_text(text), ids


def split_strong_lead(text: str) -> tuple[str, str]:
    match = re.match(r"^\*\*([^*]+):\*\*\s*(.+)$", text)
    if match:
        return clean_text(match.group(1)), clean_text(match.group(2))
    return "", clean_text(re.sub(r"^[-*]\s*", "", text))


def source_chips(ids: list[str], lookup: dict[str, Item]) -> str:
    chips: list[str] = []
    seen: set[str] = set()
    for pos, item_id in enumerate(ids, 1):
        if item_id in seen:
            continue
        seen.add(item_id)
        item = lookup.get(item_id)
        if not item:
            continue
        href = html.escape(item.url, quote=True)
        label = f"Source {pos}"
        chips.append(f'<a class="source-chip" href="{href}" target="_blank" rel="noopener noreferrer">↗ {label}</a>')
    return "".join(chips)


def bullet_to_html(line: str, lookup: dict[str, Item]) -> str:
    raw = line.strip()
    if raw.startswith(("- ", "* ")):
        raw = raw[2:].strip()
    raw, ids = strip_source_ids(raw)
    lead, body = split_strong_lead(raw)
    if lead:
        point = f"<strong>{html.escape(lead)}:</strong> {html.escape(body)}"
    else:
        point = html.escape(body)
    chips = source_chips(ids, lookup)
    if chips:
        sources = f'<div class="source-row"><span class="source-label">Sources</span>{chips}</div>'
    else:
        sources = ""
    return f'<li><p>{point}</p>{sources}</li>'


def section_to_html(heading: str, body_lines: list[str], lookup: dict[str, Item]) -> str:
    bullets = [line for line in body_lines if line.strip().startswith(("- ", "* "))]
    if not bullets:
        return ""
    html_lines = [f'<section class="digest-section">', f'<h2>{html.escape(heading)}</h2>', '<ul class="digest-points">']
    for line in bullets:
        html_lines.append(bullet_to_html(line, lookup))
    html_lines.append('</ul>')
    html_lines.append('</section>')
    return "\n".join(html_lines)


def source_list(items: list[Item]) -> str:
    lines = ['<details class="sources-considered">', '<summary>Sources considered</summary>', '<ul>']
    for item in items:
        title = html.escape(clean_text(item.title))
        source = html.escape(clean_text(item.source))
        url = html.escape(item.url, quote=True)
        lines.append(f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">[{item.item_id}] {title}</a> <span>{source}</span></li>')
    lines.extend(['</ul>', '</details>'])
    return "\n".join(lines)


def write_post(ai_text: str, items: list[Item], settings: dict) -> str:
    POSTS.mkdir(parents=True, exist_ok=True)
    title, summary, sections = parse_ai_output(ai_text)
    date = now_ist()
    try:
        run_time = date.strftime("%-I:%M%p")
    except ValueError:
        run_time = date.strftime("%I:%M%p").lstrip("0")
    slug = "cosmology-brief"
    filename = POSTS / f"{date.strftime('%Y-%m-%d')}-{slug}.md"

    front = (
        "---\n"
        "layout: default\n"
        f"title: {safe_yaml(title)}\n"
        f"date: {date.isoformat()}\n"
        f"summary: {safe_yaml(summary)}\n"
        f"run_time_ist: {safe_yaml(run_time)}\n"
        "---\n"
    )

    lookup = item_lookup(items)
    run_label = "Gemini Summary" if settings.get("used_ai", True) else "Headline Digest"
    html_parts: list[str] = []
    html_parts.append('<p class="site-link-wrap"><a class="site-link" href="{{ \'/\' | relative_url }}">Cosmology Brief</a></p>')
    html_parts.append(f'<h1 class="brief-run">{html.escape(run_label)}: {html.escape(run_time)}</h1>')
    html_parts.append('<hr class="brief-rule">')

    for heading, body_lines in sections:
        block = section_to_html(heading, body_lines, lookup)
        if block:
            html_parts.append(block)

    html_parts.append(source_list(items))
    filename.write_text(front + "\n" + "\n\n".join(html_parts).rstrip() + "\n", encoding="utf-8")
    return str(filename)
