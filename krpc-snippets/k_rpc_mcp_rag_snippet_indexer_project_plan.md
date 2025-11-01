# kRPC MCP – RAG Snippet Indexer Project Plan

## 0) Executive Summary
kRPC MCP currently lacks sufficient, high‑quality **code examples** for the LLM to reliably generate efficient, idiomatic kRPC programs. We will build a Retrieval‑Augmented Generation (RAG) **lookup library** that ingests public kRPC/KSP repositories, extracts small, single‑purpose snippets (e.g., *circularise orbit*, *PID hover/landing*), enriches them with LLM‑generated summaries & functional tags, and makes them searchable via keyword + semantic (embedding) search. The MCP server and Codex CLI can then autonomously query this library to retrieve the **best existing examples** (with dependencies resolved) and assemble fully functioning solutions.

---

## 1) Why (Motivation & Goals)
- **Close the examples gap:** Today, kRPC MCP doesn’t provide the LLM with enough concrete examples; the RAG library supplies a rich, curated set the model can query autonomously during codegen.
- **Higher code quality & speed:** Reuse proven patterns (streams, gravity turns, circularisation, PID landing) instead of re‑inventing them each time.
- **Better explainability:** Each snippet carries a concise NL summary (what/why/how) and inputs/outputs so agents (and humans) can reason about usage.
- **Composable automation:** Make it easy for Codex/agents to chain operations (e.g., ascent → circularise → transfer → landing).
- **Licensing clarity:** Every record tracks origin, licence, and commit; GPL and restricted licences are flagged.

### Success Criteria (measurable)
- **Retrieval quality:** On a 30‑query benchmark (e.g., “circularise orbit”, “suicide burn altitude”, “rendezvous node”), Top‑3 contains a correct snippet ≥ **85%**; Top‑1 ≥ **70%**.
- **Coverage:** ≥ **12** functional categories, each with ≥ **3** examples.
- **Latency:** Query to results in **< 300 ms** (index) and **< 1.5 s** (semantic rerank) on a modest VM.
- **Compliance:** 100% of records carry licence + repo + commit metadata; GPL content is flagged.

---

## 2) What (Scope)
- Languages: **Python** primarily; future hooks for C#/Java.
- Sources: public kRPC/KSP repos (examples, autopilots, PID controllers, mission scripts) plus structured docs.
- Artifacts: JSONL snippet corpus, SQLite/Parquet stores, inverted index, vector store, MCP tools, evaluation harness, CI.

Out of scope (initial): Code execution sandboxing, refactoring whole repos, code formatting opinions.

---

## 3) Overview of Seed Repositories (non‑exhaustive)
- **kRPC/krpc‑library** — Community examples for kRPC (general patterns, telemetry/control/streams).  https://github.com/krpc/krpc-library
- **AlanCunningham/krpc‑scripts** — Launch to orbit, Mun transfer; gravity turn + circularisation utilities.  https://github.com/AlanCunningham/krpc-scripts
- **alexlabbane/kRPC‑mun‑mission** — Full mission (LKO → Mun transfer/landing) with modular steps; reusable ascent/circularisation.  https://github.com/alexlabbane/kRPC-mun-mission
- **Jake1402/KSP‑PID‑Hovering** — PID‑based hover/landing control using kRPC flight data.  https://github.com/Jake1402/KSP-PID-Hovering
- **azolotarev/ksp‑with‑python** — Landing & suicide‑burn computations (burn start altitude, throttle control).  https://github.com/azolotarev/ksp-with-python
- **ndeutschmann‑fun/ksp‑ap** — Ascent autopilot modules, vis‑viva circularisation, suicide‑burn; modular architecture.  https://github.com/ndeutschmann-fun/ksp-ap
- **whatdamath/KerbalSpaceProgram** — Dynamic‑pressure‑limited ascent and circularisation node execution.  https://github.com/whatdamath/KerbalSpaceProgram
- **BlackBreezeCastle/peg‑for‑krpc‑python** — Powered Explicit Guidance (PEG) for ascent guidance (pair with your control loop).  https://github.com/BlackBreezeCastle/peg-for-krpc-python
- **pmauby/ksp‑autopilot** — Recoverable booster state machine: ascent, stage, flip, boost‑back, glide, land (PID).  https://github.com/pmauby/ksp-autopilot
- **vmeazevedo/ksp_orbital_rocket_automation** — End‑to‑end launch→orbit→re‑entry→parachute landing.  https://github.com/vmeazevedo/ksp_orbital_rocket_automation
- **Hansastro/KSP_Adventure** — Mission scripts: science collection, ascent, safe recovery; good for utility patterns.  https://github.com/Hansastro/KSP_Adventure
- **Genhis/KRPC.MechJeb** — kRPC service exposing MechJeb autopilots (ascent/plane etc.) for scriptable control.  https://github.com/Genhis/KRPC.MechJeb

> The ingest pipeline records **repo URL**, **commit hash**, **licence**, and **file paths** in every snippet record to ensure provenance and compliance.

---

## 4) How (Architecture)

### Mermaid: Pipeline Schematic
```mermaid
flowchart TD
  subgraph SRC[Sources]
    G1[GitHub repos]
    G2[kRPC docs & tutorials]
  end

  G1 -->|clone/fetch| P1[Repo Walker]
  P1 --> P2[Static Parser (AST)]
  P2 --> P3[Snippet Extractor]
  P3 --> M1[LLM Summariser & Tagger]
  P2 --> D1[Dependency Analyzer]
  D1 --> J1[Linker]
  M1 --> J1
  J1 --> S1[(Snippet Store JSONL/Parquet)]

  S1 --> I1[Keyword Index (inverted)]
  S1 --> I2[Embedding Store]

  subgraph SVR[MCP Server & Search API]
    Q1[Query Router]
    Q2[Keyword Search]
    Q3[Vector Search]
    Q4[Reranker]
    Q5[Resolver (deps)]
  end

  I1 --> Q2
  I2 --> Q3
  Q2 --> Q4
  Q3 --> Q4
  Q4 --> Q5
  Q5 --> O1[Results: snippet + deps + metadata]

  subgraph GOV[Governance]
    L1[Licence Auditor]
    E1[Eval Harness]
    C1[CI/QA]
  end

  S1 --> L1
  S1 --> E1
  SVR --> C1
  L1 --> C1
  E1 --> C1
```

---

## 5) Implementation Plan (Codex‑friendly, one commit per step)
Each step includes **Deliverables**, **Automated Tests** (scriptable), and **Manual Checks** (if applicable). Steps are designed to run locally and in CI.

### Phase A — Scaffolding & Data Contracts
**A1. Repo skeleton & config (implemented)**
- Deliverables (as implemented):
  - Side‑project folder `krpc-snippets/` containing the package and scaffolding only for this project.
  - Python package `krpc_snippets/` with a module‑based CLI `krpc_snippets.cli:main`.
  - Console script entry in root `pyproject.toml`: `krpc-snippets = "krpc_snippets.cli:main"`.
  - CLI subcommands (stubs): `ingest`, `enrich`, `index`, `search`, `search-hybrid`, `resolve`.
  - Quick‑start docs: `krpc-snippets/README.md`.
  - Environment template: `krpc-snippets/.env.example` (for later enrichment/embeddings).
  - Placeholders: `krpc-snippets/data/`, `krpc-snippets/artifacts/`, `krpc-snippets/ci/README.md`, `krpc-snippets/scripts/README.md`.
  - Plan file relocated to `krpc-snippets/k_rpc_mcp_rag_snippet_indexer_project_plan.md` (with this updated A1).
  - Note file at original location: `krpc_code_examples_rag/MOVED.md`.
- Auto Tests: Deferred to E4 (CI). For A1 we only added the CLI and structure; no lint/type gates yet.
- Manual: CLI help shows usage successfully.
  - Module: `uv --directory krpc-snippets run -m krpc_snippets.cli --help`
  - Console script (after editable install): `uv run krpc-snippets --help`

**A2. Snippet JSON schema (implemented)**
- Deliverables (as implemented):
  - Schema: `krpc_snippets/schemas/snippet.schema.json` with required fields `{ id, repo, commit, path, lang, name, description, code, categories[], dependencies[], license, license_url, created_at }` and optional metadata (`restricted`, `inputs`, `outputs`, `when_to_use`, `size_bytes`, `lines_of_code`).
  - Fixtures: `krpc-snippets/data/fixtures/snippet_valid.json` and `krpc-snippets/data/fixtures/snippet_invalid_missing_fields.json`.
  - Validator script: `krpc-snippets/scripts/schema_validate.py` (uses `jsonschema`).
- Auto: Run validator on fixtures; valid exits 0, invalid exits non‑zero.
  - `uv --directory . run python krpc-snippets/scripts/schema_validate.py krpc-snippets/data/fixtures/snippet_valid.json`
  - `uv --directory . run python krpc-snippets/scripts/schema_validate.py krpc-snippets/data/fixtures/snippet_invalid_missing_fields.json`
- Manual: Extend fixtures as needed; inspect errors for clarity and completeness.

**A3. Storage adapters (implemented)** (JSONL + Parquet + SQLite)
- Deliverables (as implemented):
  - JSONL adapter: `krpc_snippets/store/jsonl.py` → `write_jsonl`, `iter_jsonl` (atomic write, streaming read, optional validation; prunes None for optional fields).
  - Parquet adapter: `krpc_snippets/store/parquet.py` → `write_parquet`, `read_parquet` (requires `pyarrow`; array fields mapped to list types).
  - SQLite adapter: `krpc_snippets/store/sqlite.py` → `open_db`, `init_schema`, `upsert_snippet`, `bulk_insert`, `get_by_id`, `iter_all`, `query`.
    - Internal column `commit_sha` is mapped back to schema field `commit` on export.
    - Arrays stored as JSON TEXT; simple LIKE filter supported for `category` queries; WAL + NORMAL sync.
  - Types/helpers: `krpc_snippets/store/types.py` (dataclass, size/loc helpers), `krpc_snippets/store/validation.py` (jsonschema-backed, optional).
  - CLI utilities: `krpc-snippets/scripts/snippets_store_cli.py` with commands:
    - `jsonl-to-sqlite`, `sqlite-to-jsonl`, `jsonl-to-parquet`, `parquet-to-jsonl`, `count`, `head`.
- Auto (sanity):
  - Build JSONL from fixtures, import to SQLite, verify `count`/`head`, export back to JSONL with `--validate`.
  - Optional Parquet round-trip with `pyarrow` installed.
  - All checks pass on local fixtures (N=2).

### Phase B — Ingestion & Parsing
**B1. Git fetcher (implemented)**
- Deliverables (as implemented):
  - Module: `krpc_snippets/ingest/git_fetch.py` — clone/update, checkout by branch/SHA, resolve HEAD, default branch, and write manifest (`write_manifest`).
  - CLI: `krpc-snippets/scripts/fetch_repo.py` — single `--url` or batch `--file` (JSONL with `{url, branch?, sha?}`), options for `--depth` and `--out`.
  - Output layout: `krpc-snippets/data/repos/<slug>/` with `fetch.json` containing `{ repo_url, branch, sha, resolved_commit, default_branch, dest_path, fetched_at }`.
- Auto: Local offline test using a temporary git repo; verified resolved commit and manifest written.
- Manual: Fetching multiple seed repos via JSONL batch; inspect manifests and working copies.

**B2. File discovery & language detection (implemented)**
- Deliverables (as implemented):
  - Module: `krpc_snippets/ingest/walk_repo.py` — discovers Python files using `git ls-files` or filesystem walk; supports include/exclude globs, repo-level ignores via `.krpc-snippets-ignore`, default excluded directories, size cap, and returns stable sorted `FileInfo[]` with `sha256` and `size_bytes`.
  - CLI: `krpc-snippets/scripts/walk_repo_cli.py` — flags: `--root`, `--use-git`, `--max-size`, `--include`, `--exclude-dir`, `--exclude`, `--count`, `--head`.
- Auto: Synthetic local repo tree verified — default excludes applied, repo-level ignore patterns respected, deterministic ordering.

**B3. Python AST parser (implemented)**
- Deliverables (as implemented):
  - Module: `krpc_snippets/ingest/python_ast.py` — parses modules via `ast` + `tokenize` (encoding-aware); extracts top‑level functions/classes (with spans, docstrings, leading comments, decorators, params, returns), class methods, imports/from_imports, and an initial top-level constants block (UPPER_CASE assignments before first def/class).
  - CLI: `krpc-snippets/scripts/ast_parse_cli.py` — `--path`, `--json` (with `--no-code`), `--summary`, `--functions`, `--classes`, `--consts`.
- Auto: Sanity file under `krpc-snippets/data/test_repo_fs/a/sample.py` verified; line spans and names extracted correctly; const block detected.

**B4. Snippet extraction (implemented)**
- Deliverables (as implemented):
  - Module: `krpc_snippets/ingest/extract_snippets.py` — builds schema-compliant records from parsed AST (functions, methods, classes, first const block) with stable ids (hash of repo+commit+path+kind+qualname+span), provenance from CLI or `fetch.json`.
  - CLI: `krpc-snippets/scripts/extract_snippets.py` — supports single file or full repo extraction, sets default license fields, toggles to include/exclude kinds, optional schema validation, outputs JSONL.
- Auto: Sanity on sample file yields 4 records (function, class, method, const). Records validated prior to write; JSONL round-trip via store CLI succeeds.

**B5. Dependency analysis (implemented)**
- Deliverables (as implemented):
  - Module: `krpc_snippets/ingest/deps.py` — builds repo-wide symbol index (`module.func`, `module.Class.method`), analyzes per-function/method call sites using imports/aliases and attribute resolution, and resolves repo-local dependencies.
  - CLI: `krpc-snippets/scripts/deps_analyze_repo.py` — enriches existing or freshly extracted snippets with `dependencies[]`.
- Auto: Synthetic multi-file example verifies `a.main2.calls` depends on `pkg.util.helper`; class/method handling and non-local calls ignored.

**B6. Licence detector**
- Deliverables: `src/governance/license.py` (SPDX detection from LICENSE file + GitHub API fallback + file headers). Flags GPL‑family.
- Auto: Fixtures for MIT, BSD‑3, GPL‑3; sets `license` and `license_url`; marks `restricted=True` for GPL.

**B7. Provenance recorder**
- Deliverables: Attach `{repo, commit, path}` to every snippet; compute stable `id` = hash(repo+commit+path+span).
- Auto: Deterministic id test (same input→same id; different span→different id).

### Phase C — Enrichment (LLM) & Indexing
**C1. LLM summariser & tagger**
- Deliverables: `src/enrich/summarise.py` batching calls to the OpenAI API (or mock), producing `description`, `categories[]`, `inputs/outputs`, and “when to use”.
- Auto: Golden‑file tests using a local mock that returns stable outputs; validates field presence & length bounds.
- Manual: Spot‑check 10 outputs for correctness.

**C2. Embedding generator**
- Deliverables: `src/enrich/embed.py` generating embeddings for `name + description + code_head`. Pluggable model name.
- Auto: Mocked embedding client; vector dimension/shape checks; deterministic seed path.

**C3. Keyword index (inverted)**
- Deliverables: `src/index/keyword.py` (tokeniser + inverted index + boosted title/description weights). CLI: `scripts/search_keyword.py`.
- Auto: Query tests on fixtures (“circularise orbit” → expected ids appear in Top‑3).

**C4. Vector store & hybrid retrieval**
- Deliverables: `src/index/vector.py` (FAISS/SQLite); `src/search/hybrid.py` that merges keyword + vector results with simple rank fusion.
- Auto: Evaluate hybrid > keyword on a small benchmark; assert improvement.

**C5. Reranker (optional)**
- Deliverables: `src/search/rerank.py` (cross‑encoder or lightweight LLM re‑score for Top‑K).
- Auto: Offline metric shows NDCG@10 improvement ≥ pre‑set threshold.

### Phase D — Serving & Resolution
**D1. Dependency‑aware resolver**
- Deliverables: `src/resolve/resolve_snippet.py` that, given a snippet id, returns snippet + required helpers (bounded by size), with a topological order for paste‑ability.
- Auto: Graph tests on cross‑file fixtures; prevents cycles; respects size cap.

**D2. MCP tools**
- Deliverables: `src/mcp/tools.py` exposing `search_snippets(query)`, `get_snippet(id)`, `resolve_snippet(id)`, `search_and_resolve(query)`.
- Auto: Tool contract tests; JSON serialisation; error handling.

**D3. HTTP API (optional)**
- Deliverables: Minimal FastAPI app for local/dev consumption by other agents.
- Auto: Endpoint tests; OpenAPI schema validation.

### Phase E — Governance, Evaluation, CI
**E1. Licence auditor & policy**
- Deliverables: `scripts/audit_licenses.py` → report (counts by licence, restricted ids). Policy doc for reuse guidance.
- Auto: CI job fails if restricted snippets lack `restricted=True` or missing provenance.

**E2. Query benchmark & eval harness**
- Deliverables: `eval/queries.jsonl` (seed queries + expected ids), `scripts/eval_retrieval.py` computing Top‑K accuracy & NDCG.
- Auto: CI gate (e.g., Top‑3 ≥ 60% initially; ratchet upwards over time).
- Manual: Curator runbook for adjusting “goldens”.

**E3. Performance tests**
- Deliverables: `scripts/bench_search.py` measuring P95 latency and memory footprint on N≈5k snippets.
- Auto: Fails if latency > target; emits flamegraph (optional).

**E4. CI pipeline**
- Deliverables: GitHub Actions (lint, type, unit, eval, licence audit, build). Binary cache for embeddings if applicable.
- Auto: All steps green on PR; status badge.

### Phase F — Developer Experience & Docs
**F1. Codex CLI playbooks**
- Deliverables: `playbooks/codex/` with command snippets to: ingest a repo, enrich, index, search, resolve, and export.
- Auto: Dry‑run tests (no network) using mocks; ensures CLI examples don’t rot.
- Manual: End‑to‑end demo following the README.

**F2. User docs**
- Deliverables: `docs/` with “Getting Started”, “Ingestion”, “Search”, “Resolution”, “Licensing”, “Troubleshooting”.
- Auto: Link checker; doctest for inline code blocks where possible.

**F3. Release packaging**
- Deliverables: Versioned wheel; changelog; `--version` flag; SemVer tagging.
- Auto: Build + publish to test index; install‑from‑wheel smoke test.

---

## 6) Quality Gates (“Definition of Done” per Phase)
- **Index correctness:** All snippet records validate against schema; dependency graphs acyclic; resolver returns runnable bundle.
- **Retrieval quality:** Hybrid+rerank outperforms keyword‑only on benchmark queries.
- **Compliance:** 100% snippet records include licence + repo + commit; audit job passes.
- **Docs:** README quick‑start works from a clean checkout.

---

## 7) Risks & Mitigations
- **Licence complexity (GPL, AGPL):** Flag restricted licences; provide toggles to exclude or include with warnings.
- **Model hallucination in summaries:** Keep code‑first metadata authoritative; use concise prompts; sample manual review.
- **Cross‑file resolution bloat:** Cap helper inclusion; prefer links to related snippets beyond a depth.
- **Cost/latency of enrichment:** Batch requests; cache; allow offline mode with mock outputs for CI.

---

## 8) Operating the System
- **Repository management:** Functionality to manually or programmatically add new repositories later on; no periodic or automated ingest required.
- 
- **Security:** No secrets in records; redact absolute paths; sandbox any optional execution features.
