from __future__ import annotations

from .server import mcp


PLAYBOOK_TEXT = (
    "Maneuver Node Playbook\n\n"
    "1) Read status: get_status_overview (orbit, time, mass), get_stage_plan(env)\n"
    "2) Navigation: get_navigation_info (phase angle, AN/DN)\n"
    "3) Choose goal: circularize | plane change | raise/lower Ap/Pe | transfer\n"
    "4) Plan: use compute_* helper (burn time, UT anchor, pro/normal/radial)\n"
    "5) Set: set_maneuver_node(ut, prograde, normal, radial)\n"
    "6) Optional: warp_to(ut - burn_time/2)\n"
    "7) Execute burn (Python execution pipeline)\n"
    "8) Verify orbit; delete nodes when done\n\n"
    "Snippets usage:\n"
    "- Before scripting, search example code: snippets_search({\"query\": \"circularize orbit\", \"k\": 5, \"mode\": \"hybrid\", \"rerank\": true})\n"
    "- Inspect an item with snippets_get(id, include_code=false); resolve into paste-ready code with snippets_resolve({\"id\": \"<id>\"})\n"
    "- Filter by category (function/class/method) or use exclude_restricted=true for license policy compliance.\n"
)


@mcp.resource("resource://playbooks/maneuver-node")
def get_maneuver_node_playbook() -> str:
    return PLAYBOOK_TEXT


BLUEPRINT_USAGE = (
    "Vessel Blueprint Usage\n\n"
    "Purpose: Provide the agent with a structural understanding of the current vessel to plan safe, effective scripts.\n\n"
    "Recommended Calls:\n"
    "- get_status_overview — confirm scene, body, situation\n"
    "- get_vessel_blueprint — meta, stages (dv/TWR), engines, parts\n"
    "- get_blueprint_ascii — quick human-readable summary (by stage)\n\n"
    "Key Fields:\n"
    "- meta.current_stage — current stage index\n"
    "- stages[] — per-engine-stage Δv/TWR (approximate)\n"
    "- parts[].stage / parts[].decouple_stage — staging order and drop points\n"
    "- engines[] — engine locations (part_id), thrust/Isp\n\n"
    "Checklist Before Staging/Burn:\n"
    "1) Confirm next stage has engines and sufficient propellant (parts with LiquidFuel/Oxidizer/MonoPropellant/SolidFuel).\n"
    "2) Verify TWR > 1 if performing a surface/ascent burn.\n"
    "3) Ensure control capabilities: SAS/Reaction Wheels, RCS if required.\n"
    "4) After staging, refresh blueprint to update structure and dv/TWR.\n\n"
    "Notes:\n"
    "- Stage plan is an approximation; values differ from KSP UI. Use as planning guidance.\n"
    "- Geometry is best-effort; thrust axis and CoM may be unavailable.\n"
    "\nSnippets usage:\n"
    "- For common control patterns (staging, throttle guards, SAS modes), search examples: snippets_search({\"query\": \"throttle stage SAS\", \"k\": 5, \"mode\": \"hybrid\"})\n"
    "- Resolve a minimal helper (function/class) with snippets_resolve and adapt to current vessel blueprint constraints.\n"
)


@mcp.resource("resource://playbooks/vessel-blueprint-usage")
def get_blueprint_usage_playbook() -> str:
    return BLUEPRINT_USAGE


# Additional playbooks

FLIGHT_CONTROL_PLAYBOOK = (
    "Flight Control Playbook\n\n"
    "1) Establish control state: get_status_overview; confirm SAS/RCS/throttle\n"
    "2) Safety checks: staging readiness, propellant availability, engine status\n"
    "3) Attitude plan: target pitch/heading/roll or point to node/target\n"
    "4) Throttle plan: TWR targets or specific acceleration profiles\n"
    "5) Execute control loop (bounded, telemetry-driven); log state\n"
    "6) Evaluate metrics; adapt or exit with SUMMARY\n\n"
    "Snippets usage:\n"
    "- Search common loops (PID hover, ascent control, pitch program): snippets_search({\"query\": \"ascent autopilot PID\", \"k\": 10, \"mode\": \"hybrid\", \"rerank\": true})\n"
    "- Inspect with snippets_get; resolve focused helpers with snippets_resolve to avoid bloat.\n"
    "- Filter by category=\"function\" or exclude_restricted=true per policy.\n"
)


@mcp.resource("resource://playbooks/flight-control")
def get_flight_control_playbook() -> str:
    return FLIGHT_CONTROL_PLAYBOOK


RENDEZVOUS_PLAYBOOK = (
    "Rendezvous & Docking Playbook\n\n"
    "1) Align planes: compute_plane_change_nodes; plan burn at AN/DN\n"
    "2) Phase for intercept: compute_rendezvous_phase_node; set transfer\n"
    "3) Execute intercept burns; monitor relative speed and distance\n"
    "4) Approach & docking: reduce closing speed; align ports; finalize\n\n"
    "Snippets usage:\n"
    "- Search rendezvous helpers: snippets_search({\"query\": \"rendezvous docking approach\", \"k\": 10, \"mode\": \"hybrid\"})\n"
    "- Resolve utilities for vector math/approach throttling; prefer minimal functions.\n"
    "- Use exclude_restricted=true when license policy requires.\n"
)


@mcp.resource("resource://playbooks/rendezvous-docking")
def get_rendezvous_playbook() -> str:
    return RENDEZVOUS_PLAYBOOK
