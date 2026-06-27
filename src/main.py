#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

try:
    from .ai import fallback_digest, gemini_digest
    from .common import API_KEY_ENV, ensure_dirs, load_settings, load_sources, read_env_file
    from .fetch import collect_all
    from .filter import select_items
    from .markdown import write_post
except ImportError:
    from ai import fallback_digest, gemini_digest
    from common import API_KEY_ENV, ensure_dirs, load_settings, load_sources, read_env_file
    from fetch import collect_all
    from filter import select_items
    from markdown import write_post


def generate(use_ai: bool = True) -> str:
    read_env_file()
    ensure_dirs()
    settings = load_settings()
    news_sources = load_sources("news_sources.yml")
    job_sources = load_sources("job_sources.yml")
    collected = collect_all(news_sources, job_sources, settings)
    selected = select_items(collected, settings)

    if use_ai and os.environ.get(API_KEY_ENV):
        settings["used_ai"] = True
        try:
            digest = gemini_digest(selected, os.environ[API_KEY_ENV], settings)
        except Exception as exc:
            print(f"Warning: Gemini failed; using fallback digest: {exc}", file=sys.stderr)
            settings["used_ai"] = False
            digest = fallback_digest(selected, settings)
    else:
        settings["used_ai"] = False
        digest = fallback_digest(selected, settings)
    return write_post(digest, selected, settings)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a cosmology news and academic jobs brief.")
    parser.add_argument("command", nargs="?", default="generate", choices=["generate", "no-ai"], help="generate uses Gemini when COSMOLOGY_API_KEY is set; no-ai always uses fallback output")
    args = parser.parse_args()
    path = generate(use_ai=args.command != "no-ai")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
