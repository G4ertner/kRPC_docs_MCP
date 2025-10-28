#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from mcp_server.krpc.client import connect_to_game
from mcp_server.krpc import readers


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch vessel blueprint and ASCII summary via kRPC")
    p.add_argument("--address", required=True)
    p.add_argument("--rpc-port", type=int, default=50000)
    p.add_argument("--stream-port", type=int, default=50001)
    p.add_argument("--name", default="Blueprint CLI")
    args = p.parse_args()

    conn = connect_to_game(args.address, rpc_port=args.rpc_port, stream_port=args.stream_port, name=args.name)
    bp = readers.vessel_blueprint(conn)
    print(json.dumps(bp, indent=2))
    print("\n----- ASCII -----\n")
    print(readers.blueprint_ascii(conn))


if __name__ == "__main__":
    main()

