import argparse
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server.ksp_wiki_client import KspWikiClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Query the KSP Wiki (English)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search wiki")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=5)

    p_get = sub.add_parser("get", help="Get page text")
    p_get.add_argument("title")
    p_get.add_argument("--max-chars", type=int, default=600)

    args = ap.parse_args()
    client = KspWikiClient()

    if args.cmd == "search":
        for r in client.search(args.query, limit=args.limit):
            print(f"- {r.title} — {r.url}\n  {r.snippet}")
        return 0
    elif args.cmd == "get":
        text = client.get_page(args.title)
        if not text:
            print("Page not found")
            return 1
        if len(text) > args.max_chars:
            text = text[: args.max_chars - 1].rstrip() + "…"
        print(text)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

