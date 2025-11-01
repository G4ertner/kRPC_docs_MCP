#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import median
from typing import Optional, List

from krpc_snippets.index.keyword import KeywordIndex, build_index
from krpc_snippets.index.keyword import search as kw_search
from krpc_snippets.search.hybrid import (
    load_embeddings_sqlite,
    load_embeddings_jsonl,
    load_embeddings_parquet,
    search_hybrid,
)


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


def _rss_mb() -> float:
    try:
        import resource  # type: ignore

        r = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss is kilobytes on Linux, bytes on mac; normalize best-effort
        val = float(getattr(r, "ru_maxrss", 0.0) or 0.0)
        if val > 10_000:  # assume kilobytes
            return val / 1024.0
        return val / (1024.0 * 1024.0)
    except Exception:
        return -1.0


def _percentile(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    xs2 = sorted(xs)
    k = int(round((p / 100.0) * (len(xs2) - 1)))
    k = max(0, min(k, len(xs2) - 1))
    return xs2[k]


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Benchmark keyword/hybrid search latency and memory")
    p.add_argument("--queries", required=True)
    p.add_argument("--snippets", required=True)
    p.add_argument("--index")
    p.add_argument("--embeddings-sqlite")
    p.add_argument("--embeddings-jsonl")
    p.add_argument("--embeddings-parquet")
    p.add_argument("--mode", choices=("keyword", "hybrid"), default=None)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--iters", type=int, default=50)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--mock", action="store_true", help="Use mock query embedding in hybrid mode")
    p.add_argument("--report")

    args = p.parse_args(argv)
    qpath = Path(args.queries)
    spath = Path(args.snippets)
    ipath = Path(args.index) if args.index else None
    idx = _load_keyword_index(ipath, spath)
    vec = _load_vec_store(Path(args.embeddings_sqlite) if args.embeddings_sqlite else None,
                          Path(args.embeddings_jsonl) if args.embeddings_jsonl else None,
                          Path(args.embeddings_parquet) if args.embeddings_parquet else None)
    mode = args.mode or ("hybrid" if vec is not None else "keyword")
    queries = [q.get("text") for q in _load_jsonl(qpath)]
    if not queries:
        print("No queries found", file=sys.stderr)
        return 2

    # Warmup
    for i in range(int(args.warmup)):
        q = queries[i % len(queries)]
        if mode == "keyword":
            kw_search(idx, q, k=int(args.k))
        else:
            search_hybrid(idx, vec, q, k=int(args.k), mock_query_embed=bool(args.mock))

    # Timed runs
    durs: List[float] = []
    for i in range(int(args.iters)):
        q = queries[i % len(queries)]
        t0 = time.perf_counter()
        if mode == "keyword":
            kw_search(idx, q, k=int(args.k))
        else:
            search_hybrid(idx, vec, q, k=int(args.k), mock_query_embed=bool(args.mock))
        durs.append((time.perf_counter() - t0) * 1000.0)  # ms

    rep = {
        "config": {
            "mode": mode,
            "k": int(args.k),
            "iters": int(args.iters),
            "warmup": int(args.warmup),
            "mock_query_embed": bool(args.mock),
        },
        "latency_ms": {
            "p50": median(durs),
            "p95": _percentile(durs, 95.0),
            "avg": sum(durs) / max(1, len(durs)),
        },
        "memory": {
            "rss_mb": _rss_mb(),
        },
    }
    print(json.dumps(rep, ensure_ascii=False))
    if args.report:
        Path(args.report).write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())

