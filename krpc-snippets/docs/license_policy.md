License Policy (krpc-snippets)

Overview
- Every snippet record must include `license` (SPDX id), `license_url`, and provenance (`repo`, `commit`, `path`).
- GPL-family licenses (GPL/AGPL/LGPL) are considered restricted. Records should set `restricted=true` accordingly.

Guidelines
- Preferred detection sources:
  1. LICENSE/COPYING file at repo root (SPDX identifier or heuristic match)
  2. SPDX header in top lines of source files: `SPDX-License-Identifier: <ID>`
  3. If unknown, mark as `license=UNKNOWN` and avoid redistribution until clarified.

Enforcement
- Use `scripts/license_detect.py` to detect and enrich JSONL records with license fields.
- Use `scripts/audit_licenses.py` in CI to fail builds if policy violations occur:
  - `--fail-on-unknown` to block UNKNOWN licenses
  - `--fail-on-restricted` to block GPL-family
  - `--fail-on-mismatch` to catch incorrect `restricted` flags

Examples
- Detect only (writes `<repo>/license.json`):
  - `uv --directory . run python krpc-snippets/scripts/license_detect.py --root <repo> --write-summary`
- Enrich JSONL (fill missing license fields):
  - `uv --directory . run python krpc-snippets/scripts/license_detect.py --root <repo> --snippets <in.jsonl> --out <out.jsonl> --only-if-unknown --validate`
- Audit JSONL and fail on restricted:
  - `uv --directory . run python krpc-snippets/scripts/audit_licenses.py --snippets <snippets.jsonl> --fail-on-restricted --report krpc-snippets/data/license_audit.json`

