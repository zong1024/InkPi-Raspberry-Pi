"""Validate the miniapp manifest and release-facing config."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse


PROJECT_DIR = Path(__file__).resolve().parent.parent
MINIAPP_DIR = PROJECT_DIR / "miniapp"
APP_JSON = MINIAPP_DIR / "app.json"
CONFIG_JS = MINIAPP_DIR / "config.js"


def load_pages() -> list[str]:
    payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("miniapp/app.json must declare a non-empty pages array")
    return [str(item) for item in pages]


def assert_page_files(page_name: str) -> None:
    base_path = MINIAPP_DIR / page_name
    required_suffixes = (".js", ".wxml", ".wxss")
    missing = [str(base_path.with_suffix(suffix).relative_to(PROJECT_DIR)) for suffix in required_suffixes if not base_path.with_suffix(suffix).exists()]
    if missing:
        raise ValueError(f"miniapp page is missing required files: {', '.join(missing)}")


def load_api_base_url() -> str:
    match = re.search(
        r"API_BASE_URL\s*=\s*['\"](?P<value>[^'\"]+)['\"]",
        CONFIG_JS.read_text(encoding="utf-8"),
    )
    if not match:
        raise ValueError("miniapp/config.js must define API_BASE_URL")
    return match.group("value").strip()


def validate_api_base_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"miniapp/config.js API_BASE_URL is invalid: {url}")
    forbidden_hosts = {"127.0.0.1", "localhost", "0.0.0.0"}
    if parsed.hostname in forbidden_hosts:
        raise ValueError(f"miniapp/config.js API_BASE_URL must not point to a local host in release mode: {url}")


def main() -> int:
    pages = load_pages()
    for page_name in pages:
        assert_page_files(page_name)

    validate_api_base_url(load_api_base_url())
    print(f"PASS miniapp release validation ({len(pages)} pages)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
