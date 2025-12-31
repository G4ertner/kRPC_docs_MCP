Vessel Blueprint Usage

Purpose: Provide the agent with a structural understanding of the current vessel to plan safe, effective scripts.

Recommended Calls:
- get_status_overview — confirm scene, body, situation
- get_vessel_blueprint — meta, stages (dv/TWR), engines, parts
- get_stage_plan — UI-like staging stack (rounded Δv + staged parts)
- start_part_tree_job + get_job_status → read_resource(result_resource) — retrieve full part tree safely

Key Fields:
- meta.current_stage — current stage index
- stages[] — per-engine-stage Δv/TWR (approximate)
- parts[].stage / parts[].decouple_stage — staging order and drop points
- engines[] — engine locations (part_id), thrust + Isp (isp_sea_level_s, isp_vacuum_s)

Checklist Before Staging/Burn:
1) Confirm next stage has engines and sufficient propellant (parts with LiquidFuel/Oxidizer/MonoPropellant/SolidFuel).
2) Verify TWR > 1 if performing a surface/ascent burn.
3) Ensure control capabilities: SAS/Reaction Wheels, RCS if required.
4) After staging, refresh blueprint to update structure and dv/TWR.

Background job workflow:
1) Call start_part_tree_job when you need the heavy artifact.
2) Poll get_job_status(job_id) until status == "SUCCEEDED"; inspect logs if FAILED.
3) Call read_resource(result_resource) to download resource://jobs/<job_id>.json and feed it into your planning.

Notes:
- Stage plan is an approximation; values can differ from KSP UI. Use as planning guidance.
- Geometry is best-effort; thrust axis and CoM may be unavailable.
- If a job fails, read get_job_status logs (power/connection issues, wrong scene) before retrying.

Snippets usage:
- For common control patterns (staging, throttle guards, SAS modes), search examples: snippets_search({"query": "throttle stage SAS", "k": 5, "mode": "hybrid"})
- Resolve a minimal helper (function/class) with snippets_resolve and adapt to current vessel blueprint constraints.
