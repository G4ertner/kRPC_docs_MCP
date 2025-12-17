import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.utils.krpc_utils.client import KRPCConnectionError, connect_to_game  # noqa: E402
from mcp_server.utils.krpc_utils import readers  # noqa: E402


def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "vessel"
    s = re.sub(r"[^\w\-\.]+", "_", s, flags=re.UNICODE)
    return s[:80] if len(s) > 80 else s


def _enum_name(x) -> str | None:
    try:
        return getattr(x, "name", None) or str(x)
    except Exception:
        return None


def _vessel_label(v) -> str:
    name = getattr(v, "name", "vessel")
    situation = _enum_name(getattr(v, "situation", None)) or "unknown"
    body = None
    try:
        body = v.orbit.body.name
    except Exception:
        body = None
    return f"{name} [{situation}{' @ ' + body if body else ''}]"


def _wait_for_active_vessel(sc, expected_vessel, *, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if sc.active_vessel == expected_vessel:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for active vessel switch to complete.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture staging_info legacy/current + screenshots for multiple vessels.")
    ap.add_argument("--address", required=True)
    ap.add_argument("--rpc-port", type=int, default=50000)
    ap.add_argument("--stream-port", type=int, default=50001)
    ap.add_argument("--name", default="Staging Bulk Capture")
    ap.add_argument("--out", default="artifacts/staging_info_bulk_capture.json")
    ap.add_argument("--screenshot-scale", type=int, default=4)
    ap.add_argument("--include-debris", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Optional limit on number of vessels processed (0=all).")
    args = ap.parse_args()

    try:
        conn = connect_to_game(args.address, rpc_port=args.rpc_port, stream_port=args.stream_port, name=args.name)
    except KRPCConnectionError as e:
        print(f"Connect failed: {e}")
        return 1

    sc = conn.space_center
    scale = max(1, min(int(args.screenshot_scale), 4))

    screenshot_dir = Path("artifacts") / "screenshots" / "staging_info_bulk"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    vessels = list(sc.vessels)
    if not args.include_debris:
        vessels = [v for v in vessels if str(getattr(v, "type", None)) != "VesselType.debris"]

    # Prefer starting with the vessel on the launch pad.
    # Some saves report the pad vessel as pre_launch, others as landed.
    pad = None
    try:
        pad = next(
            (
                v
                for v in vessels
                if str(getattr(v, "situation", None)) in ("VesselSituation.pre_launch", "VesselSituation.landed")
            ),
            None,
        )
    except Exception:
        pad = None

    if pad is not None:
        ordered: list = [pad] + [v for v in vessels if v != pad]
    else:
        active = sc.active_vessel
        if not args.include_debris and str(getattr(active, "type", None)) == "VesselType.debris":
            active = vessels[0] if vessels else active
        ordered = [active] + [v for v in vessels if v != active]
    if args.limit and args.limit > 0:
        ordered = ordered[: int(args.limit)]

    results = {
        "captured_at_unix": time.time(),
        "address": args.address,
        "rpc_port": args.rpc_port,
        "stream_port": args.stream_port,
        "screenshot_scale": scale,
        "vessels_total_in_game": len(list(sc.vessels)),
        "vessels_selected": len(ordered),
        "items": [],
    }

    for idx, v in enumerate(ordered, start=1):
        label = _vessel_label(v)
        print(f"[{idx}/{len(ordered)}] Activating: {label}")
        try:
            sc.active_vessel = v
            _wait_for_active_vessel(sc, v)
        except Exception as e:
            print(f"  WARN: Failed to activate vessel: {e}")
            continue

        # Capture staging info (legacy + current)
        try:
            legacy = readers.staging_info_legacy(conn)
        except Exception as e:
            legacy = {"error": f"{type(e).__name__}: {e}"}
        try:
            current = readers.staging_info(conn)
        except Exception as e:
            current = {"error": f"{type(e).__name__}: {e}"}

        # Screenshot
        safe = _safe_filename(label)
        screenshot_path = (screenshot_dir / f"{idx:02d}_{safe}.png").resolve()
        try:
            sc.screenshot(str(screenshot_path), scale)
        except Exception as e:
            print(f"  WARN: Screenshot failed: {e}")
            screenshot_path = None

        item = {
            "index": idx,
            "label": label,
            "name": getattr(v, "name", None),
            "type": _enum_name(getattr(v, "type", None)),
            "situation": _enum_name(getattr(v, "situation", None)),
            "body": None,
            "screenshot_path": str(screenshot_path) if screenshot_path else None,
            "legacy": legacy,
            "current": current,
        }
        try:
            item["body"] = v.orbit.body.name
        except Exception:
            item["body"] = None

        results["items"].append(item)
        print(f"  OK: {label} -> {item['screenshot_path']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote: {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
