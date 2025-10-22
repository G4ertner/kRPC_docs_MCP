from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
import difflib
from typing import List, Optional

import requests
try:  # optional runtime cache
    import requests_cache  # type: ignore
except Exception:  # pragma: no cover
    requests_cache = None  # type: ignore


BASE = "https://wiki.kerbalspaceprogram.com"  # English wiki
API = f"{BASE}/api.php"
REST_PLAIN = f"{BASE}/api/rest_v1/page/plain"


_UA = "krpc-docs-mcp/0.1 (+https://github.com/G4ertner/kRPC_docs_MCP)"

# Known language code suffixes (lowercase) to exclude from English-only results
_LANG_SUFFIXES = {
    "af","ar","bg","bn","ca","cs","da","de","el","es","et","eu","fa","fi","fr","gl","he","hi","hr","hu","id","it","ja","ko","lt","lv","ms","mt","nl","no","pl","pt","ro","ru","sk","sl","sq","sr","sv","ta","th","tr","uk","ur","vi","zh","zh-cn","zh-tw","pt-br"
}
_LANG_CODE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z]{2})?$")


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


def _is_english_title(title: str) -> bool:
    # Accept if there's no subpage
    if "/" not in title:
        return True
    last = title.rsplit("/", 1)[-1].strip().lower()
    # If the last segment looks like a language code, exclude
    if last in _LANG_SUFFIXES or _LANG_CODE_RE.fullmatch(last):
        return False
    return True


class KspWikiClient:
    def __init__(self, throttle: float = 0.25, timeout: int = 15):
        if requests_cache is not None:
            # Cache GET responses for 24h to reduce network load
            self.session = requests_cache.CachedSession(
                "ksp_wiki_cache",
                expire_after=24 * 3600,
                allowable_methods=("GET",),
            )
        else:
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
        for item in (data.get("query", {}).get("search", []) or [])[: limit * 2]:
            title = item.get("title", "").strip()
            snippet = _strip_html(item.get("snippet", ""))
            url = f"{BASE}/wiki/{_title_to_path(title)}"
            if title and _is_english_title(title):
                results.append(WikiSearchResult(title=title, url=url, snippet=snippet))
            if len(results) >= limit:
                break
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

    def list_sections(self, title: str) -> list[tuple[str, str]]:
        """Return a list of (index, line) section descriptors for a page.

        Uses action=parse with prop=sections. Returns an empty list if unavailable.
        """
        params = {
            "action": "parse",
            "page": title,
            "prop": "sections",
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        }
        r = self.session.get(API, params=params, timeout=self.timeout)
        if r.status_code != 200:
            return []
        data = r.json() or {}
        sections = data.get("parse", {}).get("sections", []) or []
        out: list[tuple[str, str]] = []
        for s in sections:
            idx = str(s.get("index"))
            line = str(s.get("line", "")).strip()
            if idx and line:
                out.append((idx, line))
        time.sleep(self.throttle)
        return out

    def get_section(self, title: str, heading: str) -> Optional[str]:
        """Fetch a specific section by heading name.

        Matches case-insensitive; prefers exact match, otherwise first contains-match.
        Returns plain text or None if not found.
        """
        sections = self.list_sections(title)
        if not sections:
            return None
        h_norm = heading.strip().lower()

        # Numeric index support
        if h_norm.isdigit():
            for idx, _line in sections:
                if idx == h_norm:
                    chosen_idx = idx
                    break

        # Exact match
        chosen_idx: Optional[str] = None
        if chosen_idx is None:
            for idx, line in sections:
                ln = line.lower().strip()
                if ln == h_norm:
                    chosen_idx = idx
                    break
        # Contains (both ways)
        if chosen_idx is None:
            for idx, line in sections:
                ln = line.lower().strip()
                if h_norm in ln or ln in h_norm:
                    chosen_idx = idx
                    break
        # Fuzzy best match
        if chosen_idx is None:
            labels = [line for _idx, line in sections]
            best = difflib.get_close_matches(heading, labels, n=1, cutoff=0.6)
            if best:
                best_label = best[0]
                for idx, line in sections:
                    if line == best_label:
                        chosen_idx = idx
                        break
        if chosen_idx is None:
            return None

        params = {
            "action": "parse",
            "page": title,
            "prop": "text",
            "section": chosen_idx,
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        }
        r = self.session.get(API, params=params, timeout=self.timeout)
        if r.status_code != 200:
            return None
        data = r.json() or {}
        html_text = (data.get("parse", {}).get("text", "") or "")
        if not isinstance(html_text, str):
            return None
        time.sleep(self.throttle)
        return _strip_html(html_text)
