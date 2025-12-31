from __future__ import annotations

from pathlib import Path

from .mcp_context import mcp

_PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks"


def _read(name: str) -> str:
    path = _PLAYBOOK_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else "(playbook not found)"


@mcp.resource("resource://playbooks/maneuver-node")
def get_maneuver_node_playbook() -> str:
    return _read("maneuver-node")


@mcp.resource("resource://playbooks/vessel-blueprint-usage")
def get_blueprint_usage_playbook() -> str:
    return _read("vessel-blueprint-usage")


@mcp.resource("resource://playbooks/flight-control")
def get_flight_control_playbook() -> str:
    return _read("flight-control")


@mcp.resource("resource://playbooks/rendezvous-docking")
def get_rendezvous_playbook() -> str:
    return _read("rendezvous-docking")


@mcp.resource("resource://playbooks/launch-ascent-circularize")
def get_launch_ascent_circ_playbook() -> str:
    return _read("launch-ascent-circularize")


@mcp.resource("resource://playbooks/state-checkpoint-rollback")
def get_state_checkpoint_playbook() -> str:
    return _read("state-checkpoint-rollback")


@mcp.resource("resource://playbooks/orbital-return-playbook")
def get_orbital_return_playbook() -> str:
    return _read("orbital-return-playbook")


@mcp.resource("resource://playbooks/warping-playbook")
def get_warping_playbook() -> str:
    return _read("warping-playbook")
