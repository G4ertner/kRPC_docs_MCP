from __future__ import annotations

from .client import connect_to_game, KRPCConnectionError
from ..server import mcp
from . import readers
import json


@mcp.tool()
def krpc_get_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Connect to a running kRPC server and return its version (and active vessel if available).

    When to use:
        - Quick connectivity check and basic context before calling other tools.

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
    """
    Basic vessel info for the active craft.

    When to use:
      - High-level status summaries and sanity checks prior to planning.

    Args:
      address: LAN IP/hostname of the KSP PC
      rpc_port: kRPC RPC port (default 50000)
      stream_port: kRPC stream port (default 50001)
      name: Optional connection name shown in kRPC UI
      timeout: Connection timeout in seconds

    Returns:
      JSON string: { name, mass_kg, throttle, situation }
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.vessel_info(conn))


@mcp.tool()
def get_environment_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Environment info for the current body and situation.

    When to use:
      - Context for aerodynamics, entry/landing planning, and surface ops.

    Args:
      address: LAN IP/hostname of the KSP PC
      rpc_port: kRPC RPC port (default 50000)
      stream_port: kRPC stream port (default 50001)
      name: Optional connection name shown in kRPC UI
      timeout: Connection timeout in seconds

    Returns:
      JSON: { body, in_atmosphere, surface_gravity_m_s2, biome?, static_pressure_pa?,
      temperature_k?, atmosphere, atmosphere_depth_m }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.environment_info(conn))


@mcp.tool()
def get_flight_snapshot(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Flight snapshot for the active vessel.

    When to use:
      - Real-time monitoring, ascent/descent guidance, atmosphere checks.

    Returns:
      JSON: { altitude_sea_level_m, altitude_terrain_m, vertical_speed_m_s,
      speed_surface_m_s, speed_horizontal_m_s, dynamic_pressure_pa, mach,
      g_force, angle_of_attack_deg, pitch_deg, roll_deg, heading_deg }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.flight_snapshot(conn))


@mcp.tool()
def get_orbit_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Orbital elements for the active vessel.

    When to use:
      - Planning nodes, verifying orbit changes, or summarizing current orbit.

    Returns:
      JSON: { body, apoapsis_altitude_m, time_to_apoapsis_s, periapsis_altitude_m,
      time_to_periapsis_s, eccentricity, inclination_deg, lan_deg,
      argument_of_periapsis_deg, semi_major_axis_m, period_s }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.orbit_info(conn))


@mcp.tool()
def get_time_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Time context for the current save.

    When to use:
      - Scheduling burns, warp decisions, or synchronizing UT across tools.

    Returns:
      JSON: { universal_time_s, mission_time_s }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.time_status(conn))


@mcp.tool()
def get_attitude_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Attitude/control state for the active vessel.

    When to use:
      - Verify SAS/RCS/throttle state and autopilot targets before burns.

    Returns:
      JSON: { sas, sas_mode, rcs, throttle, autopilot_state, autopilot_target_pitch,
      autopilot_target_heading, autopilot_target_roll }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.attitude_status(conn))


@mcp.tool()
def get_aero_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Aerodynamic state.

    When to use:
      - Ascent/descent control, max-Q checks, aero stress monitoring.

    Returns:
      JSON: { dynamic_pressure_pa, mach, atmosphere_density_kg_m3, drag?, lift? }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.aero_status(conn))


@mcp.tool()
def list_maneuver_nodes(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List basic maneuver nodes.

    When to use:
      - Quick overview of planned burns with timing and total delta‑v.

    Returns:
      JSON array: { ut, time_to_node_s, delta_v_m_s }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.maneuver_nodes_basic(conn))


@mcp.tool()
def get_status_overview(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Combined snapshot of core vessel/game status in a single call.

    When to use:
      - Summarize state for planning, logging, or sanity checks.

    Returns:
      JSON: { vessel, environment, flight, orbit, time, attitude, aero, maneuver_nodes }.
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


# Medium batch 1: engines, resources, surface

@mcp.tool()
def get_engine_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Per-engine status for the active vessel.

    When to use:
      - Engine diagnostics before/after burns, checking flameouts or throttling.

    Returns:
      JSON array of engines with: { part, active, has_fuel, flameout, thrust_n,
      max_thrust_n, specific_impulse_s, throttle }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.engine_status(conn))


@mcp.tool()
def get_resource_breakdown(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Aggregate resource totals for the whole vessel and the current stage.

    When to use:
      - Fuel/electricity accounting, staging decisions, consumables monitoring.

    Returns:
      JSON: { vessel_totals: {Resource: {amount, max}}, stage_totals: {…}, current_stage }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.resource_breakdown(conn))


@mcp.tool()
def get_surface_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Surface context at current location: latitude/longitude, surface altitude, terrain height,
    estimated ground slope, and ground speed.

    Returns:
      JSON: { latitude_deg, longitude_deg, surface_altitude_m, terrain_height_m,
      slope_deg, ground_speed_m_s, body }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.surface_info(conn))


# Medium batch 2: targeting, detailed nodes, docking ports

@mcp.tool()
def get_targeting_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Current target summary across vessel/body/docking targets with relative geometry when available.

    Returns:
      JSON: { target_type: 'vessel'|'body'|'docking_port'|None, target_name, target_vessel?,
      distance_m?, relative_speed_m_s? }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.targeting_info(conn))


@mcp.tool()
def list_maneuver_nodes_detailed(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Detailed maneuver nodes for the active vessel including vector and simple burn-time estimate.

    Returns:
      JSON array: { ut, time_to_node_s, delta_v_vector_m_s, delta_v_total_m_s,
      burn_time_simple_s? }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.maneuver_nodes_detailed(conn))


@mcp.tool()
def list_docking_ports(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List docking ports on the active vessel and their states.

    Returns:
      JSON array: { part, state, ready, dockee }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.docking_ports(conn))


# Medium batch 3: camera, waypoints, contracts summary (best-effort)

@mcp.tool()
def get_camera_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Active camera parameters when available: mode, pitch, heading, distance, and limits.

    Returns:
      JSON: { available, mode?, pitch_deg?, heading_deg?, distance_m?,
      min_pitch_deg?, max_pitch_deg?, min_distance_m?, max_distance_m? }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.camera_status(conn))


@mcp.tool()
def list_waypoints(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Waypoints known to the waypoint manager, with vessel-relative range/bearing where possible.

    Returns:
      JSON array: { name, body, latitude_deg, longitude_deg, altitude_m,
      distance_m?, bearing_deg? }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.list_waypoints(conn))


@mcp.tool()
def get_action_groups_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Action group toggles.

    When to use:
      - Verify control safety and configuration pre‑burn or pre‑entry.

    Returns:
      JSON: { sas, rcs, lights, gear, brakes, abort, custom_1..custom_10 }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.action_groups_status(conn))


# Hard: staging with per-stage delta-v (approximate)

@mcp.tool()
def get_staging_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Approximate per-stage delta‑v and TWR plan using current engine Isp and resource masses.

    When to use:
      - Quick staging analysis for mission planning and sanity checks.

    Returns:
      JSON: { current_stage, stages: [ { stage, engines, max_thrust_n,
      combined_isp_s?, delta_v_m_s?, twr_surface?, prop_mass_kg, m0_kg, m1_kg } ] }.

    Note: Uses standard KSP resource densities and current environment Isp; results are estimates.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.staging_info(conn))


@mcp.tool()
def get_stage_plan(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, environment: str = "current") -> str:
    """
    Approximate stock‑like staging plan by grouping decouple‑only stages under the
    preceding engine stage.

    When to use:
      - Match KSP’s staging view for Δv/TWR per engine stage.

    Args:
      environment: 'current' | 'sea_level' | 'vacuum' — controls Isp used

    Returns:
      JSON: { stages: [ { stage, engines, max_thrust_n, combined_isp_s?, prop_mass_kg,
      m0_kg, m1_kg, delta_v_m_s?, twr_surface? } ] }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    env = (environment or "current").lower()
    if env not in ("current", "sea_level", "vacuum"):
        env = "current"
    return json.dumps(readers.stage_plan_approx(conn, environment=env))


@mcp.tool()
def get_navigation_info(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Coarse navigation info to the current target (body or vessel).

    When to use:
      - Pre‑planning checks for plane changes, phasing, and transfers.

    Returns:
      If body target: { target_type: 'body', name, target_sma_m, target_period_s,
      target_inclination_deg, target_lan_deg, phase_angle_deg? }.
      If vessel target: { target_type: 'vessel', name, distance_m?, relative_speed_m_s?,
      relative_inclination_deg?, phase_angle_deg? }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.navigation_info(conn))


@mcp.tool()
def get_power_status(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    ElectricCharge summary with generator/consumer counts and best‑effort estimates.

    When to use:
      - Power budgeting, troubleshooting brown‑outs, and mission readiness checks.

    Returns:
      JSON: { vessel_totals: { amount, max }, production: { solar?, rtg?, fuel_cells? },
      consumers: { wheels?, antennas?, lights? }, notes?: [..] }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.power_status(conn))


# --- Maneuver node tools (Batch 1) ---

@mcp.tool()
def compute_burn_time(address: str, dv_m_s: float, environment: str = "current", rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Estimate burn time for a given delta-v using current (or specified) thrust and Isp.

    When to use:
      - Size burns for warp lead time, node placement, or staging checks.

    Args:
      dv_m_s: Desired delta-v in m/s
      environment: 'current' | 'sea_level' | 'vacuum' — controls Isp estimate

    Returns:
      JSON with mass, thrust, Isp, burn_time_simple_s and burn_time_tsiolkovsky_s.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    env = (environment or "current").lower()
    if env not in ("current", "sea_level", "vacuum"):
        env = "current"
    return json.dumps(readers.compute_burn_time(conn, dv_m_s=dv_m_s, environment=env))


@mcp.tool()
def compute_circularize_node(address: str, at: str = "apoapsis", rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Propose a circularization node at Ap or Pe.

    When to use:
      - Circularize after insertion or cleanup of eccentric orbits.

    Args:
      at: 'apoapsis' | 'periapsis'

    Returns:
      Proposal: { ut, prograde, normal=0, radial=0, v_now_m_s, v_circ_m_s }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.propose_circularize_node(conn, at=at))


@mcp.tool()
def compute_plane_change_nodes(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Propose plane change burns at next AN/DN relative to target (vessel/body).

    When to use:
      - Align inclinations before rendezvous or transfers.

    Returns UT and normal delta-v suggestions for AN and DN when available.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.propose_plane_change_nodes(conn))


@mcp.tool()
def set_maneuver_node(address: str, ut: float, prograde: float = 0.0, normal: float = 0.0, radial: float = 0.0, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Create a maneuver node at a specific UT with given vector components.

    When to use:
      - Apply a proposed burn from compute_* helpers to the game.

    Args:
      ut: Universal time for the node
      prograde: Prograde component (m/s)
      normal: Normal component (m/s)
      radial: Radial component (m/s)

    Returns:
      JSON echo of the created node parameters.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    ctrl = conn.space_center.active_vessel.control
    try:
        node = ctrl.add_node(ut, prograde, normal, radial)
        return json.dumps({
            "ut": getattr(node, 'ut', ut),
            "prograde": prograde,
            "normal": normal,
            "radial": radial,
        })
    except Exception as e:
        return f"Failed to create node: {e}"


@mcp.tool()
def delete_maneuver_nodes(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Remove all maneuver nodes for the active vessel.

    When to use:
      - Cleanup after executing nodes or starting a new plan.

    Returns:
      Human‑readable status string with count removed.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
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


@mcp.tool()
def warp_to(address: str, ut: float, lead_time_s: float = 0.0, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
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
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    sc = conn.space_center
    tgt = ut - max(0.0, lead_time_s)
    try:
        fn = getattr(sc, 'warp_to', None)
        if callable(fn):
            fn(tgt)
            return f"Warping to UT {tgt:.2f}"
    except Exception:
        pass
    try:
        tw = getattr(sc, 'warp', None)
        if tw is not None and hasattr(tw, 'warp_to'):
            tw.warp_to(tgt)
            return f"Warping to UT {tgt:.2f}"
    except Exception:
        pass
    return "warp_to not supported by this kRPC client/server."


@mcp.tool()
def compute_raise_lower_node(address: str, kind: str, target_alt_m: float, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Propose a single‑burn node to raise/lower apoapsis or periapsis to target_alt_m.

    Args:
      kind: 'apoapsis' | 'periapsis'
      target_alt_m: Desired altitude above sea level in meters

    Returns:
      Proposal: { ut, prograde, normal=0, radial=0, v_now_m_s, v_target_m_s }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.propose_raise_lower_node(conn, kind=kind, target_alt_m=target_alt_m))


@mcp.tool()
def compute_rendezvous_phase_node(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Suggest a phasing orbit to rendezvous with the current target vessel in the same SOI.

    When to use:
      - Align orbital periods to time an intercept with a target vessel.

    Returns:
      Proposal at next Pe: { ut, prograde, normal=0, radial=0, P_phase_s, m, T_align_s }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.propose_rendezvous_phase_node(conn))


@mcp.tool()
def compute_transfer_window_to_body(address: str, body_name: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Compute a Hohmann transfer window to a target body (moon or interplanetary).

    When to use:
      - Time interplanetary or moon transfers from current body context.

    Returns phase_now/required/error, time_to_window_s, ut_window, and transfer time.
    Robust fallbacks infer the star/common parent when parent references are missing.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.propose_transfer_window_to_body(conn, target_body_name=body_name))


@mcp.tool()
def compute_ejection_node_to_body(address: str, body_name: str, parking_alt_m: float, environment: str = "current", rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Coarse ejection burn estimate for an interplanetary transfer to the target body.

    When to use:
      - After computing a transfer window, to place the ejection burn.

    Args:
      body_name: Target planet
      parking_alt_m: Circular parking orbit altitude (m) around current body
      environment: Isp environment for burn-time followups ('current'|'sea_level'|'vacuum')

    Returns:
      Proposal at UT window: { ut, prograde, normal=0, radial=0, v_inf_m_s, time_to_window_s }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    env = (environment or "current").lower()
    if env not in ("current", "sea_level", "vacuum"):
        env = "current"
    return json.dumps(readers.propose_ejection_node_to_body(conn, target_body_name=body_name, parking_alt_m=parking_alt_m, environment=env))


@mcp.tool()
def update_maneuver_node(address: str, node_index: int = 0, ut: float | None = None, prograde: float | None = None, normal: float | None = None, radial: float | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Edit an existing maneuver node (default: first node).

    Args:
      node_index: 0‑based index (default: 0)
      ut/prograde/normal/radial: Components to update (None to leave unchanged)

    Returns:
      JSON echo of the updated node: { index, ut, prograde, normal, radial }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
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
        return json.dumps({
            "index": idx,
            "ut": getattr(n, 'ut', ut),
            "prograde": getattr(n, 'prograde', prograde),
            "normal": getattr(n, 'normal', normal),
            "radial": getattr(n, 'radial', radial),
        })
    except Exception as e:
        return f"Failed to update node: {e}"


@mcp.tool()
def list_bodies(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List celestial bodies known to kRPC with key metadata.

    When to use:
      - Pick targets for transfers; validate body names.

    Returns:
      JSON array: { name, parent?, has_atmosphere, radius_m, soi_radius_m }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.list_bodies(conn))


@mcp.tool()
def set_target_body(address: str, body_name: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Set the active vessel's target body (also tries SpaceCenter.target_body).

    Args:
      body_name: Exact body name (e.g., 'Mun')

    Returns:
      Human‑readable status string or an error if not found.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    sc = conn.space_center
    v = sc.active_vessel
    try:
        b = sc.bodies.get(body_name)
        if b is None:
            return f"Body '{body_name}' not found."
        # Set both vessel- and spacecenter-level targets when available
        try:
            v.target_body = b
        except Exception:
            pass
        try:
            setattr(sc, 'target_body', b)
        except Exception:
            pass
        return f"Target body set to {getattr(b, 'name', body_name)}."
    except Exception as e:
        return f"Failed to set target body: {e}"


@mcp.tool()
def list_vessels(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    List vessels in the current save with type/situation and optional distance.

    Returns:
      JSON array: { name, type?, situation?, distance_m? }.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.list_vessels(conn))


@mcp.tool()
def set_target_vessel(address: str, vessel_name: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Set the active vessel's target vessel by name (case‑insensitive). Chooses nearest if multiple.
    Also attempts to set SpaceCenter.target_vessel.

    Args:
      vessel_name: Exact or case‑insensitive vessel name

    Returns:
      Human‑readable status string or error if not found.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    sc = conn.space_center
    v = sc.active_vessel
    try:
        candidates = [ov for ov in sc.vessels if ov.name == vessel_name]
        if not candidates:
            # Case-insensitive match
            candidates = [ov for ov in sc.vessels if ov.name.lower() == vessel_name.lower()]
        if not candidates:
            return f"Vessel '{vessel_name}' not found."
        # Prefer nearest if multiple
        cb = v.orbit.body
        ref = getattr(cb, 'non_rotating_reference_frame', cb.reference_frame)
        vp = v.position(ref)
        target = sorted(candidates, key=lambda ov: sum((ov.position(ref)[i]-vp[i])**2 for i in range(3)) if ov.id != v.id else 0)[0]
        # Set both vessel- and spacecenter-level targets when available
        try:
            v.target_vessel = target
        except Exception:
            pass
        try:
            setattr(sc, 'target_vessel', target)
        except Exception:
            pass
        return f"Target vessel set to {target.name}."
    except Exception as e:
        return f"Failed to set target vessel: {e}"


@mcp.tool()
def clear_target(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Clear target_docking_port, target_vessel, and target_body if set.

    Returns:
      Human‑readable status string: 'Cleared target.' or 'No target to clear.'
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    v = conn.space_center.active_vessel
    cleared = 0
    try:
        v.target_docking_port = None
        cleared += 1
    except Exception:
        pass
    try:
        v.target_vessel = None
        cleared += 1
    except Exception:
        pass
    try:
        v.target_body = None
        cleared += 1
    except Exception:
        pass
    return "Cleared target." if cleared else "No target to clear."


# --- Vessel blueprint tools ---

@mcp.tool()
def get_part_tree(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Hierarchical part tree with staging and module/resource summaries.

    Returns:
      JSON: { parts: [ { id, title, name, tag?, stage, decouple_stage?, parent_id?, children_ids[],
              modules: [...], resources: {R:{amount,max}}, crossfeed? } ] }
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.part_tree(conn))


@mcp.tool()
def get_vessel_blueprint(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Idealized vessel blueprint combining meta, stage plan, engines, control capabilities, and part tree.

    When to use:
      - Give the agent a structural understanding of the craft before writing scripts.

    Returns:
      JSON with sections: meta, stages, engines, control_capabilities, parts, geometry, notes.
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    bp = readers.vessel_blueprint(conn)
    try:
        # Cache for blueprint resource
        from ..blueprint_cache import set_latest_blueprint
        set_latest_blueprint(bp)
    except Exception:
        pass
    return json.dumps(bp)


@mcp.tool()
def get_blueprint_ascii(address: str, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Compact ASCII schematic/summary of the current vessel by stage.

    Includes a header and a per-stage table with engine counts, Δv, TWR,
    and key part category counts (Eng/Tank/Dec/Par/Dock).
    """
    conn = _connect(address, rpc_port, stream_port, name, timeout)
    try:
        s = readers.blueprint_ascii(conn)
        return s
    except Exception as e:
        return f"Failed to build ASCII blueprint: {e}"
