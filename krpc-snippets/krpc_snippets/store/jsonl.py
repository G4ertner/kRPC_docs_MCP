from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, Iterator, Dict, Any

from .validation import validate_snippet


_OPT_KEYS = ("restricted", "inputs", "outputs", "when_to_use", "size_bytes", "lines_of_code")


def _prune_nones(obj: Dict[str, Any]) -> Dict[str, Any]:
    o = dict(obj)
    for k in _OPT_KEYS:
        if k in o and o[k] is None:
            del o[k]
    return o


def _ensure_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_jsonl(snippets: Iterable[Dict[str, Any]], path: str | Path, *, append: bool = False, validate: bool = False) -> int:
    p = _ensure_path(path)
    mode = "a" if append and p.exists() else "w"
    if mode == "w":
        # Atomic write: write to temp and rename
        fd, tmpname = tempfile.mkstemp(prefix=p.name + ".", dir=str(p.parent))
        os.close(fd)
        tmp = Path(tmpname)
        written = 0
        try:
            with tmp.open("w", encoding="utf-8") as f:
                for obj in snippets:
                    obj = _prune_nones(obj)
                    if validate:
                        errs = validate_snippet(obj)
                        if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                            raise ValueError("Invalid snippet: " + "; ".join(errs))
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    written += 1
            tmp.replace(p)
            return written
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
    else:
        written = 0
        with p.open("a", encoding="utf-8") as f:
            for obj in snippets:
                obj = _prune_nones(obj)
                if validate:
                    errs = validate_snippet(obj)
                    if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                        raise ValueError("Invalid snippet: " + "; ".join(errs))
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                written += 1
        return written


def iter_jsonl(path: str | Path, *, validate: bool = False) -> Iterator[Dict[str, Any]]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                raise ValueError(f"Invalid JSON on line {i}: {e}")
            if validate:
                errs = validate_snippet(obj)
                if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                    raise ValueError(f"Invalid snippet on line {i}: {'; '.join(errs)}")
            yield obj
