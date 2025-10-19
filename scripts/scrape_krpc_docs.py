import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple

import requests
import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

try:
    import sphobjinv as soi
except Exception:  # pragma: no cover - optional at runtime
    soi = None


DEFAULT_START = "https://krpc.github.io/krpc/python.html"
DEFAULT_BASE = "https://krpc.github.io/krpc/"
DEFAULT_INV = DEFAULT_BASE + "objects.inv"


@dataclass
class Page:
    url: str
    title: str
    headings: list
    anchors: list
    content_text: str


def is_html_url(url: str, base: str) -> bool:
    if not url.startswith(base):
        return False
    if any(url.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".zip", ".gz", ".css", ".js")):
        return False
    # Accept URLs ending with .html or without extension
    return True


def normalize_url(url: str) -> str:
    # Strip fragments and normalize duplicate slashes
    if "#" in url:
        url = url.split("#", 1)[0]
    # Remove trailing index.html redundancy
    if url.endswith("/index.html"):
        url = url[: -len("index.html")]
    return url


def discover_via_inventory(inv_url: str, base: str, session: requests.Session) -> Set[str]:
    pages: Set[str] = set()
    if soi is None:
        return pages
    try:
        # Download inventory via session to leverage caching
        r = session.get(inv_url, timeout=20)
        r.raise_for_status()
        inv = soi.Inventory(bytes=r.content)
        for obj in inv.objects:
            rel = obj.uri  # type: ignore[attr-defined]
            if not isinstance(rel, str):
                continue
            page = rel.split("#", 1)[0]
            if page.startswith("http://") or page.startswith("https://"):
                url = page
            else:
                url = base + page.lstrip("/")
            url = normalize_url(url)
            if is_html_url(url, base):
                pages.add(url)
    except Exception:
        # On any error, return empty set to trigger fallback
        return set()
    return pages


def extract_links(html: str, page_url: str, base: str) -> Iterable[str]:
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        # Resolve relative links
        if href.startswith("http://") or href.startswith("https://"):
            url = href
        else:
            # Simple resolution
            if href.startswith("/"):
                url = base.rstrip("/") + href
            else:
                # Join relative to current page
                if page_url.endswith("/"):
                    url = page_url + href
                else:
                    url = page_url.rsplit("/", 1)[0] + "/" + href
        url = normalize_url(url)
        if is_html_url(url, base):
            yield url


def select_main_container(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    candidates = [
        soup.find("main"),
        soup.find("div", attrs={"role": "main"}),
        soup.select_one("div.document"),
        soup.select_one("div.body"),
        soup.find("article"),
    ]
    for c in candidates:
        if c:
            return c
    return soup.body or soup


def clean_container(container: BeautifulSoup) -> None:
    # Remove nav/aside/footer/sidebar/toc elements within container
    for selector in [
        "nav",
        "header",
        "footer",
        "aside",
        ".sphinxsidebar",
        ".related",
        ".toc",
        "div[role='navigation']",
        "ul.breadcrumbs",
    ]:
        for node in container.select(selector):
            node.decompose()


def extract_page(url: str, html: str) -> Page:
    soup = BeautifulSoup(html, "lxml")
    container = select_main_container(soup)
    assert container is not None
    clean_container(container)

    # Title: prefer h1 in container; fallback to <title>
    h1 = container.find("h1")
    title = (h1.get_text(strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else url))

    # Headings h2-h4
    headings = [h.get_text(strip=True) for h in container.select("h2, h3, h4")]

    # Anchors
    anchors = []
    for el in container.find_all(True):
        if el.has_attr("id"):
            anchors.append(str(el["id"]))

    # Text content
    content_text = container.get_text("\n", strip=True)

    return Page(url=url, title=title, headings=headings, anchors=anchors, content_text=content_text)


def bfs_crawl(start_url: str, base: str, session: requests.Session, throttle: float, max_pages: int, timeout: int) -> Tuple[dict, list]:
    visited: Set[str] = set()
    queue: list[str] = [normalize_url(start_url)]
    pages: list[Page] = []
    errors: dict = {}

    with tqdm(total=max_pages, desc="Crawl", unit="page") as pbar:
        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                resp = session.get(url, timeout=timeout)
                if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                    continue
                page = extract_page(url, resp.text)
                pages.append(page)
                pbar.update(1)
                # Enqueue links
                for link in extract_links(resp.text, url, base):
                    if link not in visited and link not in queue:
                        queue.append(link)
                time.sleep(throttle)
            except Exception as e:  # pragma: no cover - runtime variability
                errors[url] = str(e)
                continue
    return errors, pages


def write_dataset(out_path: Path, pages: list[Page]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for p in pages:
            obj = {
                "url": p.url,
                "title": p.title,
                "headings": p.headings,
                "anchors": p.anchors,
                "content_text": p.content_text,
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape kRPC Python docs and build a JSONL dataset")
    parser.add_argument("--start", default=DEFAULT_START, help="Seed page URL")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Docs base URL (prefix for allowed links)")
    parser.add_argument("--out", default="data/krpc_python_docs.jsonl", help="Output JSONL path")
    parser.add_argument("--no-inventory", action="store_true", help="Disable objects.inv discovery and force BFS crawl")
    parser.add_argument("--throttle", type=float, default=0.5, help="Delay between requests (seconds)")
    parser.add_argument("--max-pages", type=int, default=500, help="Maximum pages to fetch during BFS crawl")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout (seconds)")
    args = parser.parse_args(argv)

    base = args.base if args.base.endswith("/") else (args.base + "/")
    inv_url = base + "objects.inv"

    # HTTP session with caching
    requests_cache.install_cache("krpc_docs_cache", expire_after=24 * 3600)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "krpc-docs-scraper/0.1 (+https://github.com/)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    # 1) Try inventory discovery
    pages_set: Set[str] = set()
    method = "inventory"
    if not args.no_inventory:
        pages_set = discover_via_inventory(inv_url, base, session)

    pages: list[Page] = []
    errors: dict = {}
    if pages_set:
        # Fetch each page once
        for url in tqdm(sorted(pages_set), desc="Fetch", unit="page"):
            try:
                r = session.get(url, timeout=args.timeout)
                if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
                    continue
                pages.append(extract_page(url, r.text))
                time.sleep(args.throttle)
            except Exception as e:  # pragma: no cover - runtime variability
                errors[url] = str(e)
                continue
    else:
        # 2) Fallback BFS crawl
        method = "crawl"
        errors, pages = bfs_crawl(args.start, base, session, throttle=args.throttle, max_pages=args.max_pages, timeout=args.timeout)

    # Write dataset
    out_path = Path(args.out)
    write_dataset(out_path, pages)

    # Manifest
    manifest = {
        "source": base,
        "start": args.start,
        "method": method,
        "pages": len(pages),
        "errors": len(errors),
    }
    man_path = out_path.parent / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps(manifest, indent=2))
    if errors:
        # Write errors for inspection
        (out_path.parent / "errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

