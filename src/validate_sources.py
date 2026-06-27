#!/usr/bin/env python3
from __future__ import annotations

import sys

try:
    from .common import load_sources
    from .fetch import fetch_text
except ImportError:
    from common import load_sources
    from fetch import fetch_text


def check_url(name: str, url: str, source_type: str) -> tuple[str, str]:
    if source_type in {"portal", "portal_fallback"}:
        return "SKIP", "Portal-only source; intentionally not fetched during generation."
    try:
        text = fetch_text(url)
        sample = text[:100].replace("\n", " ").replace("\r", " ")
        return "OK", sample
    except Exception as exc:
        return "FAIL", repr(exc)


def iter_sources():
    for filename in ("news_sources.yml", "job_sources.yml"):
        for group, sources in load_sources(filename).items():
            for source in sources:
                yield filename, group, source.get("name", "Unnamed"), source.get("url", ""), source.get("type", "")


def main() -> None:
    failures = 0
    for filename, group, name, url, source_type in iter_sources():
        status, msg = check_url(name, url, source_type)
        print(f"[{status}] {filename}/{group}: {name} -> {url} :: {msg[:160]}")
        if status == "FAIL":
            failures += 1
    if failures:
        print(f"\n{failures} actively fetched source(s) failed. Portal-only sources are skipped by design.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
