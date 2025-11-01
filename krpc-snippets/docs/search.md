# Search

Keyword index
- Build index from enriched snippets:
  - `uv --directory . run python krpc-snippets/scripts/search_keyword.py build --in krpc-snippets/data/snippets_enriched.jsonl --out krpc-snippets/data/keyword_index.json`
- Query examples:
  - `uv --directory . run python krpc-snippets/scripts/search_keyword.py query --index krpc-snippets/data/keyword_index.json --query "NavHelper" --k 5`
  - Ad‑hoc (index-on-the-fly): `uv --directory . run python krpc-snippets/scripts/search_keyword.py adhoc --in krpc-snippets/data/snippets_enriched.jsonl --query "helper" --k 5`

Hybrid retrieval (keyword + vectors)
- Requirements: keyword index + embeddings store
- Build embeddings (mock):
  - `uv --directory . run python krpc-snippets/scripts/enrich_embed.py --in krpc-snippets/data/snippets_enriched.jsonl --out-sqlite krpc-snippets/data/embeddings.sqlite --mock --normalize`
- Live embeddings (needs `OPENAI_API_KEY`):
  - drop `--mock` and set `--model` as desired
- Query:
  - `uv --directory . run python krpc-snippets/scripts/search_hybrid.py --query "NavHelper" --index krpc-snippets/data/keyword_index.json --embeddings-sqlite krpc-snippets/data/embeddings.sqlite --k 5`
  - Add `--rerank` to re‑score Top‑M with LLM (mock/live)

Scoring
- Keyword: TF‑IDF (weighted fields) with OR/AND (`--and`)
- Hybrid: cosine similarity for vectors + fused scoring; optional rerank adds an LLM score term

Filters
- `--category` limits to snippet categories (e.g., `class`, `function`, `method`, `const`)
- `--exclude-restricted` filters GPL/AGPL/LGPL snippets per license policy

