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
    When to use:
        - Gather background on KSP mechanics, parts, or gameplay concepts.

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
    When to use:
        - Read a complete article for deeper context or guidance.

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


@mcp.tool()
def get_ksp_wiki_section(title: str, heading: str, max_chars: int = 3000) -> str:
    """
    Fetch a specific section from a KSP Wiki page (English).
    When to use:
        - Retrieve a focused subsection (e.g., a usage guide) quickly.

    Args:
        title: Page title (e.g., "Maneuver node")
        heading: Section heading to fetch (case-insensitive)
        max_chars: Max characters to return (default 3000)
    Returns:
        Title + section heading + canonical URL and the section text, or a not-found message.
    """
    client = _get_client()
    text = client.get_section(title, heading)
    if not text:
        # Provide available sections hint
        secs = client.list_sections(title)
        if not secs:
            return "Section not found."
        names = ", ".join(s for _, s in secs[:10])
        return f"Section not found. Available sections include: {names}"
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    url = f"https://wiki.kerbalspaceprogram.com/wiki/{title.replace(' ', '_')}#{heading.replace(' ', '_')}"
    return f"{title} — {heading}\n{url}\n\n{text}"
