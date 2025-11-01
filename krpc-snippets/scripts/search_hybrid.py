#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, List

from krpc_snippets.index.keyword import KeywordIndex
from krpc_snippets.search.hybrid import (
    load_keyword_index,
    load_embeddings_jsonl,
    load_embeddings_sqlite,
    load_embeddings_parquet,
    search_hybrid,
)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Hybrid search (keyword + vectors)")
    p.add_argument("--query", required=True)
    p.add_argument("--index", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--embeddings-sqlite")
    g.add_argument("--embeddings-jsonl")
    g.add_argument("--embeddings-parquet")
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--alpha-keyword", type=float, default=0.5)
    p.add_argument("--alpha-vector", type=float, default=0.5)
    p.add_argument("--and", dest="use_and", action="store_true")
    p.add_argument("--category")
    p.add_argument("--exclude-restricted", action="store_true")
    p.add_argument("--model", default=None, help="Embedding model for query text")
    p.add_argument("--mock", action="store_true", help="Use mock embedding for query")
    # Reranker options
    p.add_argument("--rerank", action="store_true")
    p.add_argument("--beta-rerank", type=float, default=0.7)
    p.add_argument("--top-m", type=int, default=20)
    p.add_argument("--rerank-model", default="gpt-4o-mini")
    p.add_argument("--mock-rerank", action="store_true")

    args = p.parse_args(argv)
    idx = load_keyword_index(Path(args.index))
    if args.embeddings_sqlite:
        store = load_embeddings_sqlite(Path(args.embeddings_sqlite))
    elif args.embeddings_jsonl:
        store = load_embeddings_jsonl(Path(args.embeddings_jsonl))
    else:
        store = load_embeddings_parquet(Path(args.embeddings_parquet))

    res = search_hybrid(
        idx,
        store,
        args.query,
        k=int(args.k),
        alpha_keyword=float(args.alpha_keyword),
        alpha_vector=float(args.alpha_vector),
        use_and=bool(args.use_and),
        category=args.category,
        exclude_restricted=bool(args.exclude_restricted),
        mock_query_embed=bool(args.mock),
        embed_model=args.model,
    )
    # Optional rerank
    if args.rerank:
        from krpc_snippets.search.rerank import RerankConfig, rerank_results
        cfg = RerankConfig(
            model=args.rerank_model,
            top_m=int(args.top_m),
            beta_rerank=float(args.beta_rerank),
            mock=bool(args.mock_rerank),
        )
        res = rerank_results(args.query, res, cfg)[: int(args.k)]

    for rank, row in enumerate(res, start=1):
        row_out = dict(row)
        row_out["rank"] = rank
        print(json.dumps(row_out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
