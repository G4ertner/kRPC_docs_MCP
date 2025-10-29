#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mcp_server.executor_tools import execute_script


def main() -> None:
    p = argparse.ArgumentParser(description="Execute a Python script via kRPC MCP executor")
    p.add_argument("--address", required=True)
    p.add_argument("--rpc-port", type=int, default=50000)
    p.add_argument("--stream-port", type=int, default=50001)
    p.add_argument("--name", default=None)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--no-pause", action="store_true")
    p.add_argument("--no-unpause-start", action="store_true")
    p.add_argument("--allow-imports", action="store_true")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--code", help="Inline code string")
    src.add_argument("--file", help="Path to a .py file with code")
    args = p.parse_args()

    if args.code:
        code = args.code
    else:
        code = Path(args.file).read_text(encoding="utf-8")

    out = execute_script(
        code=code,
        address=args.address,
        rpc_port=args.rpc_port,
        stream_port=args.stream_port,
        name=args.name,
        timeout_sec=args.timeout,
        pause_on_end=not args.no_pause,
        unpause_on_start=not args.no_unpause_start,
        allow_imports=args.allow_imports,
    )
    print(out)


if __name__ == "__main__":
    main()
