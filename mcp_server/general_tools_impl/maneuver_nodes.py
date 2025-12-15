from __future__ import annotations

from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import (
    open_connection,
)
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS
from ..executor_impl import job_tools


def list_maneuver_nodes(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List basic maneuver nodes.

    When to use:
      - Quick overview of planned burns with timing and total delta‑v.

    Returns:
      JSON array: { ut, time_to_node_s, delta_v_m_s }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.maneuver_nodes_basic(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_maneuver_nodes_detailed(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Detailed maneuver nodes for the active vessel including vector and simple burn-time estimate.

    Returns:
      JSON array: { ut, time_to_node_s, delta_v_vector_m_s, delta_v_total_m_s,
      burn_time_simple_s? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json_dumps(readers.maneuver_nodes_detailed(conn))


def set_maneuver_node(address: str = DEFAULT_KRPC_ADDRESS, ut: float | None = None, prograde: float = 0.0, normal: float = 0.0, radial: float = 0.0, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Create a maneuver node at a specific UT with given vector components.

    When to use:
      - Apply a proposed burn from compute_* helpers to the game.
      - LLM: After creating the node, set SAS to target via set_sas_mode before executing the burn.

    Args:
      ut: Universal time for the node
      prograde: Prograde component (m/s)
      normal: Normal component (m/s)
      radial: Radial component (m/s)

    Returns:
      JSON echo of the created node parameters.
    """
    if ut is None:
        raise ValueError("ut is required")
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    ctrl = conn.space_center.active_vessel.control
    try:
        node = ctrl.add_node(ut, prograde, normal, radial)
        return json_dumps({
            "ut": getattr(node, 'ut', ut),
            "prograde": prograde,
            "normal": normal,
            "radial": radial,
        })
    except Exception as e:
        return f"Failed to create node: {e}"


def update_maneuver_node(address: str = DEFAULT_KRPC_ADDRESS, node_index: int = 0, ut: float | None = None, prograde: float | None = None, normal: float | None = None, radial: float | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Edit an existing maneuver node (default: first node).

    Args:
      node_index: 0‑based index (default: 0)
      ut/prograde/normal/radial: Components to update (None to leave unchanged)

    Returns:
      JSON echo of the updated node: { index, ut, prograde, normal, radial }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    ctrl = conn.space_center.active_vessel.control
    try:
        nodes = list(ctrl.nodes)
        if not nodes:
            return "No nodes to update."
        idx = max(0, min(node_index, len(nodes)-1))
        n = nodes[idx]
        if ut is not None:
            n.ut = ut
        if prograde is not None:
            n.prograde = prograde
        if normal is not None:
            n.normal = normal
        if radial is not None:
            n.radial = radial
        return json_dumps({
            "index": idx,
            "ut": getattr(n, 'ut', ut),
            "prograde": getattr(n, 'prograde', prograde),
            "normal": getattr(n, 'normal', normal),
            "radial": getattr(n, 'radial', radial),
        })
    except Exception as e:
        return f"Failed to update node: {e}"


def delete_maneuver_nodes(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Remove all maneuver nodes for the active vessel.

    When to use:
      - Cleanup after executing nodes or starting a new plan.

    Returns:
      Human‑readable status string with count removed.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    ctrl = conn.space_center.active_vessel.control
    try:
        count = 0
        for n in list(ctrl.nodes):
            try:
                n.remove(); count += 1
            except Exception:
                continue
        return f"Removed {count} nodes."
    except Exception as e:
        return f"Failed to remove nodes: {e}"


def warp_to(address: str = DEFAULT_KRPC_ADDRESS, ut: float | None = None, lead_time_s: float = 0.0, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Best‑effort warp‑to.

    When to use:
      - Warp to a node or event time with optional lead time.

    Args:
      ut: Target universal time to arrive at
      lead_time_s: Seconds to arrive before UT (e.g., half burn time)

    Returns:
      Human‑readable status string, or a message if unsupported.
    """
    if ut is None:
        raise ValueError("ut is required")

    # IMPORTANT: Some kRPC servers block the warp_to RPC call until the warp completes, which can
    # exceed Codex CLI's 60s tool-call limit and return a timeout error while KSP keeps warping.
    # To make behavior deterministic, we start a background warp job and return immediately.
    tgt = float(ut) - max(0.0, float(lead_time_s))
    job_id = job_tools._start_warp_job_impl(
        params={
            "ut": float(ut),
            "lead_time_s": float(lead_time_s),
            "address": address,
            "rpc_port": rpc_port,
            "stream_port": stream_port,
            "name": name,
            "timeout": timeout,
            "mode": "rails",
            "target_real_time_s": 10.0,
            "settle_at_s": 2.0,
            "max_wall_time_s": None,
        }
    )
    return (
        f"Started warp job {job_id} targeting UT {tgt:.2f}. "
        f"Poll get_job_status('{job_id}_warp') for warp telemetry/ETA or get_job_status('{job_id}') for logs; "
        f"cancel_job('{job_id}') resets warp to realtime."
    )
