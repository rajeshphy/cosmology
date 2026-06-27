from __future__ import annotations

import json
import os
import re
import socket
import ssl
import signal
from contextlib import contextmanager
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

try:
    from .common import Item, clean_text, format_date
except ImportError:
    from common import Item, clean_text, format_date


USER_AGENT = "CosmologyBrief/1.1 (+https://github.com/rajeshphy/cosmology-news)"
socket.setdefaulttimeout(int(os.environ.get("FETCH_TIMEOUT_SECONDS", "6")))


def _ssl_context(allow_insecure: bool = False):
    if allow_insecure:
        return ssl._create_unverified_context()
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/rss+xml, application/atom+xml, application/xml, text/xml, text/html, */*",
            "Accept-Language": "en-IN,en;q=0.9",
        },
    )
    try:
        response_cm = urllib.request.urlopen(request, timeout=int(os.environ.get("FETCH_TIMEOUT_SECONDS", "6")), context=_ssl_context(False))
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        message = str(reason or exc)
        if "CERTIFICATE_VERIFY_FAILED" not in message:
            raise
        # Some Indian institutional websites have incomplete SSL chains on local Python installs.
        # Retry only for this certificate-chain failure; GitHub Actions usually succeeds with certifi.
        response_cm = urllib.request.urlopen(request, timeout=int(os.environ.get("FETCH_TIMEOUT_SECONDS", "6")), context=_ssl_context(True))
    with response_cm as response:
        raw = response.read()
        content_type = response.headers.get("content-type", "")
    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type, flags=re.I)
    if match:
        charset = match.group(1)
    return raw.decode(charset, errors="replace")


def parse_date(value: str | None) -> datetime | None:
    value = clean_text(value)
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value[:26], fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            continue
    return None


def absolute_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, clean_text(href))


def collect_xml(section: str, source: dict, feed_kind: str) -> list[Item]:
    source_name = source.get("name", "Source")
    source_weight = int(source.get("weight", 1))
    url = source["url"]
    text = fetch_text(url)
    root = ET.fromstring(text)
    items: list[Item] = []

    if feed_kind == "atom" or root.tag.endswith("feed"):
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//a:entry", ns) or root.findall(".//entry")
        for entry in entries:
            title = clean_text(entry.findtext("a:title", default="", namespaces=ns) or entry.findtext("title"))
            summary = clean_text(entry.findtext("a:summary", default="", namespaces=ns) or entry.findtext("summary"))
            href = ""
            for link in entry.findall("a:link", ns) + entry.findall("link"):
                candidate = link.attrib.get("href", "")
                rel = link.attrib.get("rel", "alternate")
                if candidate and rel in {"alternate", ""}:
                    href = candidate
                    break
                href = href or candidate
            published_at = parse_date(entry.findtext("a:published", default="", namespaces=ns) or entry.findtext("a:updated", default="", namespaces=ns) or "")
            if title and href:
                items.append(Item(section, "", title, absolute_url(url, href), source_name, source_weight, format_date(published_at), published_at, feed_kind, summary))
        return items

    for entry in root.findall(".//item"):
        title = clean_text(entry.findtext("title"))
        link = clean_text(entry.findtext("link"))
        summary = clean_text(entry.findtext("description"))
        published_at = parse_date(clean_text(entry.findtext("pubDate") or entry.findtext("date") or entry.findtext("published")))
        if title and link:
            items.append(Item(section, "", title, absolute_url(url, link), source_name, source_weight, format_date(published_at), published_at, feed_kind, summary))
    return items


def strip_tracking(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    keep = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if not key.lower().startswith(("utm_", "fbclid", "gclid")):
            keep.append((key, value))
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(keep), fragment=""))




def source_context(source: dict) -> str:
    parts = []
    for key, label in (("region", "Region"), ("eligibility", "Eligibility"), ("note", "Note")):
        value = clean_text(source.get(key))
        if value:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)


def collect_html_links(section: str, source: dict, keywords: list[str], limit: int = 18) -> list[Item]:
    source_name = source.get("name", "Source")
    source_weight = int(source.get("weight", 1))
    url = source["url"]
    html = fetch_text(url)
    links = re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S)
    items: list[Item] = []
    seen: set[str] = set()
    for href, label_html in links:
        title = clean_text(label_html)
        if len(title) < 8 or len(title) > 190:
            continue
        haystack = title.lower()
        if keywords and not any(word in haystack for word in keywords):
            continue
        link = strip_tracking(absolute_url(url, href))
        key = urllib.parse.urlparse(link)._replace(query="", fragment="").geturl()
        if key in seen:
            continue
        seen.add(key)
        summary = source_context(source)
        items.append(Item(section, "", title, link, source_name, source_weight, "unknown", None, source.get("type", "html"), summary))
        if len(items) >= limit:
            break
    return items


def collect_json_jobs(section: str, source: dict, settings: dict) -> list[Item]:
    source_name = source.get("name", "Jobs")
    source_weight = int(source.get("weight", 1))
    url = source["url"]
    data = json.loads(fetch_text(url))
    records = data.get("hits", {}).get("hits", []) if isinstance(data, dict) else []
    items: list[Item] = []
    for record in records:
        meta = record.get("metadata", {}) if isinstance(record, dict) else {}
        title = clean_text(meta.get("position") or meta.get("title") or meta.get("name"))
        if not title:
            continue
        rec_id = record.get("id") or meta.get("control_number") or ""
        link = f"https://inspirehep.net/jobs/{rec_id}" if rec_id else url
        deadline = clean_text(meta.get("deadline_date") or meta.get("deadline") or "")
        institutions = meta.get("institutions") or []
        place = ""
        if institutions and isinstance(institutions, list):
            place = clean_text(institutions[0].get("value") or institutions[0].get("name") or "")
        summary = " ".join(x for x in [place, f"Deadline: {deadline}" if deadline else "", source_context(source)] if x)
        items.append(Item(section, "", title, link, source_name, source_weight, deadline or "unknown", parse_date(deadline), source.get("type", "jobs"), summary))
    return items


def collect_html_jobs(section: str, source: dict, settings: dict) -> list[Item]:
    job_words = [
        "postdoc", "postdoctoral", "fellow", "fellowship", "scientist", "faculty", "assistant professor",
        "associate professor", "lecturer", "tenure", "research", "cosmology", "astrophysics", "astronomy", "gravity", "relativity",
    ]
    items = collect_html_links(section, source, job_words, limit=14)
    if not items:
        title = f"{source.get('name', 'Jobs')}: current cosmology, astrophysics, and physics opportunities page"
        items.append(Item(section, "", title, source["url"], source.get("name", "Jobs"), int(source.get("weight", 1)), "unknown", None, source.get("type", "jobs"), source_context(source)))
    return items


def collect_html_news(section: str, source: dict, settings: dict) -> list[Item]:
    news_words = [
        "cosmology", "cosmic", "universe", "galaxy", "galaxies", "dark matter", "dark energy", "cmb",
        "black hole", "gravitational", "euclid", "roman", "webb", "hubble", "inflation", "supernova",
    ]
    return collect_html_links(section, source, news_words, limit=12)


def source_public_url(source: dict) -> str:
    """Return a user-facing URL. For RSS/Atom/API sources, prefer the human page.

    This prevents generated posts from opening XML/API feeds when a feed is only
    used as a machine-readable input.
    """
    return clean_text(source.get("home_url") or source.get("public_url") or source.get("portal_url") or source.get("url"))


def portal_fallback(section: str, source: dict) -> list[Item]:
    if section == "news":
        title = f"{source.get('name', 'News source')}: current cosmology news source"
        summary_base = "Source retained; automated fetching may be blocked or temporarily unavailable."
    else:
        title = f"{source.get('name', 'Portal')}: current cosmology, astrophysics, and physics opportunities page"
        summary_base = "Portal retained because some job boards block automated fetching."
    context = source_context(source)
    summary = summary_base + (" " + context if context else "")
    return [Item(section, "", title, source_public_url(source), source.get("name", "Portal"), int(source.get("weight", 1)), "unknown", None, source.get("type", "portal"), summary)]


def collect_source(section: str, source: dict, settings: dict) -> list[Item]:
    kind = source.get("type", "rss")
    if kind in {"portal", "portal_fallback"}:
        return portal_fallback(section, source)
    if kind in {"rss", "atom"}:
        return collect_xml(section, source, kind)
    if kind == "json_jobs":
        return collect_json_jobs(section, source, settings)
    if kind == "html_news":
        return collect_html_news(section, source, settings)
    return collect_html_jobs(section, source, settings)




@contextmanager
def source_timeout(seconds: int):
    if not hasattr(signal, "SIGALRM") or seconds <= 0:
        yield
        return
    def handler(signum, frame):
        raise TimeoutError(f"source fetch exceeded {seconds}s")
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

def _should_show_fetch_warnings(settings: dict) -> bool:
    return str(settings.get("show_fetch_warnings", "false")).strip().lower() in {"1", "true", "yes", "on"}


def collect_all(news_sources: dict, job_sources: dict, settings: dict) -> list[Item]:
    all_items: list[Item] = []
    show_warnings = _should_show_fetch_warnings(settings)
    for _, sources in news_sources.items():
        for source in sources:
            try:
                with source_timeout(int(settings.get("fetch_timeout_seconds", 6))):
                    all_items.extend(collect_source("news", source, settings))
            except Exception as exc:
                if str(source.get("fallback_on_error", "true")).lower() in {"1", "true", "yes", "on"}:
                    all_items.extend(portal_fallback("news", source))
                if show_warnings:
                    print(f"Notice: using fallback for news source {source.get('name')}: {exc}", file=sys.stderr)
    for _, sources in job_sources.items():
        for source in sources:
            try:
                with source_timeout(int(settings.get("fetch_timeout_seconds", 6))):
                    all_items.extend(collect_source("jobs", source, settings))
            except Exception as exc:
                if str(source.get("fallback_on_error", "true")).lower() in {"1", "true", "yes", "on"}:
                    all_items.extend(portal_fallback("jobs", source))
                if show_warnings:
                    print(f"Notice: using fallback for job source {source.get('name')}: {exc}", file=sys.stderr)
    return all_items
