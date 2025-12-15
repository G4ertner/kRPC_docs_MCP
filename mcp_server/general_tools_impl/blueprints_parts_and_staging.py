from __future__ import annotations

from .blueprints import set_latest_vessel_blueprint
from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_part_tree(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Hierarchical part tree with staging and module/resource summaries.

    Note:
      This synchronous call can exceed the CLI's 60 s limit on large vessels.
      Prefer start_part_tree_job -> get_job_status(job_id) -> read_resource(result_resource)
      when you need a full tree safely; fall back to this direct call only for quick checks.

    Returns:
      JSON: { parts: [ { id, title, name, tag?, stage, decouple_stage?, parent_id?, children_ids[],
              modules: [...], resources: {R:{amount,max}}, crossfeed? } ] }
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.part_tree(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_vessel_blueprint(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Idealized vessel blueprint combining meta, stage plan, engines, control capabilities, and part tree.

    When to use:
      - Give the agent a structural understanding of the craft before writing scripts.

    Returns:
      JSON with sections: meta, stages, engines, control_capabilities, parts, geometry, notes.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        bp = readers.vessel_blueprint(conn)
        try:
            # Cache for blueprint resource
            set_latest_vessel_blueprint(bp)
        except Exception:
            pass
        return json_dumps(bp)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_blueprint_ascii(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Compact ASCII schematic/summary of the current vessel by stage.

    Includes a header and a per-stage table with engine counts, Δv, TWR,
    and key part category counts (Eng/Tank/Dec/Par/Dock).
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        s = readers.blueprint_ascii(conn)
        return s
    except Exception as e:
        return f"Failed to build ASCII blueprint: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_stage_plan(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, environment: str = "current") -> str:
    """
    Approximate stock‑like staging plan by grouping decouple‑only stages under the
    preceding engine stage.

    Note:
      For big rockets this direct call can exceed the 60 s CLI limit. Prefer
      start_stage_plan_job -> get_job_status(job_id) -> read_resource(result_resource)
      to fetch the JSON artifact safely, and reserve this helper for quick snapshots.

    When to use:
      - Match KSP’s staging view for Δv/TWR per engine stage.

    Args:
      environment: 'current' | 'sea_level' | 'vacuum' — controls Isp used

    Returns:
      JSON: { stages: [ { stage, engines, max_thrust_n, combined_isp_s?, prop_mass_kg,
      m0_kg, m1_kg, delta_v_m_s?, twr_surface? } ] }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    env = (environment or "current").lower()
    if env not in ("current", "sea_level", "vacuum"):
        env = "current"
    try:
        return json_dumps(readers.stage_plan_approx(conn, environment=env))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_staging_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Approximate per-stage delta‑v and TWR plan using current engine Isp and resource masses.

    When to use:
      - Quick staging analysis for mission planning and sanity checks.

    Returns:
      JSON: { current_stage, stages: [ { stage, engines, max_thrust_n,
      combined_isp_s?, delta_v_m_s?, twr_surface?, prop_mass_kg, m0_kg, m1_kg } ] }.

    Note: Uses standard KSP resource densities and current environment Isp; results are estimates.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.staging_info(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass
