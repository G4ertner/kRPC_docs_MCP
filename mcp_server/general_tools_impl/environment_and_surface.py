from __future__ import annotations

import json

from ..utils.krpc_utils import readers
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_environment_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Environment info for the current body and situation.

    When to use:
      - Context for aerodynamics, entry/landing planning, and surface ops.

    Args:
      address: LAN IP/hostname of the KSP PC
      rpc_port: kRPC RPC port (default 50000)
      stream_port: kRPC stream port (default 50001)
      name: Optional connection name shown in kRPC UI
      timeout: Connection timeout in seconds

    Returns:
      JSON: { body, in_atmosphere, surface_gravity_m_s2, biome?, static_pressure_pa?,
      temperature_k?, atmosphere, atmosphere_depth_m }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json.dumps(readers.environment_info(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_surface_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Surface context at current location: latitude/longitude, surface altitude, terrain height,
    estimated ground slope, and ground speed.

    Returns:
      JSON: { latitude_deg, longitude_deg, surface_altitude_m, terrain_height_m,
      slope_deg, ground_speed_m_s, body }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.surface_info(conn))
