from __future__ import annotations

import re
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests import Response

# ---- Tunables ---------------------------------------------------------------

BLOCK_TAGS = {
    "script", "style", "noscript", "template", "iframe", "svg", "canvas",
    "header", "footer", "nav"
}

HIDDEN_SELECTORS = (
    '[hidden], [aria-hidden="true"], [style*="display:none"], '
    '[style*="visibility:hidden"], [style*="opacity:0"]'
)

MIN_CHARS_PER_LINE = 30  # skip tiny crumbs like menus/toolbars

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---- Exceptions -------------------------------------------------------------

class SkippedArticle(Exception):
    """Raised when the article should be skipped (paywall/blocked)."""


# ---- Core helpers -----------------------------------------------------------

def _fix_encoding(resp: Response) -> None:
    """Ensure response.text uses a sensible encoding."""
    enc = (resp.encoding or "").lower()
    if not enc or enc == "iso-8859-1":
        resp.encoding = resp.apparent_encoding


def fetch_html(url: str, timeout: int = 15) -> str:
    """Fetch HTML, raising SkippedArticle for common block/paywall statuses."""
    with requests.Session() as s:
        s.headers.update(DEFAULT_HEADERS)
        r = s.get(url, timeout=timeout)
        if r.status_code in {401, 402, 403, 451}:
            # Blocked, paywalled, or legally restricted
            raise SkippedArticle(f"Skipped (HTTP {r.status_code}): access not permitted.")
        r.raise_for_status()
        _fix_encoding(r)
        return r.text


def extract_readable_text(html: str) -> str:
    """Remove boilerplate/hidden elements and return cleaned visible text."""
    soup = BeautifulSoup(html, "lxml")

    # Remove obvious non-content blocks
    for tag in soup.find_all(BLOCK_TAGS):
        tag.decompose()

    # Remove elements hidden via attributes/inline CSS
    for el in soup.select(HIDDEN_SELECTORS):
        el.decompose()

    # Quick heuristic: bail if the page is clearly a paywall/tease
    page_text_lower = soup.get_text(" ", strip=True).lower()
    paywall_markers = (
        "subscribe", "subscription", "subscriber-only", "for subscribers",
        "log in to continue", "sign in to continue", "metered", "paywall"
    )
    if any(m in page_text_lower for m in paywall_markers):
        raise SkippedArticle("Skipped: detected paywall copy in page.")

    # Extract and tidy text
    raw = soup.get_text(separator="\n")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw.splitlines()]
    # Keep only lines that look like real content
    lines = [
        ln for ln in lines
        if ln and len(ln) >= MIN_CHARS_PER_LINE and any(c.isalpha() for c in ln)
    ]

    # Deduplicate consecutive lines
    deduped = []
    for ln in lines:
        if not deduped or ln != deduped[-1]:
            deduped.append(ln)

    return "\n".join(deduped)


def get_all_text_from_url(url: str, timeout: int = 15) -> str:
    """Top-level convenience function."""
    html = fetch_html(url, timeout=timeout)
    return extract_readable_text(html)


# ---- CLI entry --------------------------------------------------------------

if __name__ == "__main__":
    url = "https://www.ctvnews.ca/canada/newfoundland-and-labrador/article/amid-nl-wildfire-evacuations-thousands-are-on-notice-near-st-johns/"

    try:
        print(get_all_text_from_url(url))
    except SkippedArticle as e:
        print(str(e))
        sys.exit(0)
    except requests.Timeout:
        print("Skipped: page load timeout.")
        sys.exit(0)
    except requests.RequestException as e:
        print(f"Skipped: network error - {e}")
        sys.exit(0)
    except Exception as e:
        print(f"Skipped: unexpected error - {type(e).__name__}: {e}")
        sys.exit(0)
