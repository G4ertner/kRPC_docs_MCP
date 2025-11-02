from __future__ import annotations

import json
import signal
import sys
import traceback
import time as _time
from pathlib import Path
from typing import Any, Dict, Optional

from ..krpc.client import connect_to_game
from ..krpc import readers
from .injectors import build_globals, restore_after_exec
from .parsers import EXEC_META_PREFIX


def _get_paused(conn) -> bool | None:
    try:
        return bool(conn.krpc.paused)
    except Exception:
        return None


def _try_pause(conn) -> bool | None:
    # Preferred API: KRPC.paused (read/write)
    try:
        current = bool(conn.krpc.paused)
        if not current:
            conn.krpc.paused = True
        return True
    except Exception:
        pass
    # Fallbacks: SpaceCenter variants across versions
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
    # Try attribute write
    for attr in ("paused", "is_paused"):
        try:
            if hasattr(sc, attr):
                setattr(sc, attr, True)
                return True
        except Exception:
            continue
    return None


def _try_unpause(conn) -> bool | None:
    """Best-effort attempt to unpause the game (equivalent to closing pause menu)."""
    # Preferred API: KRPC.paused (read/write) — only write when currently paused
    try:
        if bool(conn.krpc.paused):
            conn.krpc.paused = False
        return True
    except Exception:
        pass
    # Fallbacks: SpaceCenter variants across versions
    try:
        sc = conn.space_center
    except Exception:
        return None
    for attr in ("set_pause", "set_paused", "pause"):
        try:
            fn = getattr(sc, attr, None)
            if callable(fn):
                fn(False)
                return True
        except Exception:
            continue
    for attr in ("paused", "is_paused"):
        try:
            if hasattr(sc, attr):
                setattr(sc, attr, False)
                return True
        except Exception:
            continue
    return None


def _is_prelaunch(vessel) -> bool | None:
    try:
        sit = getattr(vessel, "situation", None)
        if sit is None:
            return None
        name = getattr(sit, "name", None)
        text = (name or str(sit) or "").lower()
        return ("pre_launch" in text) or ("prelaunch" in text)
    except Exception:
        return None


def _load_config() -> Dict[str, Any]:
    cfg_env = sys.argv[1] if len(sys.argv) > 1 else None
    if not cfg_env:
        raise SystemExit("Missing runner config JSON argument")
    try:
        cfg = json.loads(cfg_env)
    except Exception as e:  # pragma: no cover
        raise SystemExit(f"Invalid runner config JSON: {e}")
    return cfg


_CONN: Optional[object] = None


def _signal_handler(signum, frame):
    try:
        # Best-effort pause when interrupted (Ctrl-C, tool cancel, supervisor stop)
        pre_pause_flight = None
        if _CONN is not None:
            try:
                pre_pause_flight = readers.flight_snapshot(_CONN)
            except Exception:
                pre_pause_flight = None
            try:
                _try_pause(_CONN)
            except Exception:
                pass
        meta = {
            "ok": False,
            "paused": (_get_paused(_CONN) if _CONN is not None else None),
            "unpaused": None,
            "exec_time_s": None,
            "pre_pause_flight": pre_pause_flight,
        }
        # Ensure meta line is printed so parent can parse a graceful end
        print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
    finally:
        # 128 + signal number is conventional exit code for signals
        code = 128 + int(signum or 0)
        try:
            sys.stdout.flush(); sys.stderr.flush()
        except Exception:
            pass
        os._exit(code)


def main() -> None:
    cfg = _load_config()
    code_path = Path(cfg["code_path"]).resolve()
    address = cfg["address"]
    rpc_port = int(cfg.get("rpc_port", 50000))
    stream_port = int(cfg.get("stream_port", 50001))
    name = cfg.get("name")
    _raw_timeout = cfg.get("timeout_sec", None)
    timeout_sec = None if _raw_timeout in (None, "", 0, 0.0) else float(_raw_timeout)
    allow_imports = bool(cfg.get("allow_imports", False))
    pause_on_end = bool(cfg.get("pause_on_end", True))
    unpause_on_start = bool(cfg.get("unpause_on_start", True))

    exec_start = _time.monotonic()
    paused: bool | None = None
    unpaused: bool | None = None
    initial_prelaunch: bool | None = None

    conn = None
    try:
        conn = connect_to_game(
            address,
            rpc_port=rpc_port,
            stream_port=stream_port,
            name=name,
            timeout=(min(timeout_sec, 10.0) if isinstance(timeout_sec, (int, float)) and timeout_sec > 0 else 10.0),
        )
        # Expose to signal handler
        global _CONN
        _CONN = conn
        # Install signal handlers to pause on external interrupts
        for sig in (getattr(signal, 'SIGINT', None), getattr(signal, 'SIGTERM', None)):
            if sig is not None:
                try:
                    signal.signal(sig, _signal_handler)
                except Exception:
                    pass
    except Exception:
        # Print traceback to stderr for parent to parse
        traceback.print_exc()
        meta = {
            "ok": False,
            "paused": None,
            "unpaused": None,
            "exec_time_s": _time.monotonic() - exec_start,
        }
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
        return

    # Capture initial state
    try:
        v0 = getattr(conn.space_center, "active_vessel", None)
        initial_prelaunch = _is_prelaunch(v0)
    except Exception:
        initial_prelaunch = None

    # Best-effort: ensure the game is running before the user code executes
    if unpause_on_start:
        try:
            unpaused = _try_unpause(conn)
        except Exception:
            unpaused = None

    try:
        glb, cleanup = build_globals(conn, timeout_sec=timeout_sec, allow_imports=allow_imports)
    except Exception:
        # Best-effort: pause if requested and we have a live connection
        pre_pause_flight = None
        if pause_on_end:
            try:
                pre_pause_flight = readers.flight_snapshot(conn)
            except Exception:
                pre_pause_flight = None
            try:
                _try_pause(conn)
            except Exception:
                pass
        traceback.print_exc()
        meta = {
            "ok": False,
            "paused": _get_paused(conn),
            "unpaused": unpaused,
            "exec_time_s": _time.monotonic() - exec_start,
            "pre_pause_flight": pre_pause_flight,
        }
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
        return

    try:
        code = code_path.read_text(encoding="utf-8")
    except Exception:
        # Best-effort: pause if requested and we have a live connection
        pre_pause_flight = None
        if pause_on_end:
            try:
                pre_pause_flight = readers.flight_snapshot(conn)
            except Exception:
                pre_pause_flight = None
            try:
                _try_pause(conn)
            except Exception:
                pass
        traceback.print_exc()
        meta = {
            "ok": False,
            "paused": _get_paused(conn),
            "unpaused": unpaused,
            "exec_time_s": _time.monotonic() - exec_start,
            "pre_pause_flight": pre_pause_flight,
        }
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
        return

    try:
        exec(compile(code, "<user_code>", "exec"), glb, glb)
        ok = True
    except Exception:
        traceback.print_exc()
        ok = False
    finally:
        # Always attempt to pause at the end when requested.
        if bool(pause_on_end):
            pre_pause_flight = None
            try:
                pre_pause_flight = readers.flight_snapshot(conn)
            except Exception:
                pre_pause_flight = None
            try:
                paused = _try_pause(conn)
            except Exception:
                paused = None
        restore_after_exec(cleanup)

    # Ensure logs flush before emitting final meta line
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass

    meta = {
        "ok": ok,
        "paused": paused,
        "unpaused": unpaused,
        "exec_time_s": _time.monotonic() - exec_start,
        "pre_pause_flight": (locals().get('pre_pause_flight', None)),
    }
    print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
    return


if __name__ == "__main__":
    main()
