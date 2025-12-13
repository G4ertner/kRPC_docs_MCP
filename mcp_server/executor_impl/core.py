from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import subprocess
import threading
import logging
from pathlib import Path
from typing import Any, Dict

from ..utils.krpc_utils.client import KRPCConnectionError, connect_to_game  # re-exported in docs
from ..utils.krpc_utils import readers
from ..utils.krpc_helpers import best_effort_pause
from ..executors.parsers import split_stdout_and_meta, parse_summary, extract_error_from_stderr
from ..utils.helper_utils import utc_timestamp
from .job_artifacts import save_job_artifact, job_resource_uri
from .jobs import job_registry


def execute_script_impl(
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
        transcript: str,          // combined stdout + stderr so crashes are visible
        stdout: str,              // raw stdout only
        stderr: str,              // raw stderr only (tracebacks, etc.)
        error: {type,message,line?,traceback?}|null,
        paused: bool|null,
        unpaused: bool|null,
        timing: {exec_time_s},
        pre_pause_flight: {...}|null,  // snapshot just before pausing (has non-zero speeds)
        follow_up?: {                 // when ok=false, guidance for next step
          suggest_get_diagnostics: true,
          message: string,            // human-readable hint
          tool: "get_diagnostics",
          params: { address, rpc_port, stream_port, name }
        },
        code_stats: {line_count, has_imports}
      }

    Operational behavior:
      - On start: best-effort unpause (unpause_on_start=true by default) so physics runs.
      - On end (success, failure, or exception): best-effort pause; includes `pre_pause_flight`
        with velocities sampled immediately before pausing so speeds are informative.
      - Soft timeout: your script should call `check_time()` inside loops; on TimeoutError
        the runner pauses and returns `ok=false` with `pre_pause_flight`.
      - Hard timeout: if `hard_timeout_sec` elapses, the parent kills the runner, pauses the
        game, and returns a minimal `diagnostics` block plus a `follow_up` hint to call
        `get_diagnostics` for a rich snapshot while the game is paused.

    Recommended pattern after any failure/timeout:
      - If `ok=false` OR you need deeper insight, immediately call `get_diagnostics` with the
        provided params in `follow_up` to retrieve a comprehensive paused-state snapshot.

    Notes:
      - `vessel` may be None depending on the scene (e.g., KSC/Tracking Station). Guard accordingly.
      - `pause_on_end` is best-effort and may be None on some kRPC versions.
      - The `transcript` includes stderr so exceptions are visible alongside prints/logs.
    """
    result = _run_execute_script(
        code=code,
        address=address,
        rpc_port=rpc_port,
        stream_port=stream_port,
        name=name,
        timeout_sec=timeout_sec,
        pause_on_end=pause_on_end,
        unpause_on_start=unpause_on_start,
        allow_imports=allow_imports,
        hard_timeout_sec=hard_timeout_sec,
    )
    return json.dumps(result)

def start_execute_script_job_impl(
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
) -> dict:
    """
    Start a background job that runs execute_script with live log streaming.
    Usage pattern:
        1. Call start_execute_script_job(...) to enqueue the script; capture the returned job_id.
        2. Poll get_job_status(job_id) for log/print output as the script runs (alternate checks with vessel status tools
           like get_status_overview / get_flight_snapshot to keep tabs on the rocket).
        3. If something goes wrong, immediately call cancel_job(job_id), revert/restore as needed (revert_to_launch,
           load checkpoint), then plan the next step.
        4. When the job finishes, call read_resource(result_resource) to download the same JSON payload execute_script returns.
    """
    params = {
        "code": code,
        "address": address,
        "rpc_port": rpc_port,
        "stream_port": stream_port,
        "name": name,
        "timeout_sec": timeout_sec,
        "pause_on_end": pause_on_end,
        "unpause_on_start": unpause_on_start,
        "allow_imports": allow_imports,
        "hard_timeout_sec": hard_timeout_sec,
    }

    def job_fn(handle):
        handle.log("[execute_script] launching job")
        result = _run_execute_script(job_handle=handle, **params)
        artifact_payload = {
            "job_id": handle.job_id,
            "kind": "execute_script",
            "requested_at": utc_timestamp(),
            "params": params,
            "result": result,
        }
        artifact = save_job_artifact(handle.job_id, artifact_payload)
        handle.set_result_resource(job_resource_uri(handle.job_id))
        handle.log(f"[execute_script] artifact ready at {artifact}")

    job_id = job_registry.create_job(job_fn, metadata={"kind": "execute_script"})
    return {
        "job_id": job_id,
        "status": "PENDING",
        "note": (
            "Script job started. Poll get_job_status(job_id) for live logs, "
            # "alternate with get_status_overview/get_flight_snapshot to monitor the vessel, "
            "and call cancel_job(job_id) + revert/load if the burn goes sideways."
        ),
    }


def _resolve_timeouts(
    timeout_sec: float | None,
    hard_timeout_sec: float | None,
    *,
    job_handle: Any | None = None,
) -> tuple[float | None, float | None]:
    """Normalize timeouts so soft is at least as long as hard when both are provided."""

    def _coerce(value: float | None) -> float | None:
        if value is None:
            return None
        f = float(value)
        if f <= 0:
            return None
        return f

    soft = _coerce(timeout_sec)
    hard = _coerce(hard_timeout_sec)

    def _warn(msg: str) -> None:
        if job_handle is not None:
            try:
                job_handle.log(f"[execute_script] {msg}")
            except Exception:
                pass
        else:
            logging.warning(msg)

    # If caller supplies only a hard timeout, extend the soft timeout to match it.
    if soft is None and hard is not None:
        soft = hard
        _warn(f"Soft timeout not set; extending soft deadline to {hard:.1f}s to match hard watchdog.")

    # If soft is shorter than hard, extend soft to give the script a chance to wrap up gracefully.
    if soft is not None and hard is not None and soft < hard:
        soft = hard
        _warn(f"Soft timeout shorter than hard watchdog; extending soft deadline to {soft:.1f}s.")

    # When soft is meaningfully longer than hard for long-running tasks, trail the hard watchdog behind soft by a margin.
    if soft is not None and hard is not None and soft > hard and soft >= 60:
        margin = 10.0
        target = soft + margin
        if hard < target:
            hard = target
            _warn(
                "Hard watchdog was shorter than soft timeout; bumping hard timeout "
                f"to {hard:.1f}s so it trails the soft deadline."
            )

    return soft, hard


def _run_execute_script(
    *,
    code: str,
    address: str,
    rpc_port: int,
    stream_port: int,
    name: str | None,
    timeout_sec: float | None,
    pause_on_end: bool,
    unpause_on_start: bool,
    allow_imports: bool,
    hard_timeout_sec: float | None,
    job_handle: Any | None = None,
) -> Dict[str, Any]:
    """Helper that executes the script and returns a structured result dict (no JSON)."""
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
        cfg["timeout_sec"], hard_timeout_sec = _resolve_timeouts(
            cfg["timeout_sec"],
            hard_timeout_sec,
            job_handle=job_handle,
        )

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
                bufsize=1,
            )
        except Exception as e:
            return {
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
            }

        cancel_flag = {"cancelled": False}
        if job_handle is not None:
            def _cancel_proc():
                cancel_flag["cancelled"] = True
                try:
                    job_handle.log("[execute_script] cancellation requested")
                except Exception:
                    pass
                try:
                    proc.kill()
                except Exception:
                    pass
            job_handle.register_cancel_callback(_cancel_proc)

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        def _reader(pipe, sink, kind: str) -> None:
            if pipe is None:
                return
            for line in iter(pipe.readline, ""):
                sink.append(line)
                if job_handle is not None:
                    try:
                        job_handle.log(f"[execute_script:{kind}] {line.rstrip()}")
                    except Exception:
                        pass

        threads = []
        if proc.stdout is not None:
            t = threading.Thread(target=_reader, args=(proc.stdout, stdout_lines, "stdout"), daemon=True)
            t.start()
            threads.append(t)
        if proc.stderr is not None:
            t = threading.Thread(target=_reader, args=(proc.stderr, stderr_lines, "stderr"), daemon=True)
            t.start()
            threads.append(t)

        try:
            if hard_timeout_sec is not None and float(hard_timeout_sec) > 0:
                proc.wait(timeout=float(hard_timeout_sec))
            else:
                proc.wait()
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            diagnostics: Dict[str, Any] | None = None
            conn = None
            try:
                conn = connect_to_game(
                    address,
                    rpc_port=int(rpc_port),
                    stream_port=int(stream_port),
                    name=name,
                    timeout=3.0,
                )
                pre_flight = None
                try:
                    pre_flight = readers.flight_snapshot(conn)
                except Exception:
                    pre_flight = None
                try:
                    best_effort_pause(conn)
                except Exception:
                    pass
                diagnostics = {
                    "vessel": readers.vessel_info(conn),
                    "time": readers.time_status(conn),
                    "pre_pause_flight": pre_flight,
                }
            except Exception as e:
                diagnostics = {"note": f"diagnostics unavailable: {type(e).__name__}"}
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

            for t in threads:
                t.join(timeout=0.2)
            return {
                "ok": False,
                "summary": None,
                "transcript": "",
                "stdout": "",
                "stderr": "TimeoutExpired: hard timeout reached; process killed",
                "error": {"type": "TimeoutError", "message": "Hard timeout reached"},
                "paused": None,
                "timing": {"exec_time_s": (float(hard_timeout_sec) if hard_timeout_sec else None)},
                "diagnostics": diagnostics,
                "follow_up": {
                    "suggest_get_diagnostics": True,
                    "message": "Hint: call get_diagnostics to capture a rich paused-state snapshot and investigate why the script failed or timed out.",
                    "tool": "get_diagnostics",
                    "params": {
                        "address": address,
                        "rpc_port": int(rpc_port),
                        "stream_port": int(stream_port),
                        "name": name,
                    },
                },
                "code_stats": {
                    "line_count": code.count("\n") + 1,
                    "has_imports": bool(re.search(r"^\s*(from|import)\b", code, re.M)),
                },
            }

        for t in threads:
            t.join(timeout=0.2)

        out = "".join(stdout_lines)
        err = "".join(stderr_lines)
        transcript_out, meta = split_stdout_and_meta(out or "")
        summary = parse_summary(transcript_out)
        transcript = transcript_out + (("\n" + err) if err else "")

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
        if not result["ok"]:
            result["follow_up"] = {
                "suggest_get_diagnostics": True,
                "message": "Hint: call get_diagnostics to capture a rich paused-state snapshot and investigate why the script failed or timed out.",
                "tool": "get_diagnostics",
                "params": {
                    "address": address,
                    "rpc_port": int(rpc_port),
                    "stream_port": int(stream_port),
                    "name": name,
                },
            }
        if cancel_flag["cancelled"]:
            result.setdefault("error", {"type": "Cancelled", "message": "Job cancelled by user"})
            result["ok"] = False
        return result
