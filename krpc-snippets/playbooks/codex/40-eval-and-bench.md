# Eval & Bench

```bash
SN=krpc-snippets/data/snippets_enriched.jsonl
[ -f "$SN" ] || SN=krpc-snippets/data/snippets_extracted.jsonl
IDX=krpc-snippets/data/keyword_index.json
EMB=krpc-snippets/data/embeddings.jsonl

# 1) Eval (keyword)
uv --directory . run python krpc-snippets/scripts/eval_retrieval.py \
  --queries krpc-snippets/eval/queries.jsonl --snippets $SN --index $IDX \
  --mode keyword --k 10 --report krpc-snippets/data/eval_keyword.json

# 2) Eval (hybrid; mock)
uv --directory . run python krpc-snippets/scripts/eval_retrieval.py \
  --queries krpc-snippets/eval/queries.jsonl --snippets $SN --index $IDX \
  --embeddings-jsonl $EMB --mode hybrid --k 10 --report krpc-snippets/data/eval_hybrid.json

# 3) Bench (keyword)
uv --directory . run python krpc-snippets/scripts/bench_search.py \
  --queries krpc-snippets/eval/queries.jsonl --snippets $SN --index $IDX \
  --mode keyword --iters 25 --warmup 5 --k 5 --report krpc-snippets/data/bench_keyword.json
```
