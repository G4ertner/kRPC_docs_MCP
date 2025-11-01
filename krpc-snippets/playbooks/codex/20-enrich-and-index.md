# Enrich & Index

```bash
SN=krpc-snippets/data/snippets_extracted.jsonl
[ -f krpc-snippets/data/snippets_enriched.jsonl ] && SN=krpc-snippets/data/snippets_enriched.jsonl
IDX=krpc-snippets/data/keyword_index.json
EMB=krpc-snippets/data/embeddings.jsonl

# 1) Summarise/tag (mock by default)
uv --directory . run python krpc-snippets/scripts/enrich_summarise.py \
  --in $SN --out $SN --only-empty --mock --validate

# 2) Embeddings (mock; JSONL)
uv --directory . run python krpc-snippets/scripts/enrich_embed.py \
  --in $SN --out-jsonl $EMB --mock --normalize

# 3) Keyword index build
uv --directory . run python krpc-snippets/scripts/search_keyword.py build \
  --in $SN --out $IDX

# 4) Keyword search
uv --directory . run python krpc-snippets/scripts/search_keyword.py query \
  --index $IDX --query "helper" --k 5

# 5) Hybrid + rerank (mock)
uv --directory . run python krpc-snippets/scripts/search_hybrid.py \
  --query "NavHelper" --index $IDX --embeddings-jsonl $EMB --k 5 --mock --rerank --mock-rerank

# Live mode (optional): set OPENAI_API_KEY and drop --mock flags
```
