from __future__ import annotations

from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_orbit_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Orbital elements for the active vessel.

    When to use:
      - Planning nodes, verifying orbit changes, or summarizing current orbit.

    Returns:
      JSON: { body, apoapsis_altitude_m, time_to_apoapsis_s, periapsis_altitude_m,
      time_to_periapsis_s, eccentricity, inclination_deg, lan_deg,
      argument_of_periapsis_deg, semi_major_axis_m, period_s }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.orbit_info(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_navigation_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Coarse navigation info to the current target (body or vessel).

    When to use:
      - Pre‑planning checks for plane changes, phasing, and transfers.

    Returns:
      If body target: { target_type: 'body', name, target_sma_m, target_period_s,
      target_inclination_deg, target_lan_deg, phase_angle_deg? }.
      If vessel target: { target_type: 'vessel', name, distance_m?, relative_speed_m_s?,
      relative_inclination_deg?, phase_angle_deg? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json_dumps(readers.navigation_info(conn))


def get_targeting_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Current target summary across vessel/body/docking targets with relative geometry when available.

    Returns:
      JSON: { target_type: 'vessel'|'body'|'docking_port'|None, target_name, target_vessel?,
      distance_m?, relative_speed_m_s? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json_dumps(readers.targeting_info(conn))
