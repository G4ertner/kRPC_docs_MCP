#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List

from krpc_snippets.ingest.deps import build_symbol_index, resolve_dependencies, attach_deps_to_records
from krpc_snippets.ingest.extract_snippets import extract_from_repo, ExtractOptions
from krpc_snippets.store import jsonl as jsonl_store
from krpc_snippets.store.validation import validate_snippet


def _load_jsonl(path: Path) -> List[dict]:
    items: List[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Analyze and attach dependencies to snippet records")
    p.add_argument("--root", required=True, help="Repository root path")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--snippets", help="Path to existing snippets JSONL to enrich with dependencies")
    g.add_argument("--extract", action="store_true", help="Extract snippets from repo before dependency analysis")
    p.add_argument("--repo-url", dest="repo_url", default=None)
    p.add_argument("--commit", dest="commit", default=None)
    p.add_argument("--out", dest="out", default="-", help="Output JSONL ('-' for stdout)")
    p.add_argument("--validate", action="store_true")

    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Root not found: {root}", file=sys.stderr)
        return 1

    # Load or extract records
    if args.snippets:
        recs = _load_jsonl(Path(args.snippets))
    else:
        opts = ExtractOptions()
        recs = extract_from_repo(root, repo_url=args.repo_url, commit=args.commit, opts=opts)

    # Build symbol index and dependency map
    sym = build_symbol_index(root)
    dep_map = resolve_dependencies(root, symbol_index=sym)
    out_recs = attach_deps_to_records(recs, dep_map)

    if args.validate:
        for r in out_recs:
            errs = validate_snippet(r)
            if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                print("Validation failed:", errs, file=sys.stderr)
                return 2

    if args.out == "-":
        for r in out_recs:
            print(json.dumps(r, ensure_ascii=False))
    else:
        jsonl_store.write_jsonl(out_recs, args.out, append=False, validate=args.validate)
        print(f"Wrote {len(out_recs)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

