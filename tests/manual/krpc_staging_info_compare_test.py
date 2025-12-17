import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.utils.krpc_utils.client import KRPCConnectionError, connect_to_game  # noqa: E402
from mcp_server.utils.krpc_utils import readers  # noqa: E402


def _summarize(data: dict) -> dict:
    stages = data.get("stages") or []
    total_dv = 0.0
    bad_engines_no_prop = 0
    bad_prop_no_engines = 0
    bad_negative_m1 = 0
    for seg in stages:
        engines = int(seg.get("engines") or 0)
        prop = float(seg.get("prop_mass_kg") or 0.0)
        m1 = seg.get("m1_kg")
        dv = seg.get("delta_v_m_s")
        if dv is not None:
            try:
                total_dv += float(dv)
            except Exception:
                pass
        if engines > 0 and prop <= 0.0:
            bad_engines_no_prop += 1
        if engines <= 0 and prop > 0.0:
            bad_prop_no_engines += 1
        if m1 is not None and float(m1) < 0.0:
            bad_negative_m1 += 1
    return {
        "stages_count": len(stages),
        "total_delta_v_m_s": total_dv,
        "bad_engines_no_prop": bad_engines_no_prop,
        "bad_prop_no_engines": bad_prop_no_engines,
        "bad_negative_m1": bad_negative_m1,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare staging_info vs staging_info_legacy")
    ap.add_argument("--address", required=True)
    ap.add_argument("--rpc-port", type=int, default=50000)
    ap.add_argument("--stream-port", type=int, default=50001)
    ap.add_argument("--name", default="Staging Compare Test")
    ap.add_argument("--full", action="store_true", help="Print full stage JSON for both implementations")
    args = ap.parse_args()

    try:
        conn = connect_to_game(args.address, rpc_port=args.rpc_port, stream_port=args.stream_port, name=args.name)
    except KRPCConnectionError as e:
        print(f"Connect failed: {e}")
        return 1

    legacy = readers.staging_info_legacy(conn)
    current = readers.staging_info(conn)

    out = {
        "legacy_summary": _summarize(legacy),
        "current_summary": _summarize(current),
    }
    if args.full:
        out["legacy"] = legacy
        out["current"] = current

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

