# Ingestion

Steps overview
- Fetch repositories (clone/update)
- Walk files with repo-level excludes
- Extract snippets (AST-based)
- Analyze dependencies
- Detect/enrich licenses
- Audit provenance

Fetch repositories
- CLI: `krpc-snippets/scripts/fetch_repo.py`
- Single repo:
  - `uv --directory . run python krpc-snippets/scripts/fetch_repo.py --url /path/to/local/repo --out krpc-snippets/data/repos`
- Batch from JSONL (lines like `{ "url": "...", "branch": "main", "sha": "..." }`):
  - `uv --directory . run python krpc-snippets/scripts/fetch_repo.py --file repos.jsonl --out krpc-snippets/data/repos`

Walk & filter files
- CLI: `krpc-snippets/scripts/walk_repo_cli.py`
- Examples:
  - `uv --directory . run python krpc-snippets/scripts/walk_repo_cli.py --root krpc-snippets/data/repos/<slug> --count`
  - `uv --directory . run python krpc-snippets/scripts/walk_repo_cli.py --root krpc-snippets/data/repos/<slug> --head 5`
- Repo-level ignores: create `.krpc-snippets-ignore` in the repo root with glob lines and `#` comments.

Extract snippets
- CLI: `krpc-snippets/scripts/extract_snippets.py`
- Single file:
  - `uv --directory . run python krpc-snippets/scripts/extract_snippets.py --root <repo> --file a/sample.py --out krpc-snippets/data/snippets.jsonl --license MIT --license-url https://opensource.org/licenses/MIT --validate`
- Whole repo:
  - `uv --directory . run python krpc-snippets/scripts/extract_snippets.py --root <repo> --all --out krpc-snippets/data/snippets_extracted.jsonl`

Dependencies
- CLI: `krpc-snippets/scripts/deps_analyze_repo.py`
- Attach dependency info to extracted snippets:
  - `uv --directory . run python krpc-snippets/scripts/deps_analyze_repo.py --root <repo> --extract --out krpc-snippets/data/snippets_with_deps.jsonl`

Licensing
- CLI: `krpc-snippets/scripts/license_detect.py`
- Detect only:
  - `uv --directory . run python krpc-snippets/scripts/license_detect.py --root <repo> --write-summary`
- Enrich JSONL:
  - `uv --directory . run python krpc-snippets/scripts/license_detect.py --root <repo> --snippets <in.jsonl> --out <out.jsonl> --only-if-unknown --validate`
- Policy: add `--fail-on-restricted` to exit non‑zero for GPL-family.

Provenance audit
- CLI: `krpc-snippets/scripts/provenance_audit.py`
- Audit/fix repo+commit+path consistency:
  - `uv --directory . run python krpc-snippets/scripts/provenance_audit.py --in krpc-snippets/data/snippets_extracted.jsonl --out krpc-snippets/data/snippets_fixed.jsonl --validate`

Storage adapters
- Convert datasets between JSONL/SQLite/Parquet with `krpc-snippets/scripts/snippets_store_cli.py`.

