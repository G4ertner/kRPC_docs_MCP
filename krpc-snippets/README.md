krpc-snippets — kRPC Code Examples RAG (side project)

Overview
- This folder contains the code and scaffolding for the kRPC code examples Retrieval-Augmented Generation (RAG) library and tools.
- It follows the implementation plan described in `k_rpc_mcp_rag_snippet_indexer_project_plan.md` (located in this folder).

Quick start
- Show CLI help (module-based):
  - `uv --directory krpc-snippets run -m krpc_snippets.cli --help`
  - Or via console script after install/editable: `uv run krpc-snippets --help`

Planned subcommands (stubs for now)
- `ingest` — clone/walk repos and parse source files
- `enrich` — summarise/tag snippets (LLM)
- `index` — build keyword/vector indices
- `search` — keyword search
- `search-hybrid` — hybrid (keyword+vector) search
- `resolve` — return snippet with resolved dependencies

Layout
- `krpc_snippets/` — Python package with CLI and module namespaces for each phase
- `data/` — placeholder for datasets (JSONL/Parquet/SQLite) generated later
- `artifacts/` — placeholder for exports and benchmarks
- `ci/` — placeholder for CI docs/config
 - `scripts/` — helper scripts (e.g., schema validation)

Step A2 — Snippet JSON schema
- Schema file: `krpc_snippets/schemas/snippet.schema.json`
- Fixtures: `data/fixtures/snippet_valid.json`, `data/fixtures/snippet_invalid_missing_fields.json`
- Validate (requires jsonschema):
  - `uv pip install jsonschema`
  - `uv --directory . run python krpc-snippets/scripts/schema_validate.py krpc-snippets/data/fixtures/snippet_valid.json`
  - `uv --directory . run python krpc-snippets/scripts/schema_validate.py krpc-snippets/data/fixtures/snippet_invalid_missing_fields.json` (should report errors and exit non‑zero)
