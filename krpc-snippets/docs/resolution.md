# Resolution

Goal
- Resolve a target snippet into a paste‑ready bundle with dependency code in a deterministic order, enforcing size caps.

CLI
- `krpc-snippets/scripts/resolve_snippet.py`
- By id:
  - `uv --directory . run python krpc-snippets/scripts/resolve_snippet.py --snippets krpc-snippets/data/snippets_extracted.jsonl --id <snippet_id> --out krpc-snippets/data/bundle.py`
- By fully‑qualified name:
  - `uv --directory . run python krpc-snippets/scripts/resolve_snippet.py --snippets krpc-snippets/data/snippets_extracted.jsonl --name a.sample.NavHelper.circ_dv --out krpc-snippets/data/bundle_navhelper.py`

Behavior
- Class methods emit their parent class to ensure method context
- Module‑level constant blocks (UPPER_CASE) are included first when referenced
- Cycles are ignored via a DAG guard; unresolved deps are reported
- Size caps: `--max-bytes` and `--max-nodes`; truncation is reported

Tips
- Prefer resolving by exact id for deterministic runs
- If targeting a method, ensure the parent class contains all needed methods for the use case or resolve the class directly

