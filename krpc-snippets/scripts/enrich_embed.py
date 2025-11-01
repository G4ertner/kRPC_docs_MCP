#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional, List

from krpc_snippets.enrich.embed import EmbedConfig, embed_records, write_sqlite, write_jsonl, write_parquet


def _load_jsonl(path: Path) -> list[dict]:
    recs: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        recs.append(json.loads(line))
    return recs


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Generate embeddings for snippet records (OpenAI or mock)")
    p.add_argument("--in", dest="infile", required=True)
    p.add_argument("--out-sqlite", dest="out_sqlite")
    p.add_argument("--out-jsonl", dest="out_jsonl")
    p.add_argument("--out-parquet", dest="out_parquet")
    p.add_argument("--model", default="text-embedding-3-small")
    p.add_argument("--fields", default="name,description,code_head")
    p.add_argument("--code-head-chars", type=int, default=800)
    p.add_argument("--normalize", action="store_true")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--cache-dir", default="krpc-snippets/data/embed_cache")
    p.add_argument("--mock", action="store_true")

    args = p.parse_args(argv)
    outputs = [args.out_sqlite, args.out_jsonl, args.out_parquet]
    if not any(outputs):
        p.error("At least one of --out-sqlite/--out-jsonl/--out-parquet is required")

    records = _load_jsonl(Path(args.infile))
    fields = [s.strip() for s in args.fields.split(",") if s.strip()]
    cfg = EmbedConfig(
        model=args.model,
        fields=fields,
        code_head_chars=int(args.code_head_chars),
        normalize=bool(args.normalize),
        batch_size=int(args.batch_size),
        cache_dir=Path(args.cache_dir),
        mock=bool(args.mock or not os.environ.get("OPENAI_API_KEY")),
    )
    embeddings = embed_records(records, cfg)
    n = len(embeddings)
    if args.out_sqlite:
        write_sqlite(embeddings, Path(args.out_sqlite))
    if args.out_jsonl:
        write_jsonl(embeddings, Path(args.out_jsonl))
    if args.out_parquet:
        write_parquet(embeddings, Path(args.out_parquet))
    print(f"Wrote {n} embeddings ({args.model})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

