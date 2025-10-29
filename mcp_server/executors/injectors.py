from __future__ import annotations

import builtins
import logging
import sys as _sys
import time as _time
import math as _math
from typing import Any, Dict, Tuple


def build_globals(conn, *, timeout_sec: float | None, allow_imports: bool) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build the global namespace for exec() with helpful utilities and safety controls.

    - Provides `conn`, `vessel`, `time`, `math`, `sleep`, `deadline`, `check_time`, `log`.
    - Optionally disables imports by overriding builtins.__import__.

    Returns (globals_dict, cleanup_state) so the runner can restore import hooks.
    """
    # Timeout helpers (soft deadline): if timeout_sec is None/<=0, disable deadline
    start = _time.monotonic()
    if timeout_sec is None or float(timeout_sec) <= 0:
        deadline = float("inf")
    else:
        deadline = start + max(0.1, float(timeout_sec))

    def check_time():
        if _time.monotonic() > deadline:
            raise TimeoutError("Script exceeded timeout budget")

    def sleep(seconds: float):
        # Bound sleeps and remain responsive to timeout
        t_end = _time.monotonic() + max(0.0, float(seconds))
        while _time.monotonic() < t_end:
            check_time()
            _time.sleep(min(0.25, t_end - _time.monotonic()))

    # Logging: configure root logger to stream to stdout with a simple prefix
    # Route logging to stdout so it's included in transcript
    logging.basicConfig(level=logging.INFO, format="LOG %(message)s", stream=_sys.stdout)

    def log(msg: Any):
        logging.info(str(msg))

    g: Dict[str, Any] = {
        "__name__": "__main__",
        "conn": conn,
        # active_vessel may not exist depending on scene; keep it optional
        "vessel": None,
        "time": _time,
        "math": _math,
        "sleep": sleep,
        "deadline": deadline,
        "check_time": check_time,
        "log": log,
        "logging": logging,
        # Builtins are available but may have import disabled below
        "__builtins__": builtins,
    }

    # Try to fetch an active vessel but tolerate missing context (e.g., KSC scene)
    try:
        g["vessel"] = getattr(conn.space_center, "active_vessel", None)
    except Exception:
        g["vessel"] = None

    cleanup: Dict[str, Any] = {}

    # Optionally disable imports to keep scripts deterministic and safe by default
    if not allow_imports:
        cleanup["__import__"] = builtins.__import__

        allowed_roots = {"logging"}  # allow common logging without import errors

        def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):  # pragma: no cover
            root = (name or "").split(".")[0]
            if root in allowed_roots:
                return cleanup["__import__"](name, globals, locals, fromlist, level)
            raise ImportError(
                "Imports are disabled for this execution. Set allow_imports=true to enable."
            )

        builtins.__import__ = _restricted_import  # type: ignore

    # Convenience helpers for common mission steps (staging, thrust checks, liftoff)
    def _sum_thrust(v) -> float:
        try:
            engines = getattr(getattr(v, "parts", None), "engines", []) or []
            return float(sum((getattr(e, "thrust", 0.0) or 0.0) for e in engines))
        except Exception:
            return 0.0

    def _has_launch_clamps(v) -> bool | None:
        try:
            clamps = getattr(getattr(v, "parts", None), "launch_clamps", None)
            if clamps is None:
                return None
            return len(list(clamps)) > 0
        except Exception:
            return None

    def _release_clamps_and_stage(ctrl, *, max_stages: int = 10) -> bool | None:
        """Stage until no launch clamps remain (best-effort). Returns True if clamps cleared."""
        cleared: bool | None = None
        for _ in range(max_stages):
            try:
                hc = _has_launch_clamps(g.get("vessel"))
                if hc is False:
                    cleared = True
                    break
                ctrl.activate_next_stage()
            except Exception:
                pass
            # give KSP a moment to update staging
            try:
                sleep(0.2)
            except Exception:
                pass
        if cleared is None:
            # Could not determine presence of clamps
            return None
        return cleared

    def _stage_until_thrust(ctrl, *, max_stages: int = 10, thrust_threshold_n: float = 1.0) -> bool:
        """Stage up to N times until total thrust exceeds threshold. Returns True if thrust detected."""
        for _ in range(max_stages):
            try:
                ctrl.activate_next_stage()
            except Exception:
                pass
            t0 = _time.monotonic()
            while _time.monotonic() - t0 < 1.0:
                try:
                    check_time()
                except Exception:
                    # If no soft deadline, continue
                    pass
                if _sum_thrust(g.get("vessel")) > float(thrust_threshold_n):
                    return True
                try:
                    sleep(0.1)
                except Exception:
                    pass
        return False

    def _wait_for_liftoff(v, *, vs_threshold: float = 0.5, timeout_s: float = 20.0) -> bool:
        """Wait until vertical speed exceeds threshold or situation changes from pre_launch."""
        t0 = _time.monotonic()
        while _time.monotonic() - t0 < float(timeout_s):
            try:
                check_time()
            except Exception:
                pass
            try:
                fl = v.flight()
                vs = float(getattr(fl, "vertical_speed", 0.0) or 0.0)
                if vs > float(vs_threshold):
                    return True
            except Exception:
                pass
            try:
                sleep(0.25)
            except Exception:
                pass
        return False

    def _situation_name(v) -> str | None:
        try:
            sit = getattr(v, "situation", None)
            return str(sit) if sit is not None else None
        except Exception:
            return None

    g["helpers"] = {
        "sum_thrust": _sum_thrust,
        "has_launch_clamps": _has_launch_clamps,
        "release_clamps": _release_clamps_and_stage,
        "stage_until_thrust": _stage_until_thrust,
        "wait_for_liftoff": _wait_for_liftoff,
        "situation": _situation_name,
    }

    return g, cleanup


def restore_after_exec(cleanup_state: Dict[str, Any]) -> None:
    """Restore any globals mutated for the exec sandbox (e.g., builtins.__import__)."""
    imp = cleanup_state.get("__import__")
    if imp is not None:
        builtins.__import__ = imp  # type: ignore
