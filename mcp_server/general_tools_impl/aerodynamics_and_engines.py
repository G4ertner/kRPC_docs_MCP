from __future__ import annotations

from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_aero_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Aerodynamic state.

    When to use:
      - Ascent/descent control, max-Q checks, aero stress monitoring.

    Returns:
      JSON: { dynamic_pressure_pa, mach, atmosphere_density_kg_m3, drag?, lift? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.aero_status(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_engine_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Per-engine status for the active vessel.

    When to use:
      - Engine diagnostics before/after burns, checking flameouts or throttling.

    Returns:
      JSON array of engines with: { part, active, has_fuel, flameout, thrust_n,
      max_thrust_n, specific_impulse_s, throttle }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json_dumps(readers.engine_status(conn))
