from __future__ import annotations

from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def list_bodies(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List celestial bodies known to kRPC with key metadata.

    When to use:
      - Pick targets for transfers; validate body names.

    Returns:
      JSON array: { name, parent?, has_atmosphere, radius_m, soi_radius_m }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.list_bodies(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_waypoints(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Waypoints known to the waypoint manager, with vessel-relative range/bearing where possible.

    Returns:
      JSON array: { name, body, latitude_deg, longitude_deg, altitude_m,
      distance_m?, bearing_deg? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.list_waypoints(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass
