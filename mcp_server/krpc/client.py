from __future__ import annotations

from typing import Optional
import socket


class KRPCConnectionError(RuntimeError):
    pass


def connect_to_game(
    address: str,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    *,
    name: Optional[str] = None,
    timeout: float = 5.0,
):
    """
    Connect to a running kRPC server (Protobuf over TCP) and return the client connection.

    Args:
        address: IP or hostname of the PC running KSP+kRPC (LAN IP, not localhost)
        rpc_port: RPC port configured in kRPC (default 50000)
        stream_port: Stream port configured in kRPC (default 50001)
        name: Optional connection name shown in kRPC UI
        timeout: Socket timeout in seconds for the initial connection

    Returns:
        krpc.client.Client

    Raises:
        KRPCConnectionError: On timeout or connection failure with a helpful message
    """
    try:
        import krpc  # Lazy import so the server can start without krpc installed
    except Exception as e:  # pragma: no cover
        raise KRPCConnectionError(
            "Python package 'krpc' is not installed. Install with 'uv pip install krpc'"
        ) from e

    prev = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        try:
            conn = krpc.connect(
                name=name or "kRPC_docs_MCP",
                address=address,
                rpc_port=rpc_port,
                stream_port=stream_port,
            )
        except Exception as e:
            raise KRPCConnectionError(
                f"Failed to connect to kRPC at {address}:{rpc_port}/{stream_port}: {e}"
            ) from e

        # Verify the connection by fetching server status
        try:
            _ = conn.krpc.get_status().version
        except Exception as e:
            raise KRPCConnectionError(
                "Connected but failed to fetch server status. Check protocol/ports match "
                "(use 'Protobuf over TCP' and ensure RPC/Stream ports)."
            ) from e
        return conn
    finally:
        socket.setdefaulttimeout(prev)

