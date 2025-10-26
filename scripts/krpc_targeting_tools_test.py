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
    ap = argparse.ArgumentParser(description="Test listing/setting targets")
    ap.add_argument("--address", required=True)
    ap.add_argument("--rpc-port", type=int, default=50000)
    ap.add_argument("--stream-port", type=int, default=50001)
    ap.add_argument("--name", default="Target Test")
    ap.add_argument("--body", default="")
    ap.add_argument("--vessel", default="")
    args = ap.parse_args()

    try:
        conn = connect_to_game(args.address, rpc_port=args.rpc_port, stream_port=args.stream_port, name=args.name)
    except KRPCConnectionError as e:
        print(f"Connect failed: {e}")
        return 1

    print("Bodies:")
    print(json.dumps(readers.list_bodies(conn)[:10], indent=2, ensure_ascii=False))

    print("\nVessels:")
    print(json.dumps(readers.list_vessels(conn)[:10], indent=2, ensure_ascii=False))

    if args.body:
        try:
            b = conn.space_center.bodies.get(args.body)
            if b is None:
                print(f"Body '{args.body}' not found")
            else:
                conn.space_center.active_vessel.target_body = b
                print(f"Set target body: {args.body}")
        except Exception as e:
            print(f"Failed to set target body: {e}")

    if args.vessel:
        try:
            sc = conn.space_center
            vs = [ov for ov in sc.vessels if ov.name == args.vessel]
            if not vs:
                vs = [ov for ov in sc.vessels if ov.name.lower() == args.vessel.lower()]
            if not vs:
                print(f"Vessel '{args.vessel}' not found")
            else:
                conn.space_center.active_vessel.target_vessel = vs[0]
                print(f"Set target vessel: {vs[0].name}")
        except Exception as e:
            print(f"Failed to set target vessel: {e}")

    print("\nNavigation:")
    print(json.dumps(readers.navigation_info(conn), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

