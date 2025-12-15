from __future__ import annotations

from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def compute_burn_time(address: str = DEFAULT_KRPC_ADDRESS, dv_m_s: float | None = None, environment: str = "current", rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Estimate burn time for a given delta-v using current (or specified) thrust and Isp.

    When to use:
      - Size burns for warp lead time, node placement, or staging checks.

    Args:
      dv_m_s: Desired delta-v in m/s
      environment: 'current' | 'sea_level' | 'vacuum' — controls Isp estimate

    Returns:
      JSON with mass, thrust, Isp, burn_time_simple_s and burn_time_tsiolkovsky_s.
    """
    if dv_m_s is None:
        raise ValueError("dv_m_s is required")
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    env = (environment or "current").lower()
    if env not in ("current", "sea_level", "vacuum"):
        env = "current"
    try:
        return json_dumps(readers.compute_burn_time(conn, dv_m_s=dv_m_s, environment=env))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def compute_circularize_node(address: str = DEFAULT_KRPC_ADDRESS, at: str = "apoapsis", rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Propose a circularization node at Ap or Pe.

    When to use:
      - Circularize after insertion or cleanup of eccentric orbits.

    Args:
      at: 'apoapsis' | 'periapsis'

    Returns:
      Proposal: { ut, prograde, normal=0, radial=0, v_now_m_s, v_circ_m_s }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.propose_circularize_node(conn, at=at))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def compute_plane_change_nodes(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Propose plane change burns at next AN/DN relative to target (vessel/body).

    When to use:
      - Align inclinations before rendezvous or transfers.

    Returns UT and normal delta-v suggestions for AN and DN when available.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.propose_plane_change_nodes(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def compute_raise_lower_node(address: str = DEFAULT_KRPC_ADDRESS, kind: str | None = None, target_alt_m: float | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Propose a single‑burn node to raise/lower apoapsis or periapsis to target_alt_m.

    Args:
      kind: 'apoapsis' | 'periapsis'
      target_alt_m: Desired altitude above sea level in meters

    Returns:
      Proposal: { ut, prograde, normal=0, radial=0, v_now_m_s, v_target_m_s }.
    """
    if kind is None:
        raise ValueError("kind is required")
    if target_alt_m is None:
        raise ValueError("target_alt_m is required")
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.propose_raise_lower_node(conn, kind=kind, target_alt_m=target_alt_m))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def compute_rendezvous_phase_node(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Suggest a phasing orbit to rendezvous with the current target vessel in the same SOI.

    When to use:
      - Align orbital periods to time an intercept with a target vessel.

    Returns:
      Proposal at next Pe: { ut, prograde, normal=0, radial=0, P_phase_s, m, T_align_s }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.propose_rendezvous_phase_node(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def compute_transfer_window_to_body(address: str = DEFAULT_KRPC_ADDRESS, body_name: str | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Compute a Hohmann transfer window to a target body (moon or interplanetary).

    When to use:
      - Time interplanetary or moon transfers from current body context.

    Returns phase_now/required/error, time_to_window_s, ut_window, and transfer time.
    Robust fallbacks infer the star/common parent when parent references are missing.
    """
    if body_name is None:
        raise ValueError("body_name is required")
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.propose_transfer_window_to_body(conn, target_body_name=body_name))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def compute_ejection_node_to_body(address: str = DEFAULT_KRPC_ADDRESS, body_name: str | None = None, parking_alt_m: float | None = None, environment: str = "current", rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Coarse ejection burn estimate for an interplanetary transfer to the target body.

    When to use:
      - After computing a transfer window, to place the ejection burn.

    Args:
      body_name: Target planet
      parking_alt_m: Circular parking orbit altitude (m) around current body
      environment: Isp environment for burn-time followups ('current'|'sea_level'|'vacuum')

    Returns:
      Proposal at UT window: { ut, prograde, normal=0, radial=0, v_inf_m_s, time_to_window_s }.
    """
    if body_name is None:
        raise ValueError("body_name is required")
    if parking_alt_m is None:
        raise ValueError("parking_alt_m is required")
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    env = (environment or "current").lower()
    if env not in ("current", "sea_level", "vacuum"):
        env = "current"
    try:
        return json_dumps(readers.propose_ejection_node_to_body(conn, target_body_name=body_name, parking_alt_m=parking_alt_m, environment=env))
    finally:
        try:
            conn.close()
        except Exception:
            pass
