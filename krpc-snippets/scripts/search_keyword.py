#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, List

from krpc_snippets.index.keyword import KeywordConfig, KeywordIndex, build_index, search as kw_search


def _load_jsonl(path: Path) -> list[dict]:
    recs: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        recs.append(json.loads(line))
    return recs


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Keyword index builder and search CLI")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="Build index from snippets JSONL")
    b.add_argument("--in", dest="infile", required=True)
    b.add_argument("--out", dest="outfile", required=True)
    b.add_argument("--code-head-chars", type=int, default=300)

    q = sub.add_parser("query", help="Search an existing index file")
    q.add_argument("--index", required=True)
    q.add_argument("--query", required=True)
    q.add_argument("--k", type=int, default=10)
    q.add_argument("--and", dest="use_and", action="store_true")
    q.add_argument("--category", default=None)
    q.add_argument("--exclude-restricted", action="store_true")

    a = sub.add_parser("adhoc", help="Build in-memory and search")
    a.add_argument("--in", dest="infile", required=True)
    a.add_argument("--query", required=True)
    a.add_argument("--k", type=int, default=10)
    a.add_argument("--code-head-chars", type=int, default=300)

    args = p.parse_args(argv)
    if args.cmd == "build":
        cfg = KeywordConfig(code_head_chars=int(args.code_head_chars))
        recs = _load_jsonl(Path(args.infile))
        idx = build_index(recs, cfg)
        KeywordIndex.save(idx, Path(args.outfile))
        print(f"Index saved: {args.outfile} (docs={idx.N})")
        return 0
    elif args.cmd == "query":
        idx = KeywordIndex.load(Path(args.index))
        res = kw_search(idx, args.query, k=int(args.k), use_and=bool(args.use_and), category=args.category, exclude_restricted=bool(args.exclude_restricted))
        for rank, (rid, sc, doc) in enumerate(res, start=1):
            preview = (doc.get("description") or doc.get("name") or "")[:200]
            print(json.dumps({
                "rank": rank,
                "id": rid,
                "score": sc,
                "name": doc.get("name"),
                "path": doc.get("path"),
                "categories": doc.get("categories"),
                "preview": preview,
            }, ensure_ascii=False))
        return 0
    elif args.cmd == "adhoc":
        cfg = KeywordConfig(code_head_chars=int(args.code_head_chars))
        recs = _load_jsonl(Path(args.infile))
        idx = build_index(recs, cfg)
        res = kw_search(idx, args.query, k=int(args.k))
        for rank, (rid, sc, doc) in enumerate(res, start=1):
            preview = (doc.get("description") or doc.get("name") or "")[:200]
            print(json.dumps({
                "rank": rank,
                "id": rid,
                "score": sc,
                "name": doc.get("name"),
                "path": doc.get("path"),
                "categories": doc.get("categories"),
                "preview": preview,
            }, ensure_ascii=False))
        return 0
    else:
        p.print_help()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

