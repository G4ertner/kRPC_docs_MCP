from __future__ import annotations

DEFAULT_KRPC_ADDRESS = "127.0.0.1"

from .krpc_utils.client import connect_to_game
from .async_utils import run_blocking


def open_connection(
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    timeout: float = 5.0,
):
    """Helper that mirrors the legacy _connect signature but lives in utils."""
    return connect_to_game(
        address,
        rpc_port=rpc_port,
        stream_port=stream_port,
        name=name,
        timeout=timeout,
    )


async def async_open_connection(
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    timeout: float = 5.0,
    *,
    hard_timeout_sec: float | None = 60.0,
):
    """
    Async helper that opens a kRPC connection off the event loop with a hard timeout.

    Args mirror open_connection; `timeout` is the socket-level timeout, `hard_timeout_sec`
    caps total wall time for establishing the connection. Pass None to disable the cap.
    """

    return await run_blocking(
        connect_to_game,
        address,
        rpc_port=rpc_port,
        stream_port=stream_port,
        name=name,
        timeout=timeout,
        timeout_sec=hard_timeout_sec,
    )


def best_effort_pause(conn):
    """Internal pause helper shared between executor and general tools."""
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


def best_effort_unpause(conn):
    """Best-effort helper to resume physics, mirroring executor logic."""
    try:
        if bool(conn.krpc.paused):
            conn.krpc.paused = False
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


def best_effort_paused_state(conn) -> bool | None:
    """Return a best-effort paused flag without changing state."""
    try:
        return bool(conn.krpc.paused)
    except Exception:
        pass
    try:
        sc = conn.space_center
    except Exception:
        return None
    for attr in ("paused", "is_paused"):
        try:
            if hasattr(sc, attr):
                return bool(getattr(sc, attr))
        except Exception:
            continue
    return None
