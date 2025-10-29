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

from .krpc.client import KRPCConnectionError  # re-exported in docs
from .executors.parsers import split_stdout_and_meta, parse_summary, extract_error_from_stderr


@mcp.tool()
def execute_script(
    code: str,
    address: str,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    *,
    timeout_sec: float = 120.0,
    pause_on_end: bool = True,
    unpause_on_start: bool = True,
    allow_imports: bool = False,
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
      timeout_sec: Max wall time for the script (seconds)
      unpause_on_start: Best-effort unpause on start to ensure simulation runs
      pause_on_end: Attempt to pause KSP when finished (best-effort; may be None)
      allow_imports: Permit `import` statements inside the script (default false)

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
            "timeout_sec": float(timeout_sec),
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
            out, err = proc.communicate(timeout=float(timeout_sec))
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            return json.dumps({
                "ok": False,
                "summary": None,
                "transcript": "",  # interrupted
                "stdout": "",
                "stderr": "TimeoutExpired: script exceeded timeout budget",
                "error": {"type": "TimeoutError", "message": "Script timed out"},
                "paused": None,
                "timing": {"exec_time_s": float(timeout_sec)},
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
            "code_stats": {
                "line_count": code.count("\n") + 1,
                "has_imports": bool(re.search(r"^\s*(from|import)\b", code, re.M)),
            },
        }

        return json.dumps(result)
