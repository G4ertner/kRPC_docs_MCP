# Evaluation

Queries dataset
- Seed queries live at `krpc-snippets/eval/queries.jsonl`.

Script
- `krpc-snippets/scripts/eval_retrieval.py`
- Keyword‑only eval:
  - `uv --directory . run python krpc-snippets/scripts/eval_retrieval.py --queries krpc-snippets/eval/queries.jsonl --snippets krpc-snippets/data/snippets_enriched.jsonl --index krpc-snippets/data/keyword_index.json --out krpc-snippets/data/eval_keyword.json`
- Hybrid eval (requires embeddings; uses mock unless `OPENAI_API_KEY` set):
  - `uv --directory . run python krpc-snippets/scripts/eval_retrieval.py --queries krpc-snippets/eval/queries.jsonl --snippets krpc-snippets/data/snippets_enriched.jsonl --index krpc-snippets/data/keyword_index.json --embeddings-sqlite krpc-snippets/data/embeddings.sqlite --out krpc-snippets/data/eval_hybrid.json`

Metrics
- Precision@K, Recall@K (Top‑K matches against labeled positives)
- Report JSON includes per‑query details and aggregate means

CI usage
- CI runs keyword eval by default with gating thresholds; hybrid paths default to mock embeddings.

