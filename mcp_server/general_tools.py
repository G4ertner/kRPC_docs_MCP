from __future__ import annotations

from .mcp_context import mcp
from .utils.krpc_helpers import DEFAULT_KRPC_ADDRESS
from .general_tools_impl import (
    aerodynamics_and_engines,
    blueprints,
    blueprints_parts_and_staging,
    bodies_and_waypoints,
    connection_and_save,
    diagnostics,
    docking,
    environment_and_surface,
    flight_and_control,
    launch_and_vessel,
    maneuver_nodes,
    orbit_and_navigation,
    planning_helpers,
    power_and_resources,
    screenshots,
    status_and_time,
    target_control,
)


# 🔌 Connection test🔌 ---------------------------------------------------------------------
@mcp.tool()
def krpc_get_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Connect to a running kRPC server and return its version (and active vessel if available).

When to use:
    - Quick connectivity check and basic context before calling other tools.

Args:
    address: LAN IP or hostname of the KSP PC
    rpc_port: RPC port (default 50000)
    stream_port: Stream port (default 50001)
    name: Optional connection name shown in kRPC UI
    timeout: Connection timeout in seconds
Returns:
    A short status string, or an error message if connection fails."""
    return connection_and_save.krpc_get_status(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 🛰️⏱️ Status & time 🛰️⏱️ ---------------------------------------------------------------------


@mcp.tool()
def get_status_overview(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Combined snapshot of core vessel/game status in a single call.

When to use:
  - Summarize state for planning, logging, or sanity checks.

Returns:
  JSON: { vessel, environment, flight, orbit, time, attitude, aero, maneuver_nodes }."""
    return status_and_time.get_status_overview(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_vessel_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Basic vessel info for the active craft.

When to use:
  - High-level status summaries and sanity checks prior to planning.

Args:
  address: LAN IP/hostname of the KSP PC
  rpc_port: kRPC RPC port (default 50000)
  stream_port: kRPC stream port (default 50001)
  name: Optional connection name shown in kRPC UI
  timeout: Connection timeout in seconds

Returns:
  JSON string: { name, mass_kg, throttle, situation }"""
    return status_and_time.get_vessel_info(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_time_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Time context for the current save.

When to use:
  - Scheduling burns, warp decisions, or synchronizing UT across tools.

Returns:
  JSON: { universal_time_s, mission_time_s, timewarp_rate?, timewarp_mode? }."""
    return status_and_time.get_time_status(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 🌍🧭 Environment & surface 🌍🧭 ---------------------------------------------------------------------


@mcp.tool()
def get_environment_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Environment info for the current body and situation.

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
  temperature_k?, atmosphere, atmosphere_depth_m }."""
    return environment_and_surface.get_environment_info(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_surface_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Surface context at current location: latitude/longitude, surface altitude, terrain height,
estimated ground slope, and ground speed.

Returns:
  JSON: { latitude_deg, longitude_deg, surface_altitude_m, terrain_height_m,
  slope_deg, ground_speed_m_s, body }."""
    return environment_and_surface.get_surface_info(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# ✈️🎮 Flight & control ✈️🎮 ---------------------------------------------------------------------


@mcp.tool()
def get_flight_snapshot(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Flight snapshot for the active vessel.

When to use:
  - Real-time monitoring, ascent/descent guidance, atmosphere checks.

Returns:
  JSON: { altitude_sea_level_m, altitude_terrain_m, vertical_speed_m_s,
  speed_surface_m_s, speed_horizontal_m_s, dynamic_pressure_pa, mach,
  g_force, angle_of_attack_deg, pitch_deg, roll_deg, heading_deg }."""
    return flight_and_control.get_flight_snapshot(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_attitude_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Attitude/control state for the active vessel.

    When to use:
      - Verify SAS/RCS/throttle state and autopilot targets before burns.
      - Pair with set_sas_mode to adjust navball hold behaviors.

    Returns:
    JSON: { sas, sas_mode, rcs, throttle, autopilot_state, autopilot_target_pitch,
    autopilot_target_heading, autopilot_target_roll, speed_mode? }."""
    return flight_and_control.get_attitude_status(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_action_groups_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Action group toggles.

When to use:
  - Verify control safety and configuration pre‑burn or pre‑entry.

Returns:
  JSON: { sas, rcs, lights, gear, brakes, abort, custom_1..custom_10 }."""
    return flight_and_control.get_action_groups_status(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_camera_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Active camera parameters when available: mode, pitch, heading, distance, and limits.

    Returns:
      JSON: { available, mode?, pitch_deg?, heading_deg?, distance_m?,
      min_pitch_deg?, max_pitch_deg?, min_distance_m?, max_distance_m? }."""
    return flight_and_control.get_camera_status(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def get_screenshot(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, *, scale: int = 1) -> str:
    """Capture a PNG screenshot of the current scene and return it as base64 along with file metadata.

    Notes:
      - Requires the MCP server and KSP to run on the same PC (localhost/127.0.0.1/::1) so the saved file is accessible.
      - Filenames are unique per call (safe to call in fast loops).
      - LLM: To view the screenshot, use the returned `resource_uri` (resource://screenshots/<filename>) or `resource://screenshots/latest`.
        The file is also saved on disk at `saved_path` (usually `artifacts/screenshots/<filename>`).

    Args:
      scale: Resolution scaling factor forwarded to SpaceCenter.screenshot (1-4).

    Returns:
  JSON: { ok, filename, saved_path, resource_uri, scale, captured_at, image: { mime, data_base64 } } or { error }."""
    return screenshots.get_screenshot(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout, scale=scale)


# 🌬️🚀 Aerodynamics & engines 🌬️🚀 ---------------------------------------------------------------------


@mcp.tool()
def get_aero_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Aerodynamic state.

When to use:
  - Ascent/descent control, max-Q checks, aero stress monitoring.

Returns:
  JSON: { dynamic_pressure_pa, mach, atmosphere_density_kg_m3, drag?, lift? }."""
    return aerodynamics_and_engines.get_aero_status(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_engine_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Per-engine status for the active vessel.

When to use:
  - Engine diagnostics before/after burns, checking flameouts or throttling.

Returns:
  JSON array of engines with: { part, active, has_fuel, flameout, thrust_n,
  max_thrust_n, specific_impulse_s, throttle }."""
    return aerodynamics_and_engines.get_engine_status(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 🔋⛽ Power & resources 🔋⛽ ---------------------------------------------------------------------


mcp.tool()
def get_power_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """ElectricCharge summary with generator/consumer counts and best‑effort estimates.

When to use:
  - Power budgeting, troubleshooting brown‑outs, and mission readiness checks.

Returns:
  JSON: { vessel_totals: { amount, max }, production: { solar?, rtg?, fuel_cells? },
  consumers: { wheels?, antennas?, lights? }, notes?: [..] }."""
    return power_and_resources.get_power_status(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_resource_breakdown(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Aggregate resource totals for the whole vessel and the current stage.

When to use:
  - Fuel/electricity accounting, staging decisions, consumables monitoring.

Returns:
  JSON: { vessel_totals: {Resource: {amount, max}}, stage_totals: {…}, current_stage }."""
    return power_and_resources.get_resource_breakdown(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 📐🧩🪜 Blueprints, parts & staging 📐🧩🪜 ---------------------------------------------------------------------


@mcp.tool()
def get_part_tree(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Hierarchical part tree with staging and module/resource summaries.

Note:
  This synchronous call can exceed the CLI's 60 s limit on large vessels.
  Prefer start_part_tree_job -> get_job_status(job_id) -> read_resource(result_resource)
  when you need a full tree safely; fall back to this direct call only for quick checks.

Returns:
  JSON: { parts: [ { id, title, name, tag?, stage, decouple_stage?, parent_id?, children_ids[],
          modules: [...], resources: {R:{amount,max}}, crossfeed? } ] }"""
    return blueprints_parts_and_staging.get_part_tree(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_vessel_blueprint(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Idealized vessel blueprint combining meta, stage plan, engines, control capabilities, and part tree.

When to use:
  - Give the agent a structural understanding of the craft before writing scripts.

Returns:
  JSON with sections: meta, stages, engines, control_capabilities, parts, geometry, notes."""
    return blueprints_parts_and_staging.get_vessel_blueprint(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_blueprint_ascii(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Compact ASCII schematic/summary of the current vessel by stage.

Includes a header and a per-stage table with engine counts, Δv, TWR,
and key part category counts (Eng/Tank/Dec/Par/Dock)."""
    return blueprints_parts_and_staging.get_blueprint_ascii(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def get_stage_plan(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, environment: str = 'current') -> str:
    """Approximate stock‑like staging plan by grouping decouple‑only stages under the
preceding engine stage.

Note:
  For big rockets this direct call can exceed the 60 s CLI limit. Prefer
  start_stage_plan_job -> get_job_status(job_id) -> read_resource(result_resource)
  to fetch the JSON artifact safely, and reserve this helper for quick snapshots.
  For interpretation tips, see resource://playbooks/vessel-blueprint-usage and
  resource://playbooks/launch-ascent-circularize.

When to use:
  - Match KSP’s staging view for Δv/TWR per engine stage.

Args:
  environment: 'current' | 'sea_level' | 'vacuum' — controls Isp used

Returns:
  JSON: { stages: [ { stage, engines, max_thrust_n, combined_isp_s?, prop_mass_kg,
  m0_kg, m1_kg, delta_v_m_s?, twr_surface? } ] }."""
    return blueprints_parts_and_staging.get_stage_plan(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout, environment=environment)

@mcp.tool()
def get_staging_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Approximate per-stage delta‑v and TWR plan using current engine Isp and resource masses.

When to use:
  - Quick staging analysis for mission planning and sanity checks.

Returns:
  JSON: { current_stage, stages: [ { stage, engines, max_thrust_n,
  combined_isp_s?, delta_v_m_s?, twr_surface?, prop_mass_kg, m0_kg, m1_kg } ] }.

Note: Uses standard KSP resource densities and current environment Isp; results are estimates.
  For interpretation tips, see resource://playbooks/vessel-blueprint-usage and
  resource://playbooks/launch-ascent-circularize."""
    return blueprints_parts_and_staging.get_staging_info(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 🪐📡 Orbit & navigation 🪐📡 ---------------------------------------------------------------------


@mcp.tool()
def get_orbit_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Orbital elements for the active vessel.

When to use:
  - Planning nodes, verifying orbit changes, or summarizing current orbit.

Returns:
  JSON: { body, apoapsis_altitude_m, time_to_apoapsis_s, periapsis_altitude_m,
  time_to_periapsis_s, eccentricity, inclination_deg, lan_deg,
  argument_of_periapsis_deg, semi_major_axis_m, period_s }."""
    return orbit_and_navigation.get_orbit_info(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def get_navigation_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Coarse navigation info to the current target (body or vessel).

When to use:
  - Pre‑planning checks for plane changes, phasing, and transfers.

Returns:
  If body target: { target_type: 'body', name, target_sma_m, target_period_s,
  target_inclination_deg, target_lan_deg, phase_angle_deg? }.
  If vessel target: { target_type: 'vessel', name, distance_m?, relative_speed_m_s?,
  relative_inclination_deg?, phase_angle_deg? }."""
    return orbit_and_navigation.get_navigation_info(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def get_targeting_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Current target summary across vessel/body/docking targets with relative geometry when available.

Returns:
  JSON: { target_type: 'vessel'|'body'|'docking_port'|None, target_name, target_vessel?,
  distance_m?, relative_speed_m_s? }."""
    return orbit_and_navigation.get_targeting_info(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)



# 🌌📍 Bodies & waypoints 🌌📍 ---------------------------------------------------------------------


@mcp.tool()
def list_bodies(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """List celestial bodies known to kRPC with key metadata.

When to use:
  - Pick targets for transfers; validate body names.

Returns:
  JSON array: { name, parent?, has_atmosphere, radius_m, soi_radius_m }."""
    return bodies_and_waypoints.list_bodies(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def list_waypoints(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Waypoints known to the waypoint manager, with vessel-relative range/bearing where possible.

Returns:
  JSON array: { name, body, latitude_deg, longitude_deg, altitude_m,
  distance_m?, bearing_deg? }."""
    return bodies_and_waypoints.list_waypoints(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 🚀🛠️ Launch & vessels 🚀🛠️ ---------------------------------------------------------------------


@mcp.tool()
def list_launch_sites(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """List available launch sites (e.g., "LaunchPad", "Runway")."""
    return launch_and_vessel.list_launch_sites(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def list_launchable_vessels(address: str = DEFAULT_KRPC_ADDRESS, craft_directory: str = 'VAB', rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """List the names of craft files that can be launched from the specified directory ("VAB" or "SPH")."""
    return launch_and_vessel.list_launchable_vessels(address=address, craft_directory=craft_directory, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)




@mcp.tool()
def list_vessels(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """List vessels in the current save with type/situation and optional distance.

Returns:
  JSON array: { name, type?, situation?, distance_m? }."""
    return launch_and_vessel.list_vessels(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 🧭🧮 Maneuver nodes 🧭🧮 ---------------------------------------------------------------------


@mcp.tool()
def list_maneuver_nodes(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """List basic maneuver nodes.

When to use:
  - Quick overview of planned burns with timing and total delta‑v.

Returns:
  JSON array: { ut, time_to_node_s, delta_v_m_s }."""
    return maneuver_nodes.list_maneuver_nodes(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def list_maneuver_nodes_detailed(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Detailed maneuver nodes for the active vessel including vector and simple burn-time estimate.

Returns:
  JSON array: { ut, time_to_node_s, delta_v_vector_m_s, delta_v_total_m_s,
  burn_time_simple_s? }."""
    return maneuver_nodes.list_maneuver_nodes_detailed(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)





# 📝🧠 Planning helpers 📝🧠 ---------------------------------------------------------------------


@mcp.tool()
def compute_burn_time(address: str = DEFAULT_KRPC_ADDRESS, dv_m_s: float | None = None, environment: str = 'current', rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Estimate burn time for a given delta-v using current (or specified) thrust and Isp.

When to use:
  - Size burns for warp lead time, node placement, or staging checks.

Args:
  dv_m_s: Desired delta-v in m/s
  environment: 'current' | 'sea_level' | 'vacuum' — controls Isp estimate

Returns:
  JSON with mass, thrust, Isp, burn_time_simple_s and burn_time_tsiolkovsky_s."""
    return planning_helpers.compute_burn_time(address=address, dv_m_s=dv_m_s, environment=environment, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def compute_circularize_node(address: str = DEFAULT_KRPC_ADDRESS, at: str = 'apoapsis', rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Propose a circularization node at Ap or Pe.

When to use:
  - Circularize after insertion or cleanup of eccentric orbits.

Args:
  at: 'apoapsis' | 'periapsis'

Returns:
  Proposal: { ut, prograde, normal=0, radial=0, v_now_m_s, v_circ_m_s }."""
    return planning_helpers.compute_circularize_node(address=address, at=at, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def compute_plane_change_nodes(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Propose plane change burns at next AN/DN relative to target (vessel/body).

When to use:
  - Align inclinations before rendezvous or transfers.

Returns UT and normal delta-v suggestions for AN and DN when available."""
    return planning_helpers.compute_plane_change_nodes(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def compute_raise_lower_node(address: str = DEFAULT_KRPC_ADDRESS, kind: str | None = None, target_alt_m: float | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Propose a single‑burn node to raise/lower apoapsis or periapsis to target_alt_m.

Args:
  kind: 'apoapsis' | 'periapsis'
  target_alt_m: Desired altitude above sea level in meters

Returns:
  Proposal: { ut, prograde, normal=0, radial=0, v_now_m_s, v_target_m_s }."""
    return planning_helpers.compute_raise_lower_node(address=address, kind=kind, target_alt_m=target_alt_m, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def compute_rendezvous_phase_node(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Suggest a phasing orbit to rendezvous with the current target vessel in the same SOI.

When to use:
  - Align orbital periods to time an intercept with a target vessel.

Returns:
  Proposal at next Pe: { ut, prograde, normal=0, radial=0, P_phase_s, m, T_align_s }."""
    return planning_helpers.compute_rendezvous_phase_node(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def compute_transfer_window_to_body(address: str = DEFAULT_KRPC_ADDRESS, body_name: str | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Compute a Hohmann transfer window to a target body (moon or interplanetary).

When to use:
  - Time interplanetary or moon transfers from current body context.

Returns phase_now/required/error, time_to_window_s, ut_window, and transfer time.
Robust fallbacks infer the star/common parent when parent references are missing."""
    return planning_helpers.compute_transfer_window_to_body(address=address, body_name=body_name, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def compute_ejection_node_to_body(address: str = DEFAULT_KRPC_ADDRESS, body_name: str | None = None, parking_alt_m: float | None = None, environment: str = 'current', rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Coarse ejection burn estimate for an interplanetary transfer to the target body.

When to use:
  - After computing a transfer window, to place the ejection burn.

Args:
  body_name: Target planet
  parking_alt_m: Circular parking orbit altitude (m) around current body
  environment: Isp environment for burn-time followups ('current'|'sea_level'|'vacuum')

Returns:
  Proposal at UT window: { ut, prograde, normal=0, radial=0, v_inf_m_s, time_to_window_s }."""
    return planning_helpers.compute_ejection_node_to_body(address=address, body_name=body_name, parking_alt_m=parking_alt_m, environment=environment, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 🧲🛰️ Docking 🧲🛰️ ---------------------------------------------------------------------


@mcp.tool()
def list_docking_ports(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """List docking ports on the active vessel and their states.

Returns:
  JSON array: { part, state, ready, dockee }."""
    return docking.list_docking_ports(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


# 🩺🔧 Diagnostics 🩺🔧 ---------------------------------------------------------------------


@mcp.tool()
def get_diagnostics(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Collect a richer diagnostics snapshot to aid post-mortems.

Returns JSON with: vessel, time, environment, flight, orbit, attitude,
aero, engines, resources, maneuver_nodes, and surface."""
    return diagnostics.get_diagnostics(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)



# 📸 Screenshots 📸 ---------------------------------------------------------------------
@mcp.resource("resource://screenshots/latest")
def resource_get_latest_screenshot():
    return screenshots.get_latest_cached()


@mcp.resource("resource://screenshots/{filename}")
def resource_get_screenshot_file(filename: str):
    return screenshots.resource_payload_for(filename)


# 🖼️📤 Blueprints 🖼️📤 ---------------------------------------------------------------------


@mcp.tool()
def export_blueprint_diagram(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, *, format: str = 'svg', out_dir: str | None = None) -> str:
    """Export a 2D vessel blueprint diagram (SVG/PNG) and expose it as a resource.

    Notes:
      - Saves the diagram under artifacts/blueprints and returns a resource URI so the LLM can fetch/view it.
      - Use format 'svg' (default) or 'png'; png requires Pillow installed.
      - After calling, load the returned resource URI (or resource://blueprints/last-diagram.svg|.png) via read_resource/view_image to see the image in chat.

    Args:
      format: 'svg' or 'png'
      out_dir: Optional output directory; defaults to artifacts/blueprints
    """
    return blueprints.export_blueprint_diagram(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, format=format, out_dir=out_dir)

@mcp.resource("resource://staging/latest")
def resource_get_latest_staging():
    return blueprints.get_latest_staging()


@mcp.resource("resource://vessel-blueprint/latest")
def resource_get_latest_vessel_blueprint():
    return blueprints.get_latest_vessel_blueprint()


@mcp.resource("resource://blueprints/last-diagram.svg")
def resource_get_last_svg():
    return blueprints.get_last_svg()


@mcp.resource("resource://blueprints/last-diagram.png")
def resource_get_last_png():
    return blueprints.get_last_png()


@mcp.resource("resource://blueprints/{filename}")
def resource_get_blueprint_file(filename: str):
    return blueprints.resource_payload_for(filename)
