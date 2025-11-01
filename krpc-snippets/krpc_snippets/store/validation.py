from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any


@lru_cache(maxsize=1)
def _load_schema() -> Dict[str, Any]:
    here = Path(__file__).resolve().parents[1]
    schema_path = here / "schemas" / "snippet.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_snippet(obj: Dict[str, Any]) -> List[str]:
    """Return a list of validation error messages. Empty list means valid.

    Lazy-imports jsonschema to keep core import light.
    """
    try:
        import jsonschema  # type: ignore
    except Exception as e:  # pragma: no cover - optional dependency missing
        return [
            "jsonschema not installed — install with 'uv pip install jsonschema' to validate",
            f"Import error: {e}",
        ]
    schema = _load_schema()
    validator = jsonschema.Draft7Validator(schema)
    errs = []
    for err in sorted(validator.iter_errors(obj), key=lambda e: e.path):
        loc = "/".join(str(x) for x in err.path) or "<root>"
        errs.append(f"{loc}: {err.message}")
    return errs

