#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List

from krpc_snippets.governance.license import (
    detect_repo_license,
    summarize_repo_license,
    enrich_snippets_with_license,
)
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
    p = argparse.ArgumentParser(description="Detect repository license and enrich snippet JSONL records")
    p.add_argument("--root", required=True, help="Repository root path")
    p.add_argument("--snippets", help="Path to snippets JSONL to enrich with license info")
    p.add_argument("--out", default="-", help="Output JSONL or '-' for stdout (when --snippets provided)")
    p.add_argument("--only-if-unknown", action="store_true", help="Only overwrite license fields if currently UNKNOWN/empty")
    p.add_argument("--fail-on-restricted", action="store_true", help="Exit non-zero if license is restricted (GPL family)")
    p.add_argument("--write-summary", action="store_true", help="Write license summary to <root>/license.json")
    p.add_argument("--validate", action="store_true")

    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Root not found: {root}", file=sys.stderr)
        return 1

    lic = detect_repo_license(root)
    summary = summarize_repo_license(root)
    if args.write_summary:
        (root / "license.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # If no snippets provided, just print summary
    if not args.snippets:
        print(json.dumps(summary, ensure_ascii=False))
        if args.fail_on_restricted and lic.restricted:
            return 3
        return 0

    # Enrich JSONL
    recs = _load_jsonl(Path(args.snippets))
    enriched = enrich_snippets_with_license(recs, lic, only_if_unknown=args.only_if_unknown)
    if args.validate:
        for r in enriched:
            errs = validate_snippet(r)
            if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                print("Validation failed:", errs, file=sys.stderr)
                return 2
    if args.out == "-":
        for r in enriched:
            print(json.dumps(r, ensure_ascii=False))
    else:
        jsonl_store.write_jsonl(enriched, args.out, append=False, validate=args.validate)
        print(f"Wrote {len(enriched)} records to {args.out}")
    if args.fail_on_restricted and lic.restricted:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

