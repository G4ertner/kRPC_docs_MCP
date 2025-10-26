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

