# Repository Guidelines

## Project Structure & Module Organization
- `mcp_server/` — MCP server, kRPC tools, blueprint export, resources, prompts.
- `krpc_index/` — lightweight search index loader used by MCP tools.
- `scripts/` — scrapers, CLIs, and sanity tests (e.g., `*_test.py`).
- `data/` — JSONL datasets and manifests; `*.sqlite` caches.
- `artifacts/` — generated outputs (e.g., blueprint diagrams).
- Entry points (pyproject): `scrape-krpc-docs`, `krpc-mcp`.

## Build, Test, and Development Commands
- Setup (Python 3.10+):
  - `uv venv && source .venv/bin/activate`
  - `uv pip install -e .` (kRPC extras when needed: `-e .[krpc]`)
- Run MCP server:
  - `uv run -m mcp_server.main`  (or `uv run krpc-mcp`)
- Scrape docs → JSONL:
  - `uv run --with scrape scripts/scrape_krpc_docs.py --out data/krpc_python_docs.jsonl`
- Local search sanity check:
  - `uv run scripts/search_krpc_index.py "autopilot" --k 5`
- Build package: `uv build`

## Coding Style & Naming Conventions
- Python 3.10+, type hints, module docstrings, 4‑space indentation.
- Names: `snake_case` for files/functions, `UpperCamelCase` for classes.
- Prefer f‑strings, small pure helpers, explicit params; avoid globals (except server singleton `mcp_server/server.py:mcp`).
- Tools are verbs (`get_*`, `compute_*`); resources use `resource://...` names.

## Testing Guidelines
- No formal pytest suite yet. Use CLI sanity tests under `scripts/` (e.g.,
  `uv run scripts/krpc_overview_test.py`).
- For kRPC-dependent checks, pass your game PC address/ports explicitly and avoid destructive actions.
- When adding tools, include a minimal `scripts/*_test.py` that exits non‑zero on failure and prints readable state.

## Commit & Pull Request Guidelines
- Commits: imperative and scoped, e.g., `tools: add export_blueprint_diagram PNG path`.
- PRs must include: summary, linked issues, run steps, and any README/usage updates. Include example commands or output snippets when relevant.

## Security & Configuration Tips
- Do not hardcode private IPs, ports, or tokens. Accept via args/flags.
- Document side effects clearly; default examples to read‑only operations where possible.
