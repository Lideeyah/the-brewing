"""Real tools agents can call during execution.

Today: ``fetch_url`` — a live HTTP GET. Each fetch yields verifiable
proof-of-work: the resolved URL, a sha256 of the retrieved text, a title, and a
byte count, captured on the execution run so the deliverable's claims are
grounded in content that was actually retrieved (not the model's memory).
"""

from __future__ import annotations

import hashlib
import html as _html
import re
from datetime import datetime, timezone

import httpx

_TIMEOUT = 9.0
_MAX_TEXT = 40_000  # cap returned text so a page can't blow the context window
_UA = "BrewingAgent/1.0 (+https://the-brewing.vercel.app)"

# The tool schema handed to the model.
FETCH_URL_TOOL = {
    "name": "fetch_url",
    "description": (
        "Fetch the live text content of a web page by URL. Use this to gather "
        "current, real data and sources before writing — do not rely on memory "
        "for figures, prices, or dates. Returns the page's extracted text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Absolute http(s) URL to fetch."}
        },
        "required": ["url"],
    },
}


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|head)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", _html.unescape(raw)).strip()


def _title(raw: str) -> str | None:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    return re.sub(r"\s+", " ", _html.unescape(m.group(1))).strip()[:200] if m else None


async def fetch_url(url: str) -> dict:
    """Fetch a URL. Returns a proof-of-work record (never raises)."""
    started = datetime.now(timezone.utc).isoformat()
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        return {"url": str(url), "ok": False, "error": "invalid url", "fetched_at": started, "text": ""}
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, follow_redirects=True, headers={"User-Agent": _UA}
        ) as client:
            resp = await client.get(url)
        ctype = resp.headers.get("content-type", "")
        raw = resp.text
        text = _strip_html(raw) if "html" in ctype or "<" in raw[:200] else raw.strip()
        text = text[:_MAX_TEXT]
        digest = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
        return {
            "url": str(resp.url),
            "ok": resp.status_code < 400,
            "status": resp.status_code,
            "title": _title(raw),
            "sha256": digest,
            "bytes": len(text),
            "fetched_at": started,
            "text": text,
        }
    except Exception as exc:  # noqa: BLE001 — a failed fetch is data, not a crash
        return {"url": url, "ok": False, "error": str(exc)[:200], "fetched_at": started, "text": ""}
