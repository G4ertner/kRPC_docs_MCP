from __future__ import annotations

from .server import mcp


PLAYBOOK_TEXT = '''
Maneuver Node Playbook

1) Read status
- get_status_overview (orbit, time, mass), get_stage_plan(env)

2) Navigation
- get_navigation_info (phase angle, AN/DN)

3) Choose goal
- circularize | plane change | raise/lower Ap/Pe | transfer

4) Plan
- Use compute_* helper (burn time, UT anchor, pro/normal/radial)

5) Set and (optionally) warp
- set_maneuver_node(ut, prograde, normal, radial)
- warp_to(ut - burn_time/2)

6) Execute burn (script)
- Point to node vector, throttle to target Δv, feather as Δv approaches 0

Reusable code — execute_next_node (MIT; krpc/krpc-library):
```
def execute_next_node(conn):
    space_center = conn.space_center
    vessel = space_center.active_vessel
    ap = vessel.auto_pilot
    try:
        node = vessel.control.nodes[0]
    except Exception:
        return
    rf = vessel.orbit.body.reference_frame
    ap.reference_frame = rf
    ap.engage()
    ap.target_direction = node.remaining_burn_vector(rf)
    ap.wait()
    m = vessel.mass; isp = vessel.specific_impulse; dv = node.delta_v
    F = vessel.available_thrust; G = 9.81
    burn_time = (m - (m / math.exp(dv / (isp * G)))) / (F / (isp * G))
    space_center.warp_to(node.ut - (burn_time / 2.0) - 5.0)
    while node.time_to > (burn_time / 2.0):
        pass
    ap.wait()
    vessel.control.throttle = thrust_controller(vessel, node.remaining_delta_v)
    while node.remaining_delta_v > 0.1:
        ap.target_direction = node.remaining_burn_vector(rf)
        vessel.control.throttle = thrust_controller(vessel, node.remaining_delta_v)
    ap.disengage(); vessel.control.throttle = 0.0; node.remove()
```

7) Verify orbit; delete any residual nodes

Snippets usage
- Search: snippets_search({"query": "circularize orbit", "k": 5, "mode": "hybrid", "rerank": true})
- Inspect: snippets_get(id, include_code=false); Resolve: snippets_resolve({"id": "<id>"})
- Filter by category (function/class/method) or use exclude_restricted=true per policy.
'''


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

FLIGHT_CONTROL_PLAYBOOK = '''
Flight Control Playbook

1) Establish control state
- get_status_overview; confirm SAS/RCS/throttle

2) Safety checks
- staging readiness, propellant availability, engine status

3) Attitude plan
- target pitch/heading/roll or point to node/target

4) Throttle plan
- TWR targets or specific acceleration profiles; constrain dynamic pressure (max‑Q)

Reusable code — gravity turn pitch program (MIT; krpc/krpc-library):
```
def gravturn(conn, launch_params):
    vessel = conn.space_center.active_vessel
    flight = vessel.flight(vessel.orbit.body.non_rotating_reference_frame)
    progress = flight.mean_altitude / launch_params.grav_turn_finish
    vessel.auto_pilot.target_pitch = 90 - (-90 * progress * (progress - 2))
```

Reusable code — boost apoapsis with gentle throttle (MIT):
```
def boostAPA(conn, launch_params):
    vessel = conn.space_center.active_vessel
    vessel.control.throttle = 0.2
    while vessel.orbit.apoapsis_altitude < launch_params.orbit_alt:
        # optional: staging checks, telemetry logs
        pass
    vessel.control.throttle = 0.0
```

5) Execute control loop (bounded, telemetry-driven); log state
6) Evaluate metrics; adapt or exit with SUMMARY

Snippets usage
- Search (PID hover, ascent control, pitch program): snippets_search({"query": "ascent autopilot PID", "k": 10, "mode": "hybrid", "rerank": true})
- Inspect with snippets_get; resolve focused helpers with snippets_resolve to avoid bloat.
- Filter by category="function" or exclude_restricted=true per policy.
'''


@mcp.resource("resource://playbooks/flight-control")
def get_flight_control_playbook() -> str:
    return FLIGHT_CONTROL_PLAYBOOK


RENDEZVOUS_PLAYBOOK = '''
Rendezvous & Docking Playbook

1) Align planes
- compute_plane_change_nodes; plan burn at AN/DN (execute node)

Reusable code — plane match + execute (MIT):
```
def match_planes(conn):
    sc = conn.space_center; v = sc.active_vessel; t = sc.target_vessel
    if v.orbit.relative_inclination(t) < 0.00436:
        return
    ut_an = v.orbit.ut_at_true_anomaly(v.orbit.true_anomaly_an(t))
    ut_dn = v.orbit.ut_at_true_anomaly(v.orbit.true_anomaly_dn(t))
    time = ut_an if ut_an < ut_dn else ut_dn
    sp = v.orbit.orbital_speed_at(time); inc = v.orbit.relative_inclination(t)
    normal = sp * math.sin(inc); prograde = sp * math.cos(inc) - sp
    if ut_an < ut_dn: normal *= -1
    v.control.add_node(time, normal=normal, prograde=prograde)
    execute_next_node(conn)
```

2) Phase for intercept
- compute_rendezvous_phase_node; set transfer (or use Hohmann transfer helper)

Reusable code — Hohmann transfer (MIT):
```
def hohmann_transfer(vessel, target, time):
    body = vessel.orbit.body; GM = body.gravitational_parameter
    r1 = vessel.orbit.radius_at(time); SMA_i = vessel.orbit.semi_major_axis
    SMA_t = (vessel.orbit.apoapsis + target.orbit.apoapsis) / 2
    v1 = math.sqrt(GM * ((2/r1) - (1 / SMA_i)))
    v2 = math.sqrt(GM * ((2/r1) - (1 / SMA_t)))
    dv = v2 - v1
    return vessel.control.add_node(time, prograde=dv)
```

3) Execute intercept burns; monitor relative speed/distance
4) Approach & docking
- reduce closing speed; align ports; finalize

Snippets usage
- Search rendezvous helpers: snippets_search({"query": "rendezvous docking approach", "k": 10, "mode": "hybrid"})
- Resolve utilities for vector math/approach throttling; prefer minimal functions.
- Use exclude_restricted=true when license policy requires.
'''


@mcp.resource("resource://playbooks/rendezvous-docking")
def get_rendezvous_playbook() -> str:
    return RENDEZVOUS_PLAYBOOK


LAUNCH_ASCENT_CIRC_PLAYBOOK = '''
Launch, Ascent, Circularize Playbook

Purpose: Safely launch to space, perform a gravity turn, and circularize at apoapsis into a stable LKO.

0) Preconditions & Safety
- On pad or low-altitude flight; confirm kRPC connectivity (krpc_get_status).
- Snapshot: get_status_overview; export_blueprint_diagram to visualize stages.
- Verify: engine status, propellant, staging order, SAS/RCS states, throttle=0.
- Targets: orbit altitude (e.g., 80–100 km), acceptable max-Q (dynamic_pressure_pa).

1) Situation & Blueprint
- get_status_overview — gather vessel/environment/flight/orbit/time/aero.
- export_blueprint_diagram(address, format='svg') — quick stage dv/TWR overview.
- Optional: get_engine_status, get_resource_breakdown.

2) Plan Gravity Turn
- Typical start: 2–3 km or 120–150 m/s; end: ~45–65 km.
- Manage throttle to keep TWR ~1.3–1.8 and avoid max‑Q spikes.
- Reference: search_ksp_wiki("Gravity turn") for background.
- Snippets usage:
  • snippets_search({"query": "ascent gravity turn", "k": 10, "mode": "hybrid", "rerank": true})
  • Resolve helpers (functions/classes) via snippets_resolve to bootstrap the script.

Reusable code — gravity turn (MIT; from krpc/krpc-library Art_Whaleys_KRPC_Demos):
```
def gravturn(conn, launch_params):
    """
    Execute quadratic gravity turn — based on Robert Penner's easing equations (EaseOut)
    """
    vessel = conn.space_center.active_vessel
    flight = vessel.flight(vessel.orbit.body.non_rotating_reference_frame)
    progress = flight.mean_altitude / launch_params.grav_turn_finish
    vessel.auto_pilot.target_pitch = 90 - (-90 * progress * (progress - 2))
```

3) Execute Launch + Ascent (script)
- Sequence outline (adapt to blueprint & snippets):
  1. Throttle to 100%; stage clamps; stage booster/first engines.
  2. Vertical climb until 120–150 m/s OR 2–3 km.
  3. Begin pitch program: gradually pitch from 90° toward horizon; at 35 km+, switch to orbital reference for target_direction=(0,1,0) (prograde).
  4. Throttle to maintain target TWR or Δv schedule; stage as needed.
  5. Aim for apoapsis altitude target (e.g., 80–100 km). Cut throttle at AP target.
- Monitoring: dynamic_pressure_pa (limit max‑Q), g_force, pitch/heading, apoapsis_altitude_m.
- Use bounded loops with timeouts and logs; add SUMMARY at end.

Reusable code — circularize maneuver planning (MIT; krpc/krpc-library):
```
def planCirc(conn):
    """
    Plan a circularization at apoapsis using vis-viva velocities.
    """
    import math
    vessel = conn.space_center.active_vessel
    ut = conn.space_center.ut
    grav_param = vessel.orbit.body.gravitational_parameter
    apo = vessel.orbit.apoapsis
    sma = vessel.orbit.semi_major_axis
    v1 = math.sqrt(grav_param * ((2.0 / apo) - (1.0 / sma)))
    v2 = math.sqrt(grav_param * ((2.0 / apo) - (1.0 / apo)))
    vessel.control.add_node(ut + vessel.orbit.time_to_apoapsis, prograde=(v2 - v1))
```

4) Plan Circularization at Apoapsis
- Get orbit info: get_orbit_info; note time_to_apoapsis_s.
- Alternative compute helpers: compute_circularize_node(at='apoapsis'); compute_burn_time(dv).
- set_maneuver_node(ut, prograde, normal, radial); warp_to(ut - burn_time/2).
- Execute burn (script):
  • Point to node burn vector; throttle to target Δv; optionally monitor remaining_burn_vector.
  • Cut throttle; delete node(s) when complete.

Reusable code — standalone circularize function (MIT; krpc/krpc-library):
```
def circularize_at_apoapsis(vessel, ut):
    """
    Create a maneuver node to circularize orbit at given time.
    """
    import math
    body = vessel.orbit.body
    GM = body.gravitational_parameter
    apo = vessel.orbit.apoapsis
    SMA = vessel.orbit.semi_major_axis
    v1 = math.sqrt(GM * ((2 / apo) - (1 / SMA)))
    v2 = math.sqrt(GM * ((2 / apo) - (1 / (apo))))
    dv = v2 - v1
    time = vessel.orbit.time_to_apoapsis + ut
    return vessel.control.add_node(time, prograde=dv)
```

5) Verify Orbit & Cleanup
- get_orbit_info — confirm Pe/Ap near targets; eccentricity low.
- If needed: compute_raise_lower_node(kind='periapsis'|'apoapsis', target_alt_m) for small corrections.
- Delete maneuver nodes and log SUMMARY with final orbit elements.

Snippets usage (search/resolve)
- Ascent control: search "ascent", "gravity turn", "TWR throttle".
- Circularize helper: search "circularize at apoapsis"; resolve into function.
- One‑shot: snippets_search_and_resolve({"query": "circularize orbit", "k": 5, "mode": "hybrid"}).

Notes
- Respect license policy: pass exclude_restricted=true in search if required.
- MechJeb integration: when available, use its kRPC service (ascent_autopilot, maneuver planner) for higher-level automation.
'''


@mcp.resource("resource://playbooks/launch-ascent-circularize")
def get_launch_ascent_circ_playbook() -> str:
    return LAUNCH_ASCENT_CIRC_PLAYBOOK


STATE_CHECKPOINT_PLAYBOOK = '''
State Checkpoint & Rollback Playbook

Purpose: Create safe restore points during missions and reliably roll back when needed. This complements the execute pipeline (unpause at start, pause at end).

When to checkpoint
- Before irreversible actions: liftoff, circularization, transfer ejection, capture, de‑orbit/landing.
- Before complex sequences or when testing new logic.

Naming & policy
- Use save_llm_checkpoint to create unique, namespaced saves (LLM_YYYYmmddTHHMMSSZ_<tag>_<id>), so gamer saves aren’t touched.
- Only load LLM_ saves (default safeguard); avoid quicksave/quickload unless you know you want to override the single quickslot.

Core tools
- Save: save_llm_checkpoint({"address":"<IP>", "tag":"pre_circ"}) → { ok, save_name }
- Load (auto‑pause): load_llm_checkpoint({"address":"<IP>", "save_name":"LLM_..."})
  • After load, the game is paused; UT won’t advance until you resume. The execute_script tool unpauses on start and pauses again on end.
- Quick save/load (fallback): quicksave({"address":"<IP>"}), quickload({"address":"<IP>"})
  • Caution: these operate on the single quicksave slot; prefer named LLM checkpoints.
- Revert flight to pad: revert_to_launch({"address":"<IP>"})
  • Use to restart quickly after a failed attempt.

Reference sequence
1) Snapshot state:
   - get_status_overview({"address":"<IP>"})
   - export_blueprint_diagram({"address":"<IP>", "format":"svg"})
2) Save checkpoint:
   - save_llm_checkpoint({"address":"<IP>", "tag":"pre_circ"}) → record save_name
3) Proceed with operations or execute_script (auto‑unpause on start).
4) If results are bad, load back:
   - load_llm_checkpoint({"address":"<IP>", "save_name":"LLM_..."})  # auto‑pause after load
   - Verify pause: get_time_status — UT should not advance while paused
   - Resume with execute_script (which unpauses) or continue with interactive steps

Tips
- Use descriptive tags: pre_ascent, pre_circ, pre_transfer, pre_capture, pre_deorbit.
- Keep a small chain of recent checkpoints so you can step back more than one phase.
- For quick resets from flight tests, revert_to_launch is fastest.
'''


@mcp.resource("resource://playbooks/state-checkpoint-rollback")
def get_state_checkpoint_playbook() -> str:
    return STATE_CHECKPOINT_PLAYBOOK
