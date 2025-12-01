from __future__ import annotations

import json

from ..utils.krpc_utils import readers
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def list_launch_sites(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List available launch sites (e.g., "LaunchPad", "Runway").
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        sc = conn.space_center
        raw = getattr(sc, "launch_sites", None)
        names: list[str] = []
        if raw is None:
            names = []
        else:
            try:
                iterable = list(raw)
            except Exception:
                iterable = raw
            names = [getattr(s, "name", str(s)) for s in iterable]
        return json.dumps({"launch_sites": names})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_launchable_vessels(address: str = DEFAULT_KRPC_ADDRESS, craft_directory: str = "VAB", rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List the names of craft files that can be launched from the specified directory ("VAB" or "SPH").
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        sc = conn.space_center
        items = list(sc.launchable_vessels(craft_directory) or [])
        return json.dumps({"craft_directory": craft_directory, "vessels": items})
    except Exception as e:
        return json.dumps({"craft_directory": craft_directory, "error": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def launch_vessel(address: str = DEFAULT_KRPC_ADDRESS, craft_directory: str = "VAB", name: str | None = None, launch_site: str = "LaunchPad", recover: bool = True, crew: list[str] | None = None, flag_url: str = "", rpc_port: int = 50000, stream_port: int = 50001, conn_name: str | None = None, timeout: float = 10.0) -> str:
    """
    Launch a saved vessel (.craft) to a site via SpaceCenter.launch_vessel.

    Args:
      craft_directory: "VAB" or "SPH"
      name: Craft filename without ".craft" (must exist in the save's Ships/<dir> folder)
      launch_site: "LaunchPad" or "Runway"
      recover: If true, recover an existing vessel on the site before launch
      crew: Optional list of Kerbal names to assign
      flag_url: Optional asset URL for mission flag

    Returns JSON: { ok, active_vessel?, error? }.
    """
    if name is None:
        raise ValueError("name is required")
    conn = open_connection(address, rpc_port, stream_port, conn_name, timeout)
    try:
        sc = conn.space_center
        # kRPC requires a list for crew; use empty list when None
        crew_list = list(crew) if crew is not None else []
        sc.launch_vessel(craft_directory, name, launch_site, recover, crew_list, flag_url or "")
        av = None
        try:
            av = sc.active_vessel.name
        except Exception:
            av = None
        return json.dumps({"ok": True, "active_vessel": av, "launch_site": launch_site})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_vessels(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List vessels in the current save with type/situation and optional distance.

    Returns:
      JSON array: { name, type?, situation?, distance_m? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.list_vessels(conn))
