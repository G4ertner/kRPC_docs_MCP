import argparse
import asyncio
import json
import re
import subprocess
import time
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


ROOT = Path(__file__).resolve().parents[2]


def _safe_name(name: str) -> str:
    name = (name or "").strip() or "vessel"
    name = re.sub(r"[^\w\-. ]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip().replace(" ", "_")
    return name[:80]


def _tool_text(result) -> str:
    texts: list[str] = []
    for c in getattr(result, "content", []) or []:
        if getattr(c, "type", None) == "text":
            texts.append(c.text)
    return "\n".join(texts).strip()


def _parse_tool_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}
    return json.loads(text)


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


async def _wait_for_vessel(session: ClientSession, expected_name: str, timeout_s: float = 45.0) -> dict | None:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        try:
            res = await session.call_tool("get_vessel_info", {})
            text = _tool_text(res)
            last = _parse_tool_json(text)
            if last.get("name") == expected_name:
                return last
        except Exception:
            pass
        await asyncio.sleep(0.25)
    return last


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


async def main() -> int:
    ap = argparse.ArgumentParser(
        description="Launch each craft via geept_mcp tools and capture staging plan (new vs legacy) + UI screenshot."
    )
    ap.add_argument("--mcp-url", default="http://127.0.0.1:5500/mcp")
    ap.add_argument("--craft-directory", default="VAB", choices=["VAB", "SPH"])
    ap.add_argument("--launch-site", default="LaunchPad")
    ap.add_argument("--recover", action="store_true", default=True)
    ap.add_argument("--env", default="current", choices=["current", "sea_level", "vacuum"])
    ap.add_argument("--out-dir", default=str(ROOT / "artifacts" / "stage_plan_launchable_validation"))
    ap.add_argument("--timeout-s", type=float, default=60.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    async with streamablehttp_client(args.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            res = await session.call_tool("list_launchable_vessels", {"craft_directory": args.craft_directory})
            launchables = _parse_tool_json(_tool_text(res)).get("vessels", []) or []
            if args.limit and args.limit > 0:
                launchables = launchables[: args.limit]

            print(f"Found {len(launchables)} craft(s) in {args.craft_directory}.")
            for idx, craft in enumerate(launchables, start=1):
                print(f"\n[{idx}/{len(launchables)}] Launching: {craft}")
                res = await session.call_tool(
                    "launch_vessel",
                    {
                        "craft_directory": args.craft_directory,
                        "name": craft,
                        "launch_site": args.launch_site,
                        "recover": True,
                    },
                )
                launch_resp = _parse_tool_json(_tool_text(res))
                if not launch_resp.get("ok"):
                    print(f"  Launch failed: {launch_resp.get('error')}")
                    continue

                expected_name = launch_resp.get("active_vessel") or craft
                vessel_info = await _wait_for_vessel(session, expected_name, timeout_s=float(args.timeout_s))
                if vessel_info is None or vessel_info.get("name") != expected_name:
                    print(f"  Timed out waiting for vessel '{expected_name}' to load.")

                meta = {
                    "craft_directory": args.craft_directory,
                    "craft_name": craft,
                    "launch_site": args.launch_site,
                    "expected_vessel_name": expected_name,
                    "vessel_info": vessel_info,
                    "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "environment": args.env,
                }

                case_dir = out_root / f"{idx:02d}_{_safe_name(craft)}"
                case_dir.mkdir(parents=True, exist_ok=True)
                (case_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

                # Stage plans (new + legacy)
                res_new = await session.call_tool("get_staging_plan", {"environment": args.env})
                res_old = await session.call_tool("get_staging_plan_legacy", {"environment": args.env})
                plan_new = _parse_tool_json(_tool_text(res_new))
                plan_old = _parse_tool_json(_tool_text(res_old))
                (case_dir / "stage_plan_new.json").write_text(
                    json.dumps(plan_new, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                (case_dir / "stage_plan_legacy.json").write_text(
                    json.dumps(plan_old, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                (case_dir / "stage_plan_new_summary.json").write_text(
                    json.dumps(_summarize_stage_dv(plan_new), indent=2, ensure_ascii=False), encoding="utf-8"
                )
                (case_dir / "stage_plan_legacy_summary.json").write_text(
                    json.dumps(_summarize_stage_dv(plan_old), indent=2, ensure_ascii=False), encoding="utf-8"
                )

                # UI screenshot (includes staging panel)
                out_png = case_dir / "ksp_window.png"
                try:
                    _capture_ksp_window(out_png)
                    print(f"  Screenshot: {out_png}")
                except Exception as e:
                    print(f"  Screenshot capture failed: {e}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

