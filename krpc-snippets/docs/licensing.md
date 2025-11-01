# Licensing

Policy
- See detailed policy: `krpc-snippets/docs/license_policy.md`
- Restricted families (GPL/AGPL/LGPL) can be excluded during search and flagged during audits.

Detection & enrichment
- CLI: `krpc-snippets/scripts/license_detect.py`
- Detect repository license via LICENSE text or SPDX headers; enrich snippet JSONL with `license`, `license_url`, and `restricted`.
- Examples:
  - Detect only: `uv --directory . run python krpc-snippets/scripts/license_detect.py --root <repo> --write-summary`
  - Enrich: `uv --directory . run python krpc-snippets/scripts/license_detect.py --root <repo> --snippets <in.jsonl> --out <out.jsonl> --only-if-unknown --validate`

Auditing
- CLI: `krpc-snippets/scripts/audit_licenses.py`
- Report restricted snippets and overall counts:
  - `uv --directory . run python krpc-snippets/scripts/audit_licenses.py --snippets krpc-snippets/data/snippets_enriched.jsonl --report krpc-snippets/data/license_audit.json`

Search filters
- Use `--exclude-restricted` for keyword/hybrid search CLIs and the MCP tools to hide GPL‑family content when needed.

