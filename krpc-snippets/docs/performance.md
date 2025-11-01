# Performance

Benchmark script
- `krpc-snippets/scripts/bench_search.py`

Examples
- Keyword (docs, warmups, reps):
  - `uv --directory . run python krpc-snippets/scripts/bench_search.py --index krpc-snippets/data/keyword_index.json --docs 1000 --warmup 3 --reps 10 --out krpc-snippets/data/bench_keyword.json`
- Hybrid (requires embeddings):
  - `uv --directory . run python krpc-snippets/scripts/bench_search.py --index krpc-snippets/data/keyword_index.json --embeddings-sqlite krpc-snippets/data/embeddings.sqlite --docs 1000 --warmup 3 --reps 10 --out krpc-snippets/data/bench_hybrid.json`

Outputs
- JSON with latency (p50/p90), throughput, and memory snapshots

Tips
- Ensure indices are pre‑loaded to amortize disk I/O
- For deterministic runs, pin Python version and disable CPU frequency scaling if possible

