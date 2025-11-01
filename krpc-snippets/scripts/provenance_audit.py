#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List

from krpc_snippets.ingest.provenance import audit_record, fix_record, build_provenance_map
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
    p = argparse.ArgumentParser(description="Audit and repair snippet provenance (repo/commit/path/id)")
    p.add_argument("--root", required=True, help="Repository root path")
    p.add_argument("--snippets", required=True, help="Input snippets JSONL")
    p.add_argument("--out", help="Output JSONL when using --fix or --provenance-map")
    p.add_argument("--repair-id", action="store_true", help="Attempt to recompute ids when spans resolve")
    p.add_argument("--repo-url", dest="repo_url", default=None)
    p.add_argument("--commit", dest="commit", default=None)
    p.add_argument("--provenance-map", action="store_true", help="Write id->provenance JSONL instead of full records")
    p.add_argument("--fix", action="store_true", help="Write fixed records to --out")
    p.add_argument("--strict", action="store_true", help="Exit non-zero if spans cannot be resolved and --repair-id used")
    p.add_argument("--validate", action="store_true")
    p.add_argument("--quiet", action="store_true")

    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Root not found: {root}", file=sys.stderr)
        return 1
    in_path = Path(args.snippets)
    recs = _load_jsonl(in_path)

    missing = bad = mismatch = unresolved = 0
    fixed: list[dict] = []
    for r in recs:
        rep = audit_record(r, root, args.repo_url, args.commit)
        missing += int(rep.missing_provenance)
        bad += int(rep.bad_path)
        mismatch += int(rep.id_mismatch)
        unresolved += int(rep.span_unresolved)
        if not args.quiet:
            print(json.dumps({"id": r.get("id"), "audit": rep.__dict__}, ensure_ascii=False))
        if args.fix:
            fixed.append(fix_record(r, root, args.repo_url, args.commit, repair_id=args.repair_id))

    if args.provenance_map:
        if not args.out:
            print("--out is required with --provenance-map", file=sys.stderr)
            return 2
        prov = build_provenance_map(fixed if args.fix else recs)
        jsonl_store.write_jsonl(prov, args.out, append=False, validate=False)
        print(f"Wrote {len(prov)} rows to {args.out}")
        return 0

    if args.fix:
        if not args.out:
            print("--out is required with --fix", file=sys.stderr)
            return 2
        if args.validate:
            for r in fixed:
                errs = validate_snippet(r)
                if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                    print("Validation failed:", errs, file=sys.stderr)
                    return 2
        jsonl_store.write_jsonl(fixed, args.out, append=False, validate=args.validate)
        print(f"Wrote {len(fixed)} records to {args.out}")

    print(json.dumps({
        "missing_provenance": missing,
        "bad_path": bad,
        "id_mismatch": mismatch,
        "span_unresolved": unresolved,
        "total": len(recs),
    }, ensure_ascii=False))

    if args.strict and args.repair_id and unresolved:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

