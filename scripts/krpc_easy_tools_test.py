import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.krpc.client import connect_to_game, KRPCConnectionError  # noqa: E402
from mcp_server.krpc import readers  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Test easy kRPC info tools against a running KSP+kRPC")
    ap.add_argument("--address", required=True)
    ap.add_argument("--rpc-port", type=int, default=50000)
    ap.add_argument("--stream-port", type=int, default=50001)
    ap.add_argument("--name", default="Easy Tools Test")
    args = ap.parse_args()

    try:
        conn = connect_to_game(args.address, rpc_port=args.rpc_port, stream_port=args.stream_port, name=args.name)
    except KRPCConnectionError as e:
        print(f"Connect failed: {e}")
        return 1

    tests = [
        ("vessel_info", readers.vessel_info),
        ("environment_info", readers.environment_info),
        ("flight_snapshot", readers.flight_snapshot),
        ("orbit_info", readers.orbit_info),
        ("time_status", readers.time_status),
        ("attitude_status", readers.attitude_status),
        ("aero_status", readers.aero_status),
        ("maneuver_nodes_basic", readers.maneuver_nodes_basic),
    ]
    for name, fn in tests:
        try:
            data = fn(conn)
        except Exception as e:  # pragma: no cover
            print(f"{name}: ERROR: {e}")
            continue
        print(f"\n{name}:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

