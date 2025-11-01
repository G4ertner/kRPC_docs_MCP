from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Dict, Any


def _ensure_pyarrow():
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
        return pa, pq
    except Exception as e:  # pragma: no cover - optional dep
        raise RuntimeError(
            "pyarrow is required for Parquet support. Install with 'uv pip install pyarrow'."
        ) from e


_ARRAY_FIELDS = ("categories", "dependencies", "inputs", "outputs")


def _normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    obj = dict(rec)
    # Ensure optional fields exist (nullable)
    for k in ("restricted", "inputs", "outputs", "when_to_use", "size_bytes", "lines_of_code"):
        obj.setdefault(k, None)
    # Ensure arrays are lists or None
    for k in _ARRAY_FIELDS:
        v = obj.get(k)
        if v is None:
            continue
        if not isinstance(v, list):
            obj[k] = [str(v)]
    return obj


def write_parquet(snippets: Iterable[Dict[str, Any]], path: str | Path, *, validate: bool = False) -> int:
    pa, pq = _ensure_pyarrow()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    count = 0
    from .validation import validate_snippet

    for rec in snippets:
        if validate:
            errs = validate_snippet(rec)
            if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                raise ValueError("Invalid snippet: " + "; ".join(errs))
        rows.append(_normalize_record(rec))
        count += 1

    if not rows:
        # Write empty table with schema inferred from _example
        fields = [
            ("id", pa.string()),
            ("repo", pa.string()),
            ("commit", pa.string()),
            ("path", pa.string()),
            ("lang", pa.string()),
            ("name", pa.string()),
            ("description", pa.string()),
            ("code", pa.string()),
            ("categories", pa.list_(pa.string())),
            ("dependencies", pa.list_(pa.string())),
            ("license", pa.string()),
            ("license_url", pa.string()),
            ("created_at", pa.string()),
            ("restricted", pa.bool_()),
            ("inputs", pa.list_(pa.string())),
            ("outputs", pa.list_(pa.string())),
            ("when_to_use", pa.string()),
            ("size_bytes", pa.int64()),
            ("lines_of_code", pa.int64()),
        ]
        schema = pa.schema([(n, t) for n, t in fields])
        empty = pa.Table.from_arrays([pa.array([], type=t) for _, t in fields], names=[n for n, _ in fields])
        pq.write_table(empty, p)
        return 0

    # Build columns
    def col(name: str, typ):
        return pa.array([r.get(name) for r in rows], type=typ)

    table = pa.Table.from_arrays(
        [
            col("id", pa.string()),
            col("repo", pa.string()),
            col("commit", pa.string()),
            col("path", pa.string()),
            col("lang", pa.string()),
            col("name", pa.string()),
            col("description", pa.string()),
            col("code", pa.string()),
            col("categories", pa.list_(pa.string())),
            col("dependencies", pa.list_(pa.string())),
            col("license", pa.string()),
            col("license_url", pa.string()),
            col("created_at", pa.string()),
            col("restricted", pa.bool_()),
            col("inputs", pa.list_(pa.string())),
            col("outputs", pa.list_(pa.string())),
            col("when_to_use", pa.string()),
            col("size_bytes", pa.int64()),
            col("lines_of_code", pa.int64()),
        ],
        names=[
            "id",
            "repo",
            "commit",
            "path",
            "lang",
            "name",
            "description",
            "code",
            "categories",
            "dependencies",
            "license",
            "license_url",
            "created_at",
            "restricted",
            "inputs",
            "outputs",
            "when_to_use",
            "size_bytes",
            "lines_of_code",
        ],
    )
    pq.write_table(table, p)
    return count


def read_parquet(path: str | Path, *, validate: bool = False) -> List[Dict[str, Any]]:
    pa, pq = _ensure_pyarrow()
    p = Path(path)
    table = pq.read_table(p)
    out: List[Dict[str, Any]] = []
    py = table.to_pylist()
    from .validation import validate_snippet

    for rec in py:
        # Ensure None for missing optional fields
        rec = _normalize_record(rec)
        if validate:
            errs = validate_snippet(rec)
            if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                raise ValueError("Invalid snippet: " + "; ".join(errs))
        out.append(rec)
    return out

