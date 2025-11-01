#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, List

from krpc_snippets.ingest.python_ast import parse_python_module


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Parse a Python file into an AST summary for snippet extraction")
    p.add_argument("--path", required=True)
    p.add_argument("--json", action="store_true", help="Print full JSON summary")
    p.add_argument("--no-code", action="store_true", help="Omit code spans in JSON output")
    p.add_argument("--summary", action="store_true", help="Print counts (functions/classes/consts)")
    p.add_argument("--functions", action="store_true", help="Print function names with line spans")
    p.add_argument("--classes", action="store_true", help="Print class names and methods with spans")
    p.add_argument("--consts", action="store_true", help="Print const block span and names")

    args = p.parse_args(argv)
    path = Path(args.path)
    if not path.exists():
        print(f"Not found: {path}")
        return 1
    mod = parse_python_module(path)
    if args.json:
        data = json.loads(json.dumps(mod, default=lambda o: o.__dict__, ensure_ascii=False))
        if args.no_code:
            # Remove code_span fields
            for fn in data.get("functions", []) or []:
                fn.pop("code_span", None)
            for cls in data.get("classes", []) or []:
                cls.pop("code_span", None)
                for m in cls.get("methods", []) or []:
                    m.pop("code_span", None)
            for cb in data.get("const_blocks", []) or []:
                cb.pop("code_span", None)
        print(json.dumps(data, ensure_ascii=False))
        return 0
    if args.summary:
        print(f"functions={len(mod.functions)} classes={len(mod.classes)} const_blocks={len(mod.const_blocks)} parse_error={mod.parse_error is not None}")
    if args.functions:
        for fn in mod.functions:
            print(f"fn {fn.qualname} {fn.lineno}-{fn.end_lineno}")
    if args.classes:
        for cls in mod.classes:
            print(f"class {cls.qualname} {cls.lineno}-{cls.end_lineno}")
            for m in cls.methods:
                print(f"  method {m.qualname} {m.lineno}-{m.end_lineno}")
    if args.consts:
        for cb in mod.const_blocks:
            print(f"consts {cb.lineno}-{cb.end_lineno} names={','.join(cb.assignments)}")
    if not (args.summary or args.functions or args.classes or args.consts):
        # default to summary
        print(f"functions={len(mod.functions)} classes={len(mod.classes)} const_blocks={len(mod.const_blocks)} parse_error={mod.parse_error is not None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

