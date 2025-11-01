#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, List

from krpc_snippets.ingest.walk_repo import (
    WalkOptions,
    discover_python_files,
    default_exclude_dirs,
)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Walk a repository and list Python files for ingestion")
    p.add_argument("--root", required=True, help="Repository root path")
    p.add_argument("--use-git", action="store_true", help="Prefer git ls-files when available")
    p.add_argument("--max-size", type=int, default=None, help="Max file size in bytes")
    p.add_argument("--include", action="append", default=None, help="Glob to include (repeatable)")
    p.add_argument("--exclude-dir", action="append", default=None, help="Dir name to exclude (repeatable)")
    p.add_argument("--exclude", action="append", default=None, help="Glob to exclude (repeatable)")
    p.add_argument("--count", action="store_true", help="Print count only")
    p.add_argument("--head", type=int, default=0, help="Print first N records")
    p.add_argument("--jsonl", action="store_true", help="Print JSONL records (default)")

    args = p.parse_args(argv)
    root = Path(args.root)
    if not root.exists():
        print(f"Root not found: {root}")
        return 1

    opts = WalkOptions(
        include_globs=args.include or ["**/*.py"],
        exclude_dirs=(args.exclude_dir or default_exclude_dirs()),
        exclude_globs=(args.exclude or []),
        max_size_bytes=args.max_size,
        use_git_ls_files=bool(args.use_git),
    )
    files = discover_python_files(root, opts)
    if args.count:
        print(len(files))
        return 0
    items = files[: args.head] if args.head and args.head > 0 else files
    for it in items:
        print(json.dumps(it.__dict__, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

