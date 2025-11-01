# Fetch & Ingest

```bash
# 1) Fetch a repo (local path or HTTPS URL)
uv --directory . run python krpc-snippets/scripts/fetch_repo.py \
  --url /path/to/repo --out krpc-snippets/data/repos

# 2) Walk the repo (count & head)
uv --directory . run python krpc-snippets/scripts/walk_repo_cli.py \
  --root krpc-snippets/data/repos/<slug> --count
uv --directory . run python krpc-snippets/scripts/walk_repo_cli.py \
  --root krpc-snippets/data/repos/<slug> --head 5

# 3) Extract snippets (schema‑validated)
SN=krpc-snippets/data/snippets_extracted.jsonl
uv --directory . run python krpc-snippets/scripts/extract_snippets.py \
  --root krpc-snippets/data/repos/<slug> --all --out $SN --validate

# 4) Analyze dependencies
uv --directory . run python krpc-snippets/scripts/deps_analyze_repo.py \
  --root krpc-snippets/data/repos/<slug> --snippets $SN --out $SN --validate

# 5) License detect/enrich (only-if-unknown)
uv --directory . run python krpc-snippets/scripts/license_detect.py \
  --root krpc-snippets/data/repos/<slug> --snippets $SN --out $SN --only-if-unknown --validate

# 6) Provenance audit/fix (fill repo/commit/path; repair id if spans resolve)
uv --directory . run python krpc-snippets/scripts/provenance_audit.py \
  --root krpc-snippets/data/repos/<slug> --snippets $SN --fix --out $SN --repair-id --validate
```
