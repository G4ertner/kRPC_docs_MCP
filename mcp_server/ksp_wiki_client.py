from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import List, Optional

import requests


BASE = "https://wiki.kerbalspaceprogram.com"  # English wiki
API = f"{BASE}/api.php"
REST_PLAIN = f"{BASE}/api/rest_v1/page/plain"


_UA = "krpc-docs-mcp/0.1 (+https://github.com/G4ertner/kRPC_docs_MCP)"


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    # Remove tags and decode HTML entities
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def _title_to_path(title: str) -> str:
    # Convert a MediaWiki title to URL path component (spaces -> underscores)
    return title.replace(" ", "_")


@dataclass
class WikiSearchResult:
    title: str
    url: str
    snippet: str


class KspWikiClient:
    def __init__(self, throttle: float = 0.25, timeout: int = 15):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": _UA,
            "Accept": "application/json",
        })
        self.throttle = throttle
        self.timeout = timeout

    def search(self, query: str, limit: int = 10) -> List[WikiSearchResult]:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max(1, min(limit, 25)),
            "utf8": 1,
            "format": "json",
            "srprop": "snippet",
        }
        r = self.session.get(API, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json() or {}
        results = []
        for item in (data.get("query", {}).get("search", []) or [])[: limit]:
            title = item.get("title", "").strip()
            snippet = _strip_html(item.get("snippet", ""))
            url = f"{BASE}/wiki/{_title_to_path(title)}"
            if title:
                results.append(WikiSearchResult(title=title, url=url, snippet=snippet))
        time.sleep(self.throttle)
        return results

    def get_page(self, title: str) -> Optional[str]:
        # Try action=query extracts first
        params = {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "exsectionformat": "plain",
            "redirects": 1,
            "titles": title,
            "format": "json",
        }
        r = self.session.get(API, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json() or {}
        pages = (data.get("query", {}).get("pages", {}) or {})
        if isinstance(pages, dict) and pages:
            # Get first page object
            for p in pages.values():
                extract = p.get("extract") if isinstance(p, dict) else None
                if extract:
                    time.sleep(self.throttle)
                    return str(extract)

        # Fallback: REST plain endpoint
        rest_url = f"{REST_PLAIN}/{_title_to_path(title)}"
        r2 = self.session.get(rest_url, timeout=self.timeout)
        if r2.status_code == 200:
            time.sleep(self.throttle)
            return r2.text
        return None

