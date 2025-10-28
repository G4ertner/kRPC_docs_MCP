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
    "8) Verify orbit; delete nodes when done\n"
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
)


@mcp.resource("resource://playbooks/vessel-blueprint-usage")
def get_blueprint_usage_playbook() -> str:
    return BLUEPRINT_USAGE
