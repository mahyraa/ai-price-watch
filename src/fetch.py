"""Fetch a pricing page and reduce it to clean text.

Deliberately boring: one GET, a real User-Agent, a couple of retries, then strip
the page down to visible text. We do NOT try to parse prices here — the HTML
structure of a pricing page changes constantly, and every provider does it
differently. Parsing is left to extract.py, which is structure-agnostic.
"""

from __future__ import annotations

import re
import time

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 ai-price-watch/1.0"
)

# Pages carry a lot of chrome (nav, cookie banners, footers). We keep it simple
# and strip only the tags that are never content, then collapse whitespace.
STRIP_TAGS = ["script", "style", "noscript", "svg", "iframe"]

MAX_CHARS = 60_000  # keep the LLM call bounded and cheap


class FetchError(Exception):
    pass


def fetch_text(url: str, *, retries: int = 3, timeout: float = 30.0) -> str:
    """GET a URL and return its visible text. Raises FetchError on failure."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            response = httpx.get(
                url, headers=headers, timeout=timeout, follow_redirects=True
            )
            response.raise_for_status()
            return _to_text(response.text)
        except Exception as exc:  # noqa: BLE001 - we retry on anything transient
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2**attempt)  # 1s, 2s, 4s

    raise FetchError(f"could not fetch {url}: {last_error}")


def _to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(STRIP_TAGS):
        tag.decompose()
    text = soup.get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CHARS]
