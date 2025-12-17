import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.utils.krpc_utils.client import connect_to_game, KRPCConnectionError  # noqa: E402
from mcp_server.utils.krpc_utils import readers  # noqa: E402


def _safe_name(name: str) -> str:
    name = (name or "").strip() or "vessel"
    name = re.sub(r"[^\w\-. ]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip().replace(" ", "_")
    return name[:80]


def _summarize_stage_dv(plan: dict) -> dict:
    rows = []
    total = 0.0
    for s in plan.get("stages", []) or []:
        dv = s.get("delta_v_m_s")
        if dv is not None:
            try:
                total += float(dv)
            except Exception:
                pass
        rows.append(
            {
                "stage": s.get("stage"),
                "engines": s.get("engines"),
                "delta_v_m_s": dv,
                "delta_v_round_m_s": (int(round(float(dv))) if dv is not None else None),
            }
        )
    return {
        "rows": rows,
        "total_delta_v_m_s": total,
        "total_delta_v_round_m_s": int(round(total)) if total else 0,
        "total_delta_v_sum_of_stage_round_m_s": sum(r["delta_v_round_m_s"] or 0 for r in rows),
    }


def _wait_for_active_vessel(conn, expected_name: str, timeout_s: float = 30.0) -> bool:
    t0 = time.time()
    sc = conn.space_center
    while time.time() - t0 < timeout_s:
        try:
            av = sc.active_vessel
            if av and av.name == expected_name:
                _ = av.situation
                _ = av.orbit.body.name
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def _capture_ksp_window(out_png: Path) -> None:
    ps = ROOT / "tests" / "manual" / "ksp_window_capture.ps1"
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps),
        "-OutPath",
        str(out_png),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Bulk compare stage plan legacy vs new and capture UI screenshots.")
    ap.add_argument("--address", required=True)
    ap.add_argument("--rpc-port", type=int, default=50000)
    ap.add_argument("--stream-port", type=int, default=50001)
    ap.add_argument("--name", default="StagePlan Bulk Capture")
    ap.add_argument("--env", default="current", choices=["current", "sea_level", "vacuum"])
    ap.add_argument("--out-dir", default=str(ROOT / "artifacts" / "stage_plan_validation"))
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    ap.add_argument("--include-debris", action="store_true", help="Include VesselType.debris vessels")
    ap.add_argument(
        "--types",
        default="",
        help="Comma-separated VesselType names to include (e.g. ship,lander,probe). Overrides --include-debris.",
    )
    ap.add_argument("--unique-names", action="store_true", help="Process at most one vessel per name")
    args = ap.parse_args()

    try:
        conn = connect_to_game(args.address, rpc_port=args.rpc_port, stream_port=args.stream_port, name=args.name)
    except KRPCConnectionError as e:
        print(f"Connect failed: {e}")
        return 1

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    sc = conn.space_center
    active = sc.active_vessel
    vessels = list(getattr(sc, "vessels", []) or [])
    allowed_types = None
    if args.types.strip():
        allowed_types = {f"VesselType.{t.strip().lower()}" for t in args.types.split(",") if t.strip()}
    ordered = []
    if active is not None:
        ordered.append(active)
    ordered.extend([v for v in vessels if active is None or v != active])

    def _keep(vessel_obj) -> bool:
        try:
            t = str(getattr(vessel_obj, "type", None))
        except Exception:
            return True
        if allowed_types is not None:
            return t in allowed_types
        if args.include_debris:
            return True
        return t != "VesselType.debris"

    ordered = [v for v in ordered if _keep(v)]
    if args.unique_names:
        seen = set()
        uniq = []
        for v in ordered:
            try:
                n = v.name
            except Exception:
                n = None
            if not n or n in seen:
                continue
            seen.add(n)
            uniq.append(v)
        ordered = uniq

    if args.limit and args.limit > 0:
        ordered = ordered[: args.limit]

    print(f"Found {len(ordered)} vessel(s) to process.")

    for idx, v in enumerate(ordered, start=1):
        try:
            name = v.name
        except Exception:
            name = f"vessel_{idx}"

        print(f"\n[{idx}/{len(ordered)}] Activating: {name}")
        try:
            sc.active_vessel = v
        except Exception as e:
            print(f"  Failed to set active vessel: {e}")
            continue

        if not _wait_for_active_vessel(conn, name, timeout_s=45.0):
            print("  Timed out waiting for vessel to load; skipping.")
            continue

        av = sc.active_vessel
        meta = {
            "name": getattr(av, "name", None),
            "type": str(getattr(av, "type", None)),
            "situation": str(getattr(av, "situation", None)),
            "body": getattr(getattr(getattr(av, "orbit", None), "body", None), "name", None),
            "current_stage": getattr(getattr(av, "control", None), "current_stage", None),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "environment": args.env,
        }

        safe = _safe_name(meta["name"] or f"vessel_{idx}")
        case_dir = out_root / f"{idx:02d}_{safe}"
        case_dir.mkdir(parents=True, exist_ok=True)

        # Tool outputs (legacy vs new)
        legacy = readers.stage_plan_approx_legacy(conn, environment=args.env)
        current = readers.stage_plan_approx(conn, environment=args.env)
        (case_dir / "stage_plan_legacy.json").write_text(json.dumps(legacy, indent=2, ensure_ascii=False), encoding="utf-8")
        (case_dir / "stage_plan_current.json").write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        (case_dir / "stage_plan_legacy_summary.json").write_text(json.dumps(_summarize_stage_dv(legacy), indent=2, ensure_ascii=False), encoding="utf-8")
        (case_dir / "stage_plan_current_summary.json").write_text(json.dumps(_summarize_stage_dv(current), indent=2, ensure_ascii=False), encoding="utf-8")
        (case_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        # UI screenshot
        out_png = case_dir / "ksp_window.png"
        try:
            _capture_ksp_window(out_png)
            print(f"  Screenshot: {out_png}")
        except Exception as e:
            print(f"  Screenshot capture failed: {e}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
