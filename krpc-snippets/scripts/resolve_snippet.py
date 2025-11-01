#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, List

from krpc_snippets.resolve.resolve_snippet import resolve_snippet


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Resolve a snippet id/name to a paste-ready code bundle with dependencies")
    p.add_argument("--snippets", required=True, help="Snippets JSONL path")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", dest="target_id")
    g.add_argument("--name", dest="target_name", help="Target symbol 'module.qualname'")
    p.add_argument("--out", dest="out", default="-", help="Output .py file or '-' for stdout")
    p.add_argument("--max-bytes", dest="max_bytes", type=int, default=25000)
    p.add_argument("--max-nodes", dest="max_nodes", type=int, default=25)
    p.add_argument("--emit-map", dest="emit_map", action="store_true")

    args = p.parse_args(argv)
    res = resolve_snippet(
        target_id=args.target_id,
        target_name=args.target_name,
        snippets_path=Path(args.snippets),
        size_cap_bytes=int(args.max_bytes),
        size_cap_nodes=int(args.max_nodes),
        emit_map=bool(args.emit_map),
    )
    if args.out == "-":
        print(res.bundle_code)
    else:
        Path(args.out).write_text(res.bundle_code, encoding="utf-8")
        print(f"Wrote bundle to {args.out} (nodes={res.stats['nodes']}, bytes={res.stats['bytes']})")
        if res.unresolved_deps:
            print("Unresolved:", ", ".join(res.unresolved_deps))
        if res.truncated:
            print("Note: bundle truncated due to caps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

