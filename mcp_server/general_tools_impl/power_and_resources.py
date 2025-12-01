from __future__ import annotations

import json

from ..utils.krpc_utils import readers
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_power_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    ElectricCharge summary with generator/consumer counts and best‑effort estimates.

    When to use:
      - Power budgeting, troubleshooting brown‑outs, and mission readiness checks.

    Returns:
      JSON: { vessel_totals: { amount, max }, production: { solar?, rtg?, fuel_cells? },
      consumers: { wheels?, antennas?, lights? }, notes?: [..] }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json.dumps(readers.power_status(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_resource_breakdown(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Aggregate resource totals for the whole vessel and the current stage.

    When to use:
      - Fuel/electricity accounting, staging decisions, consumables monitoring.

    Returns:
      JSON: { vessel_totals: {Resource: {amount, max}}, stage_totals: {…}, current_stage }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json.dumps(readers.resource_breakdown(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass
