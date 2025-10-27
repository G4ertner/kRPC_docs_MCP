from __future__ import annotations

import json
import sys
import traceback
import time as _time
from pathlib import Path
from typing import Any, Dict

from ..krpc.client import connect_to_game
from .injectors import build_globals, restore_after_exec
from .parsers import EXEC_META_PREFIX


def _try_pause(conn) -> bool | None:
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


def _load_config() -> Dict[str, Any]:
    cfg_env = sys.argv[1] if len(sys.argv) > 1 else None
    if not cfg_env:
        raise SystemExit("Missing runner config JSON argument")
    try:
        cfg = json.loads(cfg_env)
    except Exception as e:  # pragma: no cover
        raise SystemExit(f"Invalid runner config JSON: {e}")
    return cfg


def main() -> None:
    cfg = _load_config()
    code_path = Path(cfg["code_path"]).resolve()
    address = cfg["address"]
    rpc_port = int(cfg.get("rpc_port", 50000))
    stream_port = int(cfg.get("stream_port", 50001))
    name = cfg.get("name")
    timeout_sec = float(cfg.get("timeout_sec", 120.0))
    allow_imports = bool(cfg.get("allow_imports", False))
    pause_on_end = bool(cfg.get("pause_on_end", True))

    exec_start = _time.monotonic()
    paused: bool | None = None

    try:
        conn = connect_to_game(address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=min(timeout_sec, 10.0))
    except Exception:
        # Print traceback to stderr for parent to parse
        traceback.print_exc()
        meta = {
            "ok": False,
            "paused": None,
            "exec_time_s": _time.monotonic() - exec_start,
        }
        print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
        sys.exit(1)

    try:
        glb, cleanup = build_globals(conn, timeout_sec=timeout_sec, allow_imports=allow_imports)
    except Exception:
        traceback.print_exc()
        meta = {
            "ok": False,
            "paused": None,
            "exec_time_s": _time.monotonic() - exec_start,
        }
        print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
        sys.exit(1)

    try:
        code = code_path.read_text(encoding="utf-8")
    except Exception:
        traceback.print_exc()
        meta = {
            "ok": False,
            "paused": None,
            "exec_time_s": _time.monotonic() - exec_start,
        }
        print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
        sys.exit(1)

    try:
        exec(compile(code, "<user_code>", "exec"), glb, glb)
        if pause_on_end:
            paused = _try_pause(conn)
        ok = True
    except Exception:
        traceback.print_exc()
        ok = False
    finally:
        restore_after_exec(cleanup)

    meta = {
        "ok": ok,
        "paused": paused,
        "exec_time_s": _time.monotonic() - exec_start,
    }
    print(f"{EXEC_META_PREFIX}{json.dumps(meta)}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
