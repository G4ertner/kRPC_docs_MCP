from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Iterator, Dict, Any, Optional


def open_db(path: str | Path) -> sqlite3.Connection:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snippets (
            id TEXT PRIMARY KEY,
            repo TEXT NOT NULL,
            commit_sha TEXT NOT NULL,
            path TEXT NOT NULL,
            lang TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            code TEXT NOT NULL,
            categories TEXT NOT NULL,
            dependencies TEXT NOT NULL,
            license TEXT NOT NULL,
            license_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            restricted INTEGER,
            inputs TEXT,
            outputs TEXT,
            when_to_use TEXT,
            size_bytes INTEGER,
            lines_of_code INTEGER
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snippets_commit ON snippets(commit_sha);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snippets_repo ON snippets(repo);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snippets_lang ON snippets(lang);")
    conn.commit()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    obj = dict(row)
    # Map DB column commit_sha -> schema field commit
    if "commit_sha" in obj:
        obj["commit"] = obj.pop("commit_sha")
    # Decode JSON arrays
    for k in ("categories", "dependencies", "inputs", "outputs"):
        v = obj.get(k)
        if isinstance(v, str):
            try:
                obj[k] = json.loads(v)
            except Exception:
                obj[k] = None
    # restricted integer -> bool
    if obj.get("restricted") is not None:
        obj["restricted"] = bool(obj["restricted"])
    return obj


def _encode_arrays(obj: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(obj)
    # Ensure optional nullable keys exist for parameter binding
    for k in ("restricted", "inputs", "outputs", "when_to_use", "size_bytes", "lines_of_code"):
        out.setdefault(k, None)
    for k in ("categories", "dependencies", "inputs", "outputs"):
        v = out.get(k)
        if v is None:
            out[k] = None
        else:
            out[k] = json.dumps(list(v))
    if out.get("restricted") is not None:
        out["restricted"] = 1 if out["restricted"] else 0
    return out


def upsert_snippet(conn: sqlite3.Connection, rec: Dict[str, Any], *, validate: bool = False) -> None:
    if validate:
        from .validation import validate_snippet

        errs = validate_snippet(rec)
        if errs and not all(e.startswith("jsonschema not installed") for e in errs):
            raise ValueError("Invalid snippet: " + "; ".join(errs))

    r = _encode_arrays(rec)
    conn.execute(
        """
        INSERT INTO snippets (
            id, repo, commit_sha, path, lang, name, description, code,
            categories, dependencies, license, license_url, created_at,
            restricted, inputs, outputs, when_to_use, size_bytes, lines_of_code
        ) VALUES (
            :id, :repo, :commit, :path, :lang, :name, :description, :code,
            :categories, :dependencies, :license, :license_url, :created_at,
            :restricted, :inputs, :outputs, :when_to_use, :size_bytes, :lines_of_code
        )
        ON CONFLICT(id) DO UPDATE SET
            repo=excluded.repo,
            commit_sha=excluded.commit_sha,
            path=excluded.path,
            lang=excluded.lang,
            name=excluded.name,
            description=excluded.description,
            code=excluded.code,
            categories=excluded.categories,
            dependencies=excluded.dependencies,
            license=excluded.license,
            license_url=excluded.license_url,
            created_at=excluded.created_at,
            restricted=excluded.restricted,
            inputs=excluded.inputs,
            outputs=excluded.outputs,
            when_to_use=excluded.when_to_use,
            size_bytes=excluded.size_bytes,
            lines_of_code=excluded.lines_of_code
        ;
        """,
        r,
    )
    conn.commit()


def bulk_insert(conn: sqlite3.Connection, recs: Iterable[Dict[str, Any]], *, validate: bool = False, batch_size: int = 500) -> int:
    from itertools import islice

    total = 0

    def chunk(it, size):
        it = iter(it)
        while True:
            buf = list(islice(it, size))
            if not buf:
                return
            yield buf

    for chunked in chunk(recs, batch_size):
        to_write = []
        if validate:
            from .validation import validate_snippet

            for r in chunked:
                errs = validate_snippet(r)
                if errs and not all(e.startswith("jsonschema not installed") for e in errs):
                    raise ValueError("Invalid snippet: " + "; ".join(errs))
                to_write.append(_encode_arrays(r))
        else:
            to_write = [_encode_arrays(r) for r in chunked]

        conn.executemany(
            """
            INSERT INTO snippets (
                id, repo, commit_sha, path, lang, name, description, code,
                categories, dependencies, license, license_url, created_at,
                restricted, inputs, outputs, when_to_use, size_bytes, lines_of_code
            ) VALUES (
                :id, :repo, :commit, :path, :lang, :name, :description, :code,
                :categories, :dependencies, :license, :license_url, :created_at,
                :restricted, :inputs, :outputs, :when_to_use, :size_bytes, :lines_of_code
            )
            ON CONFLICT(id) DO UPDATE SET
                repo=excluded.repo,
                commit_sha=excluded.commit_sha,
                path=excluded.path,
                lang=excluded.lang,
                name=excluded.name,
                description=excluded.description,
                code=excluded.code,
                categories=excluded.categories,
                dependencies=excluded.dependencies,
                license=excluded.license,
                license_url=excluded.license_url,
                created_at=excluded.created_at,
                restricted=excluded.restricted,
                inputs=excluded.inputs,
                outputs=excluded.outputs,
                when_to_use=excluded.when_to_use,
                size_bytes=excluded.size_bytes,
                lines_of_code=excluded.lines_of_code
            ;
            """,
            to_write,
        )
        total += len(to_write)
        conn.commit()
    return total


def get_by_id(conn: sqlite3.Connection, id: str) -> Optional[Dict[str, Any]]:
    cur = conn.execute("SELECT * FROM snippets WHERE id = ?", (id,))
    row = cur.fetchone()
    return _row_to_dict(row) if row else None


def iter_all(conn: sqlite3.Connection) -> Iterator[Dict[str, Any]]:
    cur = conn.execute("SELECT * FROM snippets")
    for row in cur:
        yield _row_to_dict(row)


def query(
    conn: sqlite3.Connection,
    *,
    lang: Optional[str] = None,
    category: Optional[str] = None,
    license: Optional[str] = None,
    limit: int = 100,
) -> list[Dict[str, Any]]:
    sql = "SELECT * FROM snippets"
    where = []
    params: list[Any] = []  # type: ignore[name-defined]
    if lang:
        where.append("lang = ?")
        params.append(lang)
    if license:
        where.append("license = ?")
        params.append(license)
    if category:
        # Simple LIKE search on JSON-encoded list
        where.append("categories LIKE ?")
        params.append(f'%"{category}"%')
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " LIMIT ?"
    params.append(int(limit))
    cur = conn.execute(sql, params)
    return [_row_to_dict(r) for r in cur.fetchall()]
