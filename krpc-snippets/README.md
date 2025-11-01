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

Step A3 — Storage adapters (JSONL, Parquet, SQLite)
- Modules:
  - JSONL: `krpc_snippets/store/jsonl.py` → `write_jsonl`, `iter_jsonl`
  - Parquet: `krpc_snippets/store/parquet.py` → `write_parquet`, `read_parquet` (requires `pyarrow`)
  - SQLite: `krpc_snippets/store/sqlite.py` → `open_db`, `init_schema`, `upsert_snippet`, `bulk_insert`, `get_by_id`, `iter_all`, `query`
- CLI helper: `krpc-snippets/scripts/snippets_store_cli.py`
  - JSONL → SQLite: `uv --directory . run python krpc-snippets/scripts/snippets_store_cli.py jsonl-to-sqlite --in krpc-snippets/data/fixtures/snippet_valid.json --out krpc-snippets/data/snippets.sqlite`
  - SQLite → JSONL: `uv --directory . run python krpc-snippets/scripts/snippets_store_cli.py sqlite-to-jsonl --in krpc-snippets/data/snippets.sqlite --out krpc-snippets/data/snippets.jsonl`
  - JSONL → Parquet: `uv pip install pyarrow && uv --directory . run python krpc-snippets/scripts/snippets_store_cli.py jsonl-to-parquet --in krpc-snippets/data/snippets.jsonl --out krpc-snippets/data/snippets.parquet`
  - Parquet → JSONL: `uv --directory . run python krpc-snippets/scripts/snippets_store_cli.py parquet-to-jsonl --in krpc-snippets/data/snippets.parquet --out krpc-snippets/data/snippets2.jsonl`
  - Count: `uv --directory . run python krpc-snippets/scripts/snippets_store_cli.py count jsonl krpc-snippets/data/snippets.jsonl`
  - Head: `uv --directory . run python krpc-snippets/scripts/snippets_store_cli.py head sqlite krpc-snippets/data/snippets.sqlite --n 2`

Step B1 — Git fetcher (clone/update + checkout)
- Module: `krpc_snippets/ingest/git_fetch.py`
  - `slugify_repo(url_or_path)` → deterministic per‑repo folder
  - `clone_or_update(url_or_path, dest_root, shallow_depth=1)`
  - `checkout(repo_path, branch=None, sha=None, shallow_depth=1)` → sets HEAD, returns commit
  - `fetch_repo(url_or_path, out_root, branch=None, sha=None, depth=1)` → end‑to‑end helper
  - Manifests: `write_manifest(...)` writes `fetch.json` per repo
- CLI: `krpc-snippets/scripts/fetch_repo.py`
  - Single repo: `uv --directory . run python krpc-snippets/scripts/fetch_repo.py --url /path/to/local/repo --out krpc-snippets/data/repos`
  - Batch JSONL (lines like `{ "url": "...", "branch": "main", "sha": "..." }`):
    - `uv --directory . run python krpc-snippets/scripts/fetch_repo.py --file repos.jsonl --out krpc-snippets/data/repos`
  - Output: per‑repo folder at `krpc-snippets/data/repos/<slug>/` with `fetch.json`

Step B2 — File discovery & repo-level excludes
- Module: `krpc_snippets/ingest/walk_repo.py`
  - `discover_python_files(repo_root, opts)` returns stable, filtered `FileInfo[]`
  - Repo-level ignores: patterns from `.krpc-snippets-ignore` in the repo root (glob lines, `#` for comments)
  - Default excludes: `default_exclude_dirs()` (e.g., `.git`, `__pycache__`, `.venv`, `node_modules`, etc.)
- CLI: `krpc-snippets/scripts/walk_repo_cli.py`
  - Examples:
    - `uv --directory . run python krpc-snippets/scripts/walk_repo_cli.py --root krpc-snippets/data/repos/<slug> --count`
    - `uv --directory . run python krpc-snippets/scripts/walk_repo_cli.py --root krpc-snippets/data/repos/<slug> --head 5`
    - `uv --directory . run python krpc-snippets/scripts/walk_repo_cli.py --root krpc-snippets/data/repos/<slug> --use-git --exclude "**/tests/**"`
  - Place a `.krpc-snippets-ignore` at the repo root to exclude custom globs

Step B4 — Snippet extraction
- Module: `krpc_snippets/ingest/extract_snippets.py`
  - Extracts functions, methods, classes, and first const block into schema-compliant records with stable ids
  - Provenance from `--repo-url/--commit` or detected from `fetch.json` at repo root
- CLI: `krpc-snippets/scripts/extract_snippets.py`
  - Single file: `uv --directory . run python krpc-snippets/scripts/extract_snippets.py --root <repo> --file a/sample.py --out krpc-snippets/data/snippets.jsonl --license MIT --license-url https://opensource.org/licenses/MIT --validate`
  - Whole repo: `uv --directory . run python krpc-snippets/scripts/extract_snippets.py --root <repo> --all --out krpc-snippets/data/snippets.jsonl`
  - Output JSONL is ready for store adapters; validate with `scripts/schema_validate.py`

Step B5 — Dependency analysis (static)
- Module: `krpc_snippets/ingest/deps.py`
  - Builds a repo-wide symbol index (module.func, module.Class.method)
  - Analyzes call sites per function/method and resolves repo-local dependencies via imports/aliases
  - Attaches `dependencies[]` to snippet records (fully qualified names)
- CLI: `krpc-snippets/scripts/deps_analyze_repo.py`
  - Enrich existing JSONL: `uv --directory . run python krpc-snippets/scripts/deps_analyze_repo.py --root <repo> --snippets <snippets.jsonl> --out <snippets_with_deps.jsonl> --validate`
  - Or extract then enrich: `uv --directory . run python krpc-snippets/scripts/deps_analyze_repo.py --root <repo> --extract --out <snippets_with_deps.jsonl>`

Step B6 — License detection and enrichment
- Module: `krpc_snippets/governance/license.py`
  - Detects repo license via LICENSE file (SPDX or heuristic phrases) or SPDX headers in file tops
  - Returns SPDX id, canonical URL, and `restricted` flag (true for GPL/AGPL/LGPL families)
  - Enrichment helper to fill `license`, `license_url`, and `restricted` in snippet records
- CLI: `krpc-snippets/scripts/license_detect.py`
  - Detect only: `uv --directory . run python krpc-snippets/scripts/license_detect.py --root <repo> --write-summary`
  - Enrich JSONL: `uv --directory . run python krpc-snippets/scripts/license_detect.py --root <repo> --snippets <in.jsonl> --out <out.jsonl> --only-if-unknown --validate`
  - Policy: use `--fail-on-restricted` to exit non-zero when license is GPL-family

Step B7 — Provenance recorder & auditor
- Module: `krpc_snippets/ingest/provenance.py`
  - Fills/normalizes `repo`, `commit`, and `path` (repo-relative POSIX), using `fetch.json` if present
  - Verifies deterministic `id` by resolving node spans, and can recompute ids when unambiguous
  - Exports a simple provenance map `{id, repo, commit, path, created_at}`
- CLI: `krpc-snippets/scripts/provenance_audit.py`
  - Audit: `uv --directory . run python krpc-snippets/scripts/provenance_audit.py --root <repo> --snippets <in.jsonl>`
  - Fix: `uv --directory . run python krpc-snippets/scripts/provenance_audit.py --root <repo> --snippets <in.jsonl> --fix --out <out.jsonl> [--repair-id] [--validate]`
  - Export map: `uv --directory . run python krpc-snippets/scripts/provenance_audit.py --root <repo> --snippets <in.jsonl> --provenance-map --out <map.jsonl>`

Phase C — Enrichment & Indexing

Step C1 — LLM summariser & tagger
- Module: `krpc_snippets/enrich/summarise.py`
  - Summarises snippet description, refines categories, and adds inputs/outputs/when_to_use
  - Uses OpenAI when `OPENAI_API_KEY` is set; otherwise mock mode; caches per-snippet results under `krpc-snippets/data/enrich_cache`
- CLI: `krpc-snippets/scripts/enrich_summarise.py`
  - `uv --directory . run python krpc-snippets/scripts/enrich_summarise.py --in <snippets.jsonl> --out <snippets_enriched.jsonl> --only-empty --validate`
  - Add `--mock` to force mock mode; set `--model` to choose model (default `gpt-4o-mini`)
  - Ensure `OPENAI_API_KEY` in environment (unquoted) when not using `--mock`

Step C2 — Embedding generator
- Module: `krpc_snippets/enrich/embed.py`
  - Builds input text (name/description/code_head), calls OpenAI embeddings (or mock), caches per snippet+model, and writes outputs
  - Default model: `text-embedding-3-small`; enable `--normalize` for L2-normalized vectors
- CLI: `krpc-snippets/scripts/enrich_embed.py`
  - Mock (no API): `uv --directory . run python krpc-snippets/scripts/enrich_embed.py --in <snippets.jsonl> --out-sqlite krpc-snippets/data/embeddings.sqlite --out-jsonl krpc-snippets/data/embeddings.jsonl --mock --normalize`
  - Live: set `OPENAI_API_KEY` and drop `--mock`; choose `--model`
  - Parquet (optional): add `--out-parquet krpc-snippets/data/embeddings.parquet` (requires `pyarrow`)

Step C3 — Keyword index (inverted)
- Module: `krpc_snippets/index/keyword.py`
  - Tokenises name/description/categories/inputs and a short code head with weighted TF and IDF; simple OR/AND query logic
  - Saves/loads a portable JSON index
- CLI: `krpc-snippets/scripts/search_keyword.py`
  - Build: `uv --directory . run python krpc-snippets/scripts/search_keyword.py build --in krpc-snippets/data/snippets_enriched.jsonl --out krpc-snippets/data/keyword_index.json`
  - Query: `uv --directory . run python krpc-snippets/scripts/search_keyword.py query --index krpc-snippets/data/keyword_index.json --query "NavHelper" --k 5`
  - Ad-hoc: `uv --directory . run python krpc-snippets/scripts/search_keyword.py adhoc --in krpc-snippets/data/snippets_enriched.jsonl --query "helper" --k 5`

Step C4 — Hybrid retrieval (keyword + vectors)
- Module: `krpc_snippets/search/hybrid.py`
  - Loads keyword index + embedding store; embeds query text (OpenAI or mock); cos-sim vector search; fuses scores (alpha weights)
- CLI: `krpc-snippets/scripts/search_hybrid.py`
  - Example: `uv --directory . run python krpc-snippets/scripts/search_hybrid.py --query "NavHelper" --index krpc-snippets/data/keyword_index.json --embeddings-jsonl krpc-snippets/data/embeddings.jsonl --k 5 --alpha-keyword 0.5 --alpha-vector 0.5 --mock`

Step C5 — Reranker (optional)
- Module: `krpc_snippets/search/rerank.py`
  - Reranks Top‑M hybrid candidates using an LLM (OpenAI) or mock heuristic; caches results per query+candidate set
  - Final score = beta_rerank * rerank_score + (1 - beta_rerank) * hybrid_fused
- CLI (extended): `krpc-snippets/scripts/search_hybrid.py`
  - `--rerank --beta-rerank 0.7 --top-m 20 --rerank-model gpt-4o-mini` (add `--mock-rerank` for offline)

Phase D — Serving & Resolution

Step D1 — Dependency-aware resolver
- Module: `krpc_snippets/resolve/resolve_snippet.py`
  - Resolves a target snippet to a paste-ready bundle including dependencies, with size caps and unresolved reporting
  - Methods emit their parent class code; const blocks for involved modules are emitted first
- CLI: `krpc-snippets/scripts/resolve_snippet.py`
  - By id: `uv --directory . run python krpc-snippets/scripts/resolve_snippet.py --snippets krpc-snippets/data/snippets_extracted.jsonl --id <snippet_id> --out krpc-snippets/data/bundle.py`
  - By name: `uv --directory . run python krpc-snippets/scripts/resolve_snippet.py --snippets krpc-snippets/data/snippets_extracted.jsonl --name a.sample.NavHelper.circ_dv --out krpc-snippets/data/bundle_navhelper.py`
