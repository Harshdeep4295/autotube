"""
Fetch readable text from a topic's source URL (stdlib HTML parsing, no extra deps).

The script prompt is grounded in this text: the model may only use specific facts
and numbers that appear here. Failure is non-fatal — the caller falls back to the
feed summary.
"""

import html
import logging
import re
from html.parser import HTMLParser
from typing import List

import requests

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; AutoTubeResearch/1.0; +https://github.com/)"
KEEP = {"p", "h1", "h2", "h3", "li", "pre", "blockquote", "td"}
SKIP = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"}


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._buf: List[str] = []
        self._keep = 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self._skip += 1
        elif tag in KEEP:
            self._keep += 1

    def handle_endtag(self, tag):
        if tag in SKIP and self._skip:
            self._skip -= 1
        elif tag in KEEP and self._keep:
            self._keep -= 1
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if len(text) > 30:
                self.parts.append(text)
            self._buf = []

    def handle_data(self, data):
        if self._keep and not self._skip:
            self._buf.append(data)


def html_to_text(page: str, limit: int = 6000) -> str:
    p = _TextParser()
    try:
        p.feed(page)
    except Exception:  # noqa: BLE001 — malformed HTML: keep what we got
        pass
    out, seen = [], set()
    for part in p.parts:
        if part not in seen:
            seen.add(part)
            out.append(part)
    return html.unescape("\n".join(out))[:limit]


def fetch_text(url: str, limit: int = 6000, timeout: float = 15) -> str:
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "html" in ctype:
            return html_to_text(r.text, limit)
        if "text/plain" in ctype or "markdown" in ctype:
            return r.text[:limit]
        return ""
    except Exception as e:  # noqa: BLE001
        logger.info(f"source fetch failed for {url[:80]}: {str(e)[:120]}")
        return ""
