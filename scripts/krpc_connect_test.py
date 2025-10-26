import argparse
import sys
from pathlib import Path

# Ensure project root import
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.krpc.client import connect_to_game, KRPCConnectionError  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Test connectivity to a running kRPC server (Protobuf over TCP)")
    ap.add_argument("--address", required=True, help="LAN IP or hostname of the PC running KSP+kRPC")
    ap.add_argument("--rpc-port", type=int, default=50000)
    ap.add_argument("--stream-port", type=int, default=50001)
    ap.add_argument("--name", default="Codex Connectivity Test")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--print-vessel", action="store_true", help="Also print the active vessel name if available")
    args = ap.parse_args()

    try:
        conn = connect_to_game(
            address=args.address,
            rpc_port=args.rpc_port,
            stream_port=args.stream_port,
            name=args.name,
            timeout=args.timeout,
        )
    except KRPCConnectionError as e:
        print(f"Connection failed: {e}")
        return 1

    version = conn.krpc.get_status().version
    print(f"Connected to kRPC at {args.address}:{args.rpc_port}/{args.stream_port}")
    print(f"Server version: {version}")

    if args.print_vessel:
        try:
            v = conn.space_center.active_vessel
            print(f"Active vessel: {v.name}")
        except Exception as e:  # pragma: no cover
            print(f"Connected, but failed to read active vessel: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

