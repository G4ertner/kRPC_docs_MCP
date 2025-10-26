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
    ap = argparse.ArgumentParser(description="Print combined status overview from kRPC")
    ap.add_argument("--address", required=True)
    ap.add_argument("--rpc-port", type=int, default=50000)
    ap.add_argument("--stream-port", type=int, default=50001)
    ap.add_argument("--name", default="Overview Test")
    args = ap.parse_args()

    try:
        conn = connect_to_game(args.address, rpc_port=args.rpc_port, stream_port=args.stream_port, name=args.name)
    except KRPCConnectionError as e:
        print(f"Connect failed: {e}")
        return 1

    out = {
        "vessel": readers.vessel_info(conn),
        "environment": readers.environment_info(conn),
        "flight": readers.flight_snapshot(conn),
        "orbit": readers.orbit_info(conn),
        "time": readers.time_status(conn),
        "attitude": readers.attitude_status(conn),
        "aero": readers.aero_status(conn),
        "maneuver_nodes": readers.maneuver_nodes_basic(conn),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

