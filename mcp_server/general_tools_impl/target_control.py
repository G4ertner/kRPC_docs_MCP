from __future__ import annotations

from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def set_target_body(address: str = DEFAULT_KRPC_ADDRESS, body_name: str | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Set the active vessel's target body (also tries SpaceCenter.target_body).

    Args:
      body_name: Exact body name (e.g., 'Mun')

    Returns:
      Human‑readable status string or an error if not found.
    """
    if body_name is None:
        raise ValueError("body_name is required")
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    sc = conn.space_center
    v = sc.active_vessel
    try:
        b = sc.bodies.get(body_name)
        if b is None:
            return f"Body '{body_name}' not found."
        # Set both vessel- and spacecenter-level targets when available
        try:
            v.target_body = b
        except Exception:
            pass
        try:
            setattr(sc, 'target_body', b)
        except Exception:
            pass
        return f"Target body set to {getattr(b, 'name', body_name)}."
    except Exception as e:
        return f"Failed to set target body: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def set_target_vessel(address: str = DEFAULT_KRPC_ADDRESS, vessel_name: str | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Set the active vessel's target vessel by name (case‑insensitive). Chooses nearest if multiple.
    Also attempts to set SpaceCenter.target_vessel.

    Args:
      vessel_name: Exact or case‑insensitive vessel name

    Returns:
      Human‑readable status string or error if not found.
    """
    if vessel_name is None:
        raise ValueError("vessel_name is required")
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    sc = conn.space_center
    v = sc.active_vessel
    try:
        candidates = [ov for ov in sc.vessels if ov.name == vessel_name]
        if not candidates:
            # Case-insensitive match
            candidates = [ov for ov in sc.vessels if ov.name.lower() == vessel_name.lower()]
        if not candidates:
            return f"Vessel '{vessel_name}' not found."
        # Prefer nearest if multiple
        cb = v.orbit.body
        ref = getattr(cb, 'non_rotating_reference_frame', cb.reference_frame)
        vp = v.position(ref)
        target = sorted(candidates, key=lambda ov: sum((ov.position(ref)[i]-vp[i])**2 for i in range(3)) if ov.id != v.id else 0)[0]
        # Set both vessel- and spacecenter-level targets when available
        try:
            v.target_vessel = target
        except Exception:
            pass
        try:
            setattr(sc, 'target_vessel', target)
        except Exception:
            pass
        return f"Target vessel set to {target.name}."
    except Exception as e:
        return f"Failed to set target vessel: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def clear_target(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Clear target_docking_port, target_vessel, and target_body if set.

    Returns:
      Human‑readable status string: 'Cleared target.' or 'No target to clear.'
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    v = conn.space_center.active_vessel
    cleared = 0
    try:
        v.target_docking_port = None
        cleared += 1
    except Exception:
        pass
    try:
        v.target_vessel = None
        cleared += 1
    except Exception:
        pass
    try:
        v.target_body = None
        cleared += 1
    except Exception:
        pass
    try:
        return "Cleared target." if cleared else "No target to clear."
    finally:
        try:
            conn.close()
        except Exception:
            pass
