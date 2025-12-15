from __future__ import annotations

import base64
import datetime as _dt
import ipaddress
import threading
import time
from pathlib import Path
from typing import Any

from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS

_SCREENSHOT_DIR = Path.cwd() / "artifacts" / "screenshots"
_LATEST_SCREENSHOT_JSON: str | None = None
_LATEST_FILENAME: str | None = None
_SEQ_LOCK = threading.Lock()
_SEQ = 0


def _is_local_address(address: str) -> bool:
    if not address:
        return False
    addr = address.strip()
    try:
        ip = ipaddress.ip_address(addr)
        return ip.is_loopback
    except ValueError:
        return addr.lower() in {"localhost"}


def _cache_latest(payload_json: str, filename: str) -> None:
    global _LATEST_SCREENSHOT_JSON, _LATEST_FILENAME
    _LATEST_SCREENSHOT_JSON = payload_json
    _LATEST_FILENAME = filename


def _next_seq() -> int:
    global _SEQ
    with _SEQ_LOCK:
        _SEQ += 1
        return _SEQ


def _format_utc_timestamp_ms(now: _dt.datetime) -> str:
    # Compact, filename-safe ISO-ish format with millisecond resolution.
    # Example: 20251214T013142123Z
    ms = now.microsecond // 1000
    return now.strftime("%Y%m%dT%H%M%S") + f"{ms:03d}Z"


def _allocate_unique_screenshot_path(now: _dt.datetime | None = None) -> tuple[str, Path, str]:
    """
    Allocate a unique screenshot filename/path.

    Returns: (filename, path, captured_at)
    """
    ts = _format_utc_timestamp_ms(now or _dt.datetime.utcnow())
    _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # Always include a per-process sequence to guarantee uniqueness even if called
    # multiple times within the same millisecond.
    for _ in range(1000):
        seq = _next_seq()
        filename = f"ksp_screenshot_{ts}_{seq:06d}.png"
        path = _SCREENSHOT_DIR / filename
        if not path.exists():
            return filename, path, ts

    # Extremely defensive fallback (should never happen unless the directory is full of
    # colliding files and we looped out).
    filename = f"ksp_screenshot_{ts}_{time.time_ns()}.png"
    path = _SCREENSHOT_DIR / filename
    return filename, path, ts


def get_latest_cached() -> str:
    return _LATEST_SCREENSHOT_JSON or json_dumps({"error": "No screenshot captured yet. Call get_screenshot first."})


def get_cached_filename() -> str | None:
    return _LATEST_FILENAME


def resource_payload_for(filename: str) -> str:
    safe_name = Path(filename).name
    path = _SCREENSHOT_DIR / safe_name
    if not path.exists():
        return json_dumps({"error": f"Screenshot '{safe_name}' not found. Capture one with get_screenshot first."})
    data = path.read_bytes()
    return json_dumps({
        "filename": safe_name,
        "mime": "image/png",
        "data_base64": base64.b64encode(data).decode("ascii"),
    })


def get_screenshot(
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    timeout: float = 5.0,
    *,
    scale: int = 1,
) -> str:
    """
    Capture a screenshot via SpaceCenter.screenshot and return the PNG as base64.
    """
    if not _is_local_address(address):
        return json_dumps({
            "error": "get_screenshot requires the MCP server and KSP to run on the same PC. "
                     "Use 127.0.0.1/localhost/::1 to capture screenshots."
        })
    try:
        scale_val = max(1, min(int(scale), 4))
    except (TypeError, ValueError):
        scale_val = 1

    filename, path, captured_at = _allocate_unique_screenshot_path()

    conn = open_connection(address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)
    try:
        sc = conn.space_center
        sc.screenshot(str(path), scale_val)
    except Exception as exc:
        return json_dumps({"error": f"Failed to capture screenshot: {exc}"})
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not path.exists():
        # Some platforms flush the screenshot asynchronously; wait briefly before failing.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if path.exists():
                break
            time.sleep(0.05)
    if not path.exists():
        return json_dumps({"error": f"Screenshot command executed but no file was created at {path}."})

    data = path.read_bytes()
    payload: dict[str, Any] = {
        "ok": True,
        "filename": filename,
        "saved_path": str(path),
        "resource_uri": f"resource://screenshots/{filename}",
        "scale": scale_val,
        "captured_at": captured_at,
        "image": {
            "mime": "image/png",
            "data_base64": base64.b64encode(data).decode("ascii"),
        },
    }
    payload_json = json_dumps(payload)
    _cache_latest(payload_json, filename)
    return payload_json
