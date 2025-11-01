# Getting Started

Prerequisites
- Python 3.10+
- `uv` (recommended): https://docs.astral.sh/uv/

Setup
- Create a venv and install in editable mode:
  - `uv venv && source .venv/bin/activate`
  - `uv pip install -e .`
  - Optional (LLM enrichment paths): `uv pip install -e .[enrich]`

Environment
- For any live OpenAI calls set `OPENAI_API_KEY` in your environment (no quotes). Example `.env` content inside `krpc-snippets/.env`:
  - `OPENAI_API_KEY=sk-...`
- The repo-level `.gitignore` already ignores `krpc-snippets/.env`.

Quick sanity (no API key needed)
- Validate schema fixture: `uv --directory . run python krpc-snippets/scripts/schema_validate.py krpc-snippets/data/fixtures/snippet_valid.json`
- Build and query keyword index (uses synthetic sample data bundled in `krpc-snippets/data`):
  - `uv --directory . run python krpc-snippets/scripts/search_keyword.py adhoc --in krpc-snippets/data/snippets_extracted.jsonl --query "helper" --k 5`

End-to-end (mock enrichment)
- Summaries/tags (mock): `uv --directory . run python krpc-snippets/scripts/enrich_summarise.py --in krpc-snippets/data/snippets_extracted.jsonl --out krpc-snippets/data/snippets_enriched.jsonl --mock --validate`
- Embeddings (mock): `uv --directory . run python krpc-snippets/scripts/enrich_embed.py --in krpc-snippets/data/snippets_enriched.jsonl --out-sqlite krpc-snippets/data/embeddings.sqlite --mock --normalize`
- Hybrid search: `uv --directory . run python krpc-snippets/scripts/search_hybrid.py --query "NavHelper" --index krpc-snippets/data/keyword_index.json --embeddings-sqlite krpc-snippets/data/embeddings.sqlite --k 5`

Preview docs locally (optional)
- A minimal MkDocs config is included under `krpc-snippets/mkdocs.yml`.
- Serve: `uv run mkdocs serve -f krpc-snippets/mkdocs.yml`
- Build: `uv run mkdocs build -f krpc-snippets/mkdocs.yml`

