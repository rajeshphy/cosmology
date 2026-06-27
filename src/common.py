from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
POSTS = ROOT / "docs" / "_posts"
DATA = ROOT / "data"
IST = ZoneInfo("Asia/Kolkata")
GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
API_KEY_ENV = "COSMOLOGY_API_KEY"

@dataclass
class Item:
    section: str
    item_id: str
    title: str
    url: str
    source: str = ""
    source_weight: int = 1
    published: str = "unknown"
    published_at: datetime | None = None
    kind: str = ""
    summary: str = ""


def clean_text(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def read_env_file() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_yaml_value(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        return value


def parse_simple_yaml(path: Path) -> dict:
    """Fallback YAML parser for the simple config shape used here."""
    root: dict = {}
    stack: list[tuple[int, object]] = [(-1, root)]

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if text.startswith("- "):
            item_text = text[2:].strip()
            if not isinstance(parent, list):
                continue
            item: dict = {}
            parent.append(item)
            if ":" in item_text:
                key, value = item_text.split(":", 1)
                item[key.strip()] = parse_yaml_value(value)
            stack.append((indent, item))
            continue

        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            container: object = [] if key not in {"sources", "settings", "news", "jobs"} and isinstance(parent, dict) else {}
            if isinstance(parent, dict):
                parent[key] = container
                stack.append((indent, container))
        else:
            if isinstance(parent, dict):
                parent[key] = parse_yaml_value(value)
    return root


def read_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data or {}
    except Exception:
        return parse_simple_yaml(path)


def load_project_config() -> dict:
    combined = CONFIG / "sources.yml"
    if combined.exists():
        return read_yaml(combined)
    return {
        "settings": read_yaml(CONFIG / "settings.yml"),
        "sources": {
            "news": read_yaml(CONFIG / "news_sources.yml").get("sources", {}),
            "jobs": read_yaml(CONFIG / "job_sources.yml").get("sources", {}),
        },
    }


def load_settings() -> dict:
    return load_project_config().get("settings", {})


def load_sources(filename: str) -> dict:
    project = load_project_config()
    sources = project.get("sources", {})
    if filename == "news_sources.yml":
        return sources.get("news", {})
    if filename == "job_sources.yml":
        return sources.get("jobs", {})
    return read_yaml(CONFIG / filename).get("sources", {})


def config_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def csv_keywords(raw: str | None) -> list[str]:
    return [clean_text(x).lower() for x in str(raw or "").split(",") if clean_text(x)]


def format_date(value: datetime | None) -> str:
    if not value:
        return "unknown"
    return value.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")


def now_ist() -> datetime:
    return datetime.now(IST)


def ensure_dirs() -> None:
    POSTS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
