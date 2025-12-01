from __future__ import annotations

import json

from ..utils.krpc_utils import readers
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def list_docking_ports(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List docking ports on the active vessel and their states.

    Returns:
      JSON array: { part, state, ready, dockee }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json.dumps(readers.docking_ports(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass
