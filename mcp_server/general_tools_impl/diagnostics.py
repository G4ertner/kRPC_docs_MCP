from __future__ import annotations

import json

from ..utils.krpc_utils import readers
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_diagnostics(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Collect a richer diagnostics snapshot to aid post-mortems.

    Returns JSON with: vessel, time, environment, flight, orbit, attitude,
    aero, engines, resources, maneuver_nodes, and surface.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        data = {
            "vessel": readers.vessel_info(conn),
            "time": readers.time_status(conn),
            "environment": readers.environment_info(conn),
            "flight": readers.flight_snapshot(conn),
            "orbit": readers.orbit_info(conn),
            "attitude": readers.attitude_status(conn),
            "aero": readers.aero_status(conn),
        }
        try:
            data["engines"] = readers.engine_status(conn)
        except Exception:
            pass
        try:
            data["resources"] = readers.resource_breakdown(conn)
        except Exception:
            pass
        try:
            data["maneuver_nodes"] = readers.maneuver_nodes_basic(conn)
        except Exception:
            pass
        try:
            data["surface"] = readers.surface_info(conn)
        except Exception:
            pass
        return json.dumps(data)
    finally:
        try:
            conn.close()
        except Exception:
            pass
