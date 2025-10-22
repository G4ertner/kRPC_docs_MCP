from __future__ import annotations

from typing import List

from .server import mcp
from .ksp_wiki_client import KspWikiClient


_client: KspWikiClient | None = None


def _get_client() -> KspWikiClient:
    global _client
    if _client is None:
        _client = KspWikiClient()
    return _client


@mcp.tool()
def search_ksp_wiki(query: str, limit: int = 10) -> str:
    """
    Search the KSP Wiki (English) and return the top results.

    Args:
        query: Search query text
        limit: Max results to return (default 10)
    Returns:
        Newline-delimited items: "- Title — URL" with a short snippet below.
    """
    client = _get_client()
    items = client.search(query, limit=limit)
    if not items:
        return "No results found."
    lines: List[str] = []
    for it in items:
        if it.snippet:
            lines.append(f"- {it.title} — {it.url}\n  {it.snippet}")
        else:
            lines.append(f"- {it.title} — {it.url}")
    return "\n".join(lines)


@mcp.tool()
def get_ksp_wiki_page(title: str, max_chars: int = 5000) -> str:
    """
    Fetch a KSP Wiki page in plain text (English).

    Args:
        title: Page title (e.g., "Delta-v")
        max_chars: Truncate returned text to this many characters (default 5000)
    Returns:
        Title, canonical URL, and plain text (truncated).
    """
    client = _get_client()
    body = client.get_page(title)
    if not body:
        return "Page not found."
    if len(body) > max_chars:
        body = body[: max_chars - 1].rstrip() + "…"
    url = f"https://wiki.kerbalspaceprogram.com/wiki/{title.replace(' ', '_')}"
    return f"{title}\n{url}\n\n{body}"

