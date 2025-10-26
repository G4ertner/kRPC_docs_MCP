#+ Handoff Notes — kRPC MCP Server for KSP

This document captures key implementation insights, current status, and pragmatic guidance for the next agent continuing this work.

## kRPC connection and scenes
- Assume vessel context can change (main menu, KSC, tracking, flight). Tools should fail soft and return helpful JSON (with "error" when appropriate) rather than raise exceptions.
- When setting or reading targets, check both vessel-level and SpaceCenter-level attributes — in some scenes, only one is populated.

## Celestial relationships (robust handling)
- Avoid proxy identity comparisons for body.orbit.reference_body — compare by names and be ready for null parents.
- If parents are missing, infer the “star” by the largest gravitational_parameter and use that to define a common frame for interplanetary logic.

## Staging and Δv
- The stock-like stage plan (implemented) segments burns at stage boundaries, attributing interleaved propellant to the preceding engine segment. This closely matches KSP’s DV readout.
- Provide environment toggles (current/sea_level/vacuum) to match KSP’s views.

## Navigation helpers
- Phase angle: project positions to the parent’s non-rotating frame (x–y) and use atan2 difference; wrap to [-180, 180].
- AN/DN: sample over one period and bisection-find zero-crossings against the target plane normal; it’s robust and scene-agnostic.

## Maneuver planning pattern
- Keep compute_* helpers read-only; return proposals like {ut, prograde, normal, radial}.
- Agent flow: compute → set node (set_maneuver_node) → warp (warp_to(ut - burn_time/2)) → execute via Python pipeline.
- The Maneuver Node Playbook resource (resource://playbooks/maneuver-node) guides deterministic order of operations.

## Power and telemetry
- Not all properties are exposed. Favor counts and best-effort estimates (e.g., solar exposure, RTG count). Return notes when estimates aren’t available.
- Prefer non-rotating reference frames for relative geometry.

## Screenshots (deferred)
- Return images as MCP resources with mime=image/png. A tool should return a resource URI.
- Choose capture method on KSP PC: (1) custom kRPC plugin (best), (2) OS-level capture agent (shared folder), or (3) F1 + folder watch fallback.

## Tests and stability
- Keep CLI scripts for quick local validation (scripts/*). They’re invaluable for smoke-testing tools.
- Prefer soft failures (JSON with context) over exceptions so agents can branch intelligently.

## Current status (high level)
- Knowledge tools: KSP Wiki (search/page/section) and kRPC docs search (done).
- kRPC tools (core done): telemetry, power/resources, surface/camera/waypoints, action groups, targeting/navigation (phase + AN/DN), staging/Δv (environment-aware), maneuver node I/O.
- Maneuver planning: Batch 1–2 implemented; Batch 3 initial (transfer windows, ejection node). Rendezvous phasing helper added (first-order).
- Playbook resource published.

## Suggested next steps
- Rendezvous: refine compute_rendezvous_phase_node (choose burn at Ap/Pe; optional small radial; handle edge cases with very close periods).
- One-shot transfer helper: given a body, plan window → set ejection node → optional warp (behind confirm).
- Screenshot capture: implement chosen path and expose as resource.
- Science opportunities: list experiments by situation/biome with transmit recommendations.
- Script execution pipeline: inject connectors/pauses; run safely; capture logs.

## Pointers
- Plan: PROJECT_IMPLEMENTATION_PLAN.md (contains screenshot strategy and playbook info)
- Entry points & logic: mcp_server/krpc/tools.py, mcp_server/krpc/readers.py, playbook in mcp_server/resources.py
- CLI scripts for quick tests: scripts/*

Good luck — the core scaffolding is solid; the above should save time on the tricky edges.

