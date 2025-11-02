from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Any, Dict

from .server import mcp

from .krpc.client import KRPCConnectionError, connect_to_game  # re-exported in docs
from .krpc import readers
from .executors.parsers import split_stdout_and_meta, parse_summary, extract_error_from_stderr


@mcp.tool()
def execute_script(
    code: str,
    address: str,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    *,
    timeout_sec: float | None = None,
    pause_on_end: bool = True,
    unpause_on_start: bool = True,
    allow_imports: bool = False,
    hard_timeout_sec: float | None = None,
) -> str:
    """
    Execute a Python script against the running kRPC game with automatic connection and helpers.

    When to use:
      - Run short, deterministic mission steps with logging and a final SUMMARY block.

    Script Contract:
      - Do NOT import kRPC or connect manually (unless you set allow_imports=True).
      - Injected globals: `conn`, `vessel` (may be None), `time`, `math`, `sleep(s)`, `deadline`, `check_time()`, `logging`, and `log(msg)`.
      - Use standard `print()` and/or Python `logging` (both are captured). Imports are disabled by default, but `logging` is pre-injected and allowed.
      - Always include a `SUMMARY:` block at the end (a single line or a block starting with `SUMMARY:`) so the agent can quickly understand outcomes.
      - Use bounded loops and call `check_time()` periodically; the runner enforces a hard wall-time timeout.

    Args:
      code: Python source string to execute
      address/rpc_port/stream_port/name: kRPC connection settings
      timeout_sec: Soft deadline (seconds) injected into the script via check_time().
                  Use None/<=0 to disable the soft deadline.
      unpause_on_start: Best-effort unpause on start to ensure simulation runs
      pause_on_end: Attempt to pause KSP when finished (best-effort; may be None)
      allow_imports: Permit `import` statements inside the script (default false)
      hard_timeout_sec: Parent watchdog (seconds). If set, the MCP process will kill the
                        script runner after this time. None disables the hard timeout.

    Returns:
      JSON: {
        ok: bool,
        summary: str|null,
        transcript: str,          // combined stdout + stderr so the agent sees crashes
        stdout: str,              // raw stdout only
        stderr: str,              // raw stderr only (tracebacks, etc.)
        error: {type,message,line?,traceback?}|null,
        paused: bool|null,
        timing: {exec_time_s},
        code_stats: {line_count, has_imports}
      }
    Notes:
      - `vessel` can be None depending on the scene (e.g., KSC/Tracking Station). Guard in scripts.
      - `pause_on_end` is best-effort and may return None when unsupported by your kRPC version.
      - The `transcript` includes stderr so exceptions are visible to the agent alongside prints/logs.
    """
    # Prepare temporary workspace
    with tempfile.TemporaryDirectory(prefix="krpc_exec_") as tmp:
        code_file = Path(tmp) / "user_code.py"
        code_file.write_text(code, encoding="utf-8")

        cfg = {
            "code_path": str(code_file),
            "address": address,
            "rpc_port": int(rpc_port),
            "stream_port": int(stream_port),
            "name": name,
            "timeout_sec": (None if (timeout_sec is None or float(timeout_sec) <= 0) else float(timeout_sec)),
            "allow_imports": bool(allow_imports),
            "pause_on_end": bool(pause_on_end),
            "unpause_on_start": bool(unpause_on_start),
        }

        # Spawn runner in a separate Python subprocess to isolate execution
        try:
            py = sys.executable or "python"
        except Exception:
            py = "python"

        cmd = [py, "-m", "mcp_server.executors.runner", json.dumps(cfg)]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tmp,
                text=True,
            )
        except Exception as e:
            return json.dumps({
                "ok": False,
                "summary": None,
                "transcript": "",
                "stdout": "",
                "stderr": str(e),
                "error": {"type": type(e).__name__, "message": str(e)},
                "paused": None,
                "timing": {"exec_time_s": None},
                "code_stats": {
                    "line_count": code.count("\n") + 1,
                    "has_imports": bool(re.search(r"^\s*(from|import)\b", code, re.M)),
                },
            })

        try:
            if hard_timeout_sec is not None and float(hard_timeout_sec) > 0:
                out, err = proc.communicate(timeout=float(hard_timeout_sec))
            else:
                # No hard timeout: wait until the runner exits
                out, err = proc.communicate()
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            # Attempt to collect best-effort diagnostics from the live game to help the LLM debug timeouts.
            diagnostics: Dict[str, Any] | None = None
            try:
                conn = connect_to_game(
                    address,
                    rpc_port=int(rpc_port),
                    stream_port=int(stream_port),
                    name=name,
                    timeout=5.0,
                )
                diagnostics = {
                    "vessel": readers.vessel_info(conn),
                    "environment": readers.environment_info(conn),
                    "flight": readers.flight_snapshot(conn),
                    "orbit": readers.orbit_info(conn),
                    "time": readers.time_status(conn),
                    "attitude": readers.attitude_status(conn),
                    "aero": readers.aero_status(conn),
                }
                try:
                    diagnostics["engines"] = readers.engine_status(conn)
                except Exception:
                    pass
                try:
                    diagnostics["resources"] = readers.resource_breakdown(conn)
                except Exception:
                    pass
                try:
                    diagnostics["maneuver_nodes"] = readers.maneuver_nodes_basic(conn)
                except Exception:
                    pass
                # After collecting diagnostics, best-effort pause so the game stops progressing.
                try:
                    _best_effort_pause(conn)
                except Exception:
                    pass
            except Exception as e:
                diagnostics = {"note": f"diagnostics unavailable: {type(e).__name__}"}

            return json.dumps({
                "ok": False,
                "summary": None,
                "transcript": "",  # interrupted
                "stdout": "",
                "stderr": "TimeoutExpired: hard timeout reached; process killed",
                "error": {"type": "TimeoutError", "message": "Hard timeout reached"},
                "paused": None,
                "timing": {"exec_time_s": (float(hard_timeout_sec) if hard_timeout_sec else None)},
                "diagnostics": diagnostics,
                "code_stats": {
                    "line_count": code.count("\n") + 1,
                    "has_imports": bool(re.search(r"^\s*(from|import)\b", code, re.M)),
                },
            })


        # Strip internal meta from stdout
        transcript_out, meta = split_stdout_and_meta(out or "")
        summary = parse_summary(transcript_out)
        # Combine stderr into transcript so the agent sees exceptions/crashes inline
        transcript = transcript_out + (("\n" + err) if err else "")

        # Error parsing
        error_obj = None
        if proc.returncode and err:
            error_obj = extract_error_from_stderr(err)

        result: Dict[str, Any] = {
            "ok": bool(meta.get("ok") if isinstance(meta, dict) else (proc.returncode == 0)),
            "summary": summary,
            "transcript": transcript,
            "stdout": transcript_out,
            "stderr": err or "",
            "error": error_obj,
            "paused": (meta.get("paused") if isinstance(meta, dict) else None),
            "unpaused": (meta.get("unpaused") if isinstance(meta, dict) else None),
            "timing": {"exec_time_s": (meta.get("exec_time_s") if isinstance(meta, dict) else None)},
            "pre_pause_flight": (meta.get("pre_pause_flight") if isinstance(meta, dict) else None),
            "code_stats": {
                "line_count": code.count("\n") + 1,
                "has_imports": bool(re.search(r"^\s*(from|import)\b", code, re.M)),
            },
        }

        return json.dumps(result)


def _best_effort_pause(conn):
    """Internal pause helper, mirrors runner/tool logic."""
    try:
        cur = bool(conn.krpc.paused)
        if not cur:
            conn.krpc.paused = True
        return True
    except Exception:
        pass
    try:
        sc = conn.space_center
    except Exception:
        return None
    for attr in ("set_pause", "set_paused", "pause"):
        try:
            fn = getattr(sc, attr, None)
            if callable(fn):
                fn(True)
                return True
        except Exception:
            continue
    for attr in ("paused", "is_paused"):
        try:
            if hasattr(sc, attr):
                setattr(sc, attr, True)
                return True
        except Exception:
            continue
    return None
