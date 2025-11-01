#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from krpc_snippets.index.keyword import KeywordIndex, build_index
from krpc_snippets.search.hybrid import (
    load_embeddings_sqlite,
    load_embeddings_jsonl,
    load_embeddings_parquet,
    search_hybrid,
)
from krpc_snippets.eval.metrics import topk_accuracy, mrr, ndcg_at_k


def _load_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def _load_keyword_index(idx_path: Optional[Path], snippets_path: Path) -> KeywordIndex:
    if idx_path and idx_path.exists():
        return KeywordIndex.load(idx_path)
    recs = _load_jsonl(snippets_path)
    return build_index(recs)


def _load_vec_store(sqlite: Optional[Path], jsonl: Optional[Path], parquet: Optional[Path]):
    if sqlite and sqlite.exists():
        return load_embeddings_sqlite(sqlite)
    if jsonl and jsonl.exists():
        return load_embeddings_jsonl(jsonl)
    if parquet and parquet.exists():
        return load_embeddings_parquet(parquet)
    return None


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate retrieval quality on a query set")
    p.add_argument("--queries", required=True)
    p.add_argument("--snippets", required=True)
    p.add_argument("--index")
    p.add_argument("--embeddings-sqlite")
    p.add_argument("--embeddings-jsonl")
    p.add_argument("--embeddings-parquet")
    p.add_argument("--mode", choices=("keyword", "hybrid"), default=None)
    p.add_argument("--rerank", action="store_true")
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--report")
    p.add_argument("--min-top3", type=float, default=None)
    p.add_argument("--min-ndcg10", type=float, default=None)

    args = p.parse_args(argv)
    qpath = Path(args.queries)
    spath = Path(args.snippets)
    ipath = Path(args.index) if args.index else None
    idx = _load_keyword_index(ipath, spath)
    vec = _load_vec_store(Path(args.embeddings_sqlite) if args.embeddings_sqlite else None,
                          Path(args.embeddings_jsonl) if args.embeddings_jsonl else None,
                          Path(args.embeddings_parquet) if args.embeddings_parquet else None)
    mode = args.mode or ("hybrid" if vec is not None else "keyword")
    queries = _load_jsonl(qpath)

    per: List[Dict[str, Any]] = []
    acc1 = acc3 = acc5 = mrr_sum = ndcg10_sum = 0.0

    for q in queries:
        qid = q.get("qid")
        text = q.get("text")
        expected = q.get("expected_ids") or []
        if mode == "keyword":
            # Build ad-hoc keyword results from index
            from krpc_snippets.index.keyword import search as kw_search
            res = kw_search(idx, text, k=int(args.k))
            rows = [{"id": rid} for rid, _, _ in res]
        else:
            rows = search_hybrid(idx, vec, text, k=int(args.k), mock_query_embed=False)
            if args.rerank:
                from krpc_snippets.search.rerank import RerankConfig, rerank_results
                rows = rerank_results(text, rows, RerankConfig(mock=False))

        ids = [r.get("id") for r in rows]
        a1 = topk_accuracy(ids, expected, 1)
        a3 = topk_accuracy(ids, expected, 3)
        a5 = topk_accuracy(ids, expected, 5)
        mm = mrr(ids, expected)
        nd = ndcg_at_k(ids, expected, 10)
        acc1 += a1; acc3 += a3; acc5 += a5; mrr_sum += mm; ndcg10_sum += nd
        per.append({"qid": qid, "text": text, "top_ids": ids, "top1": a1, "top3": a3, "top5": a5, "mrr": mm, "ndcg@10": nd})

    N = max(1, len(queries))
    macro = {
        "top1": acc1 / N,
        "top3": acc3 / N,
        "top5": acc5 / N,
        "mrr": mrr_sum / N,
        "ndcg@10": ndcg10_sum / N,
    }
    report = {
        "config": {
            "mode": mode,
            "rerank": bool(args.rerank),
            "k": int(args.k),
            "index": str(ipath) if ipath else None,
            "embeddings": args.embeddings_sqlite or args.embeddings_jsonl or args.embeddings_parquet,
        },
        "macro": macro,
        "per_query": per,
    }
    print(json.dumps(report, ensure_ascii=False))
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Fail gates
    exit_code = 0
    if args.min_top3 is not None and macro["top3"] < float(args.min_top3):
        exit_code = max(exit_code, 2)
    if args.min_ndcg10 is not None and macro["ndcg@10"] < float(args.min_ndcg10):
        exit_code = max(exit_code, 3)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

