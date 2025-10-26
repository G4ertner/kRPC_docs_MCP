from __future__ import annotations

from .client import connect_to_game, KRPCConnectionError
from ..server import mcp
from . import readers
import json


@mcp.tool()
def krpc_get_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Connect to a running kRPC server and return its version (and active vessel if available).

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
        conn = connect_to_game(address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)
    except KRPCConnectionError as e:
        return f"Connection failed: {e}"

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


# Easy set tools

def _connect(address: str, rpc_port: int, stream_port: int, name: str | None, timeout: float):
    return connect_to_game(address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def get_vessel_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.vessel_info(conn))


@mcp.tool()
def get_environment_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.environment_info(conn))


@mcp.tool()
def get_flight_snapshot(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.flight_snapshot(conn))


@mcp.tool()
def get_orbit_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.orbit_info(conn))


@mcp.tool()
def get_time_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.time_status(conn))


@mcp.tool()
def get_attitude_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.attitude_status(conn))


@mcp.tool()
def get_aero_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.aero_status(conn))


@mcp.tool()
def list_maneuver_nodes(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.maneuver_nodes_basic(conn))


@mcp.tool()
def get_status_overview(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Return a combined snapshot of core vessel/game status in a single call.

    Sections included: vessel, environment, flight, orbit, time, attitude, aero, maneuver_nodes.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    out = {
        "vessel": readers.vessel_info(conn),
        "environment": readers.environment_info(conn),
        "flight": readers.flight_snapshot(conn),
        "orbit": readers.orbit_info(conn),
        "time": readers.time_status(conn),
        "attitude": readers.attitude_status(conn),
        "aero": readers.aero_status(conn),
        "maneuver_nodes": readers.maneuver_nodes_basic(conn),
    }
    return json.dumps(out)
