#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List

from krpc_snippets.ingest.extract_snippets import (
    extract_from_file,
    extract_from_repo,
    ExtractOptions,
)
from krpc_snippets.store import jsonl as jsonl_store
from krpc_snippets.store.validation import validate_snippet


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Extract schema-compliant snippets from a repo or file")
    p.add_argument("--root", required=True, help="Repository root path")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", help="Relative path to a single Python file in the repo")
    g.add_argument("--all", action="store_true", help="Extract from all discovered Python files")
    p.add_argument("--repo-url", dest="repo_url", default=None, help="Provenance: repository URL")
    p.add_argument("--commit", dest="commit", default=None, help="Provenance: commit SHA")
    p.add_argument("--license", dest="license", default="UNKNOWN")
    p.add_argument("--license-url", dest="license_url", default="about:blank")
    p.add_argument("--no-functions", dest="no_functions", action="store_true")
    p.add_argument("--no-methods", dest="no_methods", action="store_true")
    p.add_argument("--no-classes", dest="no_classes", action="store_true")
    p.add_argument("--no-consts", dest="no_consts", action="store_true")
    p.add_argument("--out", dest="out", default="-", help="Output JSONL path or '-' for stdout")
    p.add_argument("--validate", action="store_true", help="Validate records against JSON schema")

    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Root not found: {root}", file=sys.stderr)
        return 1
    opts = ExtractOptions(
        include_functions=not args.no_functions,
        include_methods=not args.no_methods,
        include_classes=not args.no_classes,
        include_consts=not args.no_consts,
        default_license=args.license,
        default_license_url=args.license_url,
    )
    recs: List[dict]
    if args.file:
        recs = extract_from_file(
            root,
            (root / args.file).resolve(),
            repo_url=args.repo_url,
            commit=args.commit,
            opts=opts,
        )
    else:
        recs = extract_from_repo(
            root,
            repo_url=args.repo_url,
            commit=args.commit,
            opts=opts,
        )

    if args.validate:
        for r in recs:
            errs = validate_snippet(r)
            if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                print("Validation failed:", errs, file=sys.stderr)
                return 2

    if args.out == "-":
        for r in recs:
            print(json.dumps(r, ensure_ascii=False))
        return 0
    else:
        n = jsonl_store.write_jsonl(recs, args.out, append=False, validate=args.validate)
        print(f"Wrote {n} records to {args.out}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

