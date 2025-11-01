#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, List

from krpc_snippets.enrich.summarise import SummarizerConfig, summarise_snippets
from krpc_snippets.utils.env import load_env_defaults
from krpc_snippets.store import jsonl as jsonl_store
from krpc_snippets.store.validation import validate_snippet


def _load_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def main(argv: Optional[List[str]] = None) -> int:
    # Load local environment defaults (e.g., OPENAI_API_KEY) if present
    load_env_defaults()
    p = argparse.ArgumentParser(description="Summarise/tag snippets via OpenAI (with mock/caching)")
    p.add_argument("--in", dest="infile", required=True)
    p.add_argument("--out", dest="out", required=True)
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--mock", action="store_true")
    p.add_argument("--only-empty", action="store_true")
    p.add_argument("--cache-dir", default="krpc-snippets/data/enrich_cache")
    p.add_argument("--validate", action="store_true")

    args = p.parse_args(argv)
    records = _load_jsonl(Path(args.infile))
    cfg = SummarizerConfig(
        model=args.model,
        mock=bool(args.mock or not os.environ.get("OPENAI_API_KEY")),
        cache_dir=Path(args.cache_dir),
        only_if_empty=bool(args.only_empty),
    )
    out = summarise_snippets(records, cfg)
    if args.validate:
        for r in out:
            errs = validate_snippet(r)
            if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                print("Validation failed:", errs, file=sys.stderr)
                return 2
    jsonl_store.write_jsonl(out, args.out, append=False, validate=args.validate)
    print(f"Wrote {len(out)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
