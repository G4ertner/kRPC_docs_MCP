#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Dict, Any

from krpc_snippets.store import jsonl as jsonl_store
from krpc_snippets.store import parquet as pq_store
from krpc_snippets.store import sqlite as sql_store


def _load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    return jsonl_store.iter_jsonl(path)


def _write_jsonl(path: Path, recs: Iterable[Dict[str, Any]], validate: bool = False) -> int:
    return jsonl_store.write_jsonl(recs, path, append=False, validate=validate)


def cmd_jsonl_to_sqlite(args: argparse.Namespace) -> int:
    src = Path(args.infile)
    dst = Path(args.out)
    conn = sql_store.open_db(dst)
    sql_store.init_schema(conn)
    n = sql_store.bulk_insert(conn, _load_jsonl(src), validate=args.validate)
    print(f"Inserted {n} records into {dst}")
    return 0


def cmd_sqlite_to_jsonl(args: argparse.Namespace) -> int:
    src = Path(args.infile)
    dst = Path(args.out)
    conn = sql_store.open_db(src)
    recs = list(sql_store.iter_all(conn))
    n = _write_jsonl(dst, recs, validate=args.validate)
    print(f"Wrote {n} records to {dst}")
    return 0


def cmd_jsonl_to_parquet(args: argparse.Namespace) -> int:
    src = Path(args.infile)
    dst = Path(args.out)
    recs = list(_load_jsonl(src))
    n = pq_store.write_parquet(recs, dst, validate=args.validate)
    print(f"Wrote {n} records to {dst}")
    return 0


def cmd_parquet_to_jsonl(args: argparse.Namespace) -> int:
    src = Path(args.infile)
    dst = Path(args.out)
    recs = pq_store.read_parquet(src, validate=args.validate)
    n = _write_jsonl(dst, recs, validate=args.validate)
    print(f"Wrote {n} records to {dst}")
    return 0


def cmd_count(args: argparse.Namespace) -> int:
    src = Path(args.infile)
    kind = args.kind
    if kind == "jsonl":
        n = sum(1 for _ in jsonl_store.iter_jsonl(src))
    elif kind == "parquet":
        n = len(pq_store.read_parquet(src))
    elif kind == "sqlite":
        conn = sql_store.open_db(src)
        cur = conn.execute("SELECT COUNT(*) FROM snippets")
        n = int(cur.fetchone()[0])
    else:
        raise SystemExit(f"Unknown kind: {kind}")
    print(n)
    return 0


def cmd_head(args: argparse.Namespace) -> int:
    src = Path(args.infile)
    kind = args.kind
    n = int(args.n)
    items: list[Dict[str, Any]]
    if kind == "jsonl":
        items = [x for i, x in enumerate(jsonl_store.iter_jsonl(src)) if i < n]
    elif kind == "parquet":
        items = pq_store.read_parquet(src)[:n]
    elif kind == "sqlite":
        conn = sql_store.open_db(src)
        items = [x for i, x in enumerate(sql_store.iter_all(conn)) if i < n]
    else:
        raise SystemExit(f"Unknown kind: {kind}")
    for it in items:
        print(json.dumps(it, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="krpc-snippets store CLI")
    sub = p.add_subparsers(dest="cmd", metavar="command")

    # jsonl->sqlite
    sp = sub.add_parser("jsonl-to-sqlite", help="Import JSONL into SQLite")
    sp.add_argument("--in", dest="infile", required=True)
    sp.add_argument("--out", dest="out", required=True)
    sp.add_argument("--validate", action="store_true")
    sp.set_defaults(func=cmd_jsonl_to_sqlite)

    # sqlite->jsonl
    sp = sub.add_parser("sqlite-to-jsonl", help="Export SQLite to JSONL")
    sp.add_argument("--in", dest="infile", required=True)
    sp.add_argument("--out", dest="out", required=True)
    sp.add_argument("--validate", action="store_true")
    sp.set_defaults(func=cmd_sqlite_to_jsonl)

    # jsonl->parquet
    sp = sub.add_parser("jsonl-to-parquet", help="Convert JSONL to Parquet")
    sp.add_argument("--in", dest="infile", required=True)
    sp.add_argument("--out", dest="out", required=True)
    sp.add_argument("--validate", action="store_true")
    sp.set_defaults(func=cmd_jsonl_to_parquet)

    # parquet->jsonl
    sp = sub.add_parser("parquet-to-jsonl", help="Convert Parquet to JSONL")
    sp.add_argument("--in", dest="infile", required=True)
    sp.add_argument("--out", dest="out", required=True)
    sp.add_argument("--validate", action="store_true")
    sp.set_defaults(func=cmd_parquet_to_jsonl)

    # count
    sp = sub.add_parser("count", help="Count records in a store")
    sp.add_argument("kind", choices=("jsonl", "parquet", "sqlite"))
    sp.add_argument("infile")
    sp.set_defaults(func=cmd_count)

    # head
    sp = sub.add_parser("head", help="Print first N records")
    sp.add_argument("kind", choices=("jsonl", "parquet", "sqlite"))
    sp.add_argument("infile")
    sp.add_argument("--n", default=5)
    sp.set_defaults(func=cmd_head)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

