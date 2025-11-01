"""Command-line interface for the krpc-snippets project.

Usage:
    uv --directory krpc-snippets run -m krpc_snippets.cli --help

Subcommands (stubs):
    ingest         Ingest repositories and extract snippets (not implemented)
    enrich         Summarise/tag snippets using an LLM (not implemented)
    index          Build keyword/vector indices (not implemented)
    search         Keyword search over snippets (not implemented)
    search-hybrid  Hybrid search (keyword + vector) (not implemented)
    resolve        Resolve a snippet and its dependencies (not implemented)
"""

from __future__ import annotations

import argparse
from typing import List, Optional


def _add_subcommands(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="cmd", metavar="command")

    # ingest
    p_ingest = sub.add_parser(
        "ingest",
        help="Ingest repositories and extract snippets (stub)",
    )
    p_ingest.add_argument("repo", nargs="?", help="Repository URL (e.g., https://github.com/user/repo)")
    p_ingest.add_argument("--branch", dest="branch", default=None, help="Branch name")
    p_ingest.add_argument("--sha", dest="sha", default=None, help="Commit SHA")

    # enrich
    sub.add_parser(
        "enrich",
        help="Summarise and tag snippets (stub)",
    )

    # index
    sub.add_parser(
        "index",
        help="Build keyword/vector indices (stub)",
    )

    # search
    p_search = sub.add_parser(
        "search",
        help="Keyword search over snippets (stub)",
    )
    p_search.add_argument("query", nargs=argparse.REMAINDER, help="Query terms")

    # search-hybrid
    p_search_h = sub.add_parser(
        "search-hybrid",
        help="Hybrid search (keyword + vector) (stub)",
    )
    p_search_h.add_argument("query", nargs=argparse.REMAINDER, help="Query terms")

    # resolve
    p_resolve = sub.add_parser(
        "resolve",
        help="Resolve a snippet and its dependencies (stub)",
    )
    p_resolve.add_argument("id", help="Snippet identifier")


def _print_stub(name: str) -> None:
    print(f"krpc-snippets: '{name}' is not implemented yet. See project plan for milestones.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="krpc-snippets",
        description=(
            "kRPC Snippet RAG — ingestion, enrichment, indexing, search, and resolution.\n"
            "Use subcommands to explore the pipeline; most are stubs in A1."
        ),
        epilog=(
            "Examples:\n"
            "  uv --directory krpc-snippets run -m krpc_snippets.cli search autopilot\n"
            "  uv --directory krpc-snippets run -m krpc_snippets.cli search-hybrid \"circularise orbit\"\n"
            "  uv --directory krpc-snippets run -m krpc_snippets.cli resolve <snippet_id>\n"
        ),
    )
    _add_subcommands(parser)
    args = parser.parse_args(argv)

    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0

    cmd = args.cmd
    if cmd in {"ingest", "enrich", "index", "search", "search-hybrid", "resolve"}:
        _print_stub(cmd)
        return 0

    parser.error(f"Unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

