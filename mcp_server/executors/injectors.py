from __future__ import annotations

import builtins
import logging
import sys as _sys
import time as _time
import math as _math
from typing import Any, Dict, Tuple


def build_globals(conn, *, timeout_sec: float, allow_imports: bool) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build the global namespace for exec() with helpful utilities and safety controls.

    - Provides `conn`, `vessel`, `time`, `math`, `sleep`, `deadline`, `check_time`, `log`.
    - Optionally disables imports by overriding builtins.__import__.

    Returns (globals_dict, cleanup_state) so the runner can restore import hooks.
    """
    # Timeout helpers
    start = _time.monotonic()
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

    return g, cleanup


def restore_after_exec(cleanup_state: Dict[str, Any]) -> None:
    """Restore any globals mutated for the exec sandbox (e.g., builtins.__import__)."""
    imp = cleanup_state.get("__import__")
    if imp is not None:
        builtins.__import__ = imp  # type: ignore
