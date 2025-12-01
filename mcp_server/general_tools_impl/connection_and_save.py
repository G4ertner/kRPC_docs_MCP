from __future__ import annotations

import datetime as _dt
import json
import secrets

from ..utils.krpc_helpers import best_effort_pause, open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS
from ..utils.krpc_utils.client import KRPCConnectionError


def krpc_get_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Connect to a running kRPC server and return its version (and active vessel if available).

    When to use:
        - Quick connectivity check and basic context before calling other tools.

    Args:
        address: LAN IP or hostname of the KSP PC
        rpc_port: RPC port (default 50000)
        stream_port: Stream port (default 50001)
        name: Optional connection name shown in kRPC UI
        timeout: Connection timeout in seconds
    Returns:
        A short status string, or an error message if connection fails.
    """
    try:
        conn = open_connection(address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)
    except KRPCConnectionError as e:
        return f"Connection failed: {e}"

    try:
        try:
            version = conn.krpc.get_status().version
        except Exception:
            return "Connected but failed to read server version."

        vessel = None
        try:
            vessel = conn.space_center.active_vessel.name
        except Exception:
            pass
        if vessel:
            return f"kRPC version {version}; active vessel: {vessel}"
        return f"kRPC version {version}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def revert_to_launch(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Revert the current flight to launch (KSP's Revert to Launch).

    When to use:
      - Reset a mission after a failed ascent or test, returning the rocket to the launch pad.

    Notes:
      - This calls SpaceCenter.revert_to_launch(). If revert is disabled or not available in the current scene,
        returns a message indicating it cannot revert.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    sc = conn.space_center
    try:
        can = getattr(sc, 'can_revert_to_launch', True)
        if callable(can):
            can = bool(can())
        if can is False:
            return "Cannot revert to launch in the current state (disabled or unavailable)."
        sc.revert_to_launch()
        return "Reverted to launch."
    except Exception as e:
        return f"Failed to revert to launch: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def save_llm_checkpoint(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, tag: str | None = None, prefix: str = "LLM") -> str:
    """
    Save a game checkpoint under a unique LLM-namespaced name.

    Behavior:
      - Generates a unique save name like: "<prefix>_YYYYmmddTHHMMSSZ_<id>".
      - Uses SpaceCenter.save(name) instead of quicksave() to avoid overwriting the user's quicksave.

    Args:
      tag: Optional label included in the generated name for readability.
      prefix: Namespace prefix (default "LLM").

    Returns JSON: { ok, save_name, note? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    sc = conn.space_center
    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    rid = secrets.token_hex(2)  # small suffix to reduce collisions
    base = f"{prefix}_{ts}"
    if tag:
        base += f"_{tag}"
    save_name = f"{base}_{rid}"
    try:
        sc.save(save_name)
        return json.dumps({"ok": True, "save_name": save_name})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def load_llm_checkpoint(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, save_name: str = "", require_llm_prefix: bool = True, pause_after: bool = True) -> str:
    """
    Load a previously saved checkpoint by name using SpaceCenter.load(name).

    Safeguards:
      - By default, only loads names starting with "LLM_" (set require_llm_prefix=false to override).

    Returns JSON: { ok, loaded?: save_name, error? }.
    """
    if not save_name:
        return json.dumps({"ok": False, "error": "Provide save_name"})
    if require_llm_prefix and not save_name.startswith("LLM_"):
        return json.dumps({"ok": False, "error": "Refusing to load non-LLM save (set require_llm_prefix=false to override)"})
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    sc = conn.space_center
    try:
        sc.load(save_name)
        if pause_after:
            best_effort_pause(conn)
        return json.dumps({"ok": True, "loaded": save_name})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def quicksave(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Save a quicksave (SpaceCenter.quicksave()).

    Notes:
      - This overwrites the game's single quicksave slot. Prefer save_llm_checkpoint to create namespaced saves.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        conn.space_center.quicksave()
        return "Quicksaved."
    except Exception as e:
        return f"Failed to quicksave: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def quickload(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, pause_after: bool = True) -> str:
    """
    Load from the quicksave slot (SpaceCenter.quickload()).

    Notes:
      - Prefer load_llm_checkpoint for named saves to avoid conflict with a player's quicksave.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        conn.space_center.quickload()
        if pause_after:
            best_effort_pause(conn)
        return "Quickloaded."
    except Exception as e:
        return f"Failed to quickload: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass
