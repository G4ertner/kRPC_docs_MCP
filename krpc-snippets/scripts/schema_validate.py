#!/usr/bin/env python3
"""Validate snippet JSON files against the snippet JSON schema.

Usage:
  uv --directory . run python krpc-snippets/scripts/schema_validate.py <file1.json> [file2.json ...]

Notes:
- Requires the 'jsonschema' package. Install with: uv pip install jsonschema
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: schema_validate.py <file1.json> [file2.json ...]", file=sys.stderr)
        return 2
    try:
        import jsonschema  # type: ignore
    except Exception:
        print("jsonschema is required. Install with: uv pip install jsonschema", file=sys.stderr)
        return 2

    schema_path = Path(__file__).parents[1] / "krpc_snippets" / "schemas" / "snippet.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read schema: {e}", file=sys.stderr)
        return 2

    validator = jsonschema.Draft7Validator(schema)
    ok = True
    for p in argv:
        path = Path(p)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR {path}: cannot read/parse JSON: {e}")
            ok = False
            continue
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            ok = False
            print(f"INVALID {path}:")
            for err in errors:
                loc = "/".join(str(x) for x in err.path)
                print(f"  - {loc or '<root>'}: {err.message}")
        else:
            print(f"OK {path}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

