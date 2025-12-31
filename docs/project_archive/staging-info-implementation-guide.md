# (Archived) Commander’s Guide: Fixing `get_staging_info` (with legacy side-by-side comparison)

> Archived note: `get_staging_info` is no longer exposed as an MCP tool (kept internal); this guide is retained for historical context.

This guide turns `docs/staging-info-bug-analysis.md` into a concrete, step-by-step implementation + test plan. It assumes a running KSP + kRPC setup and the GeePT MCP server.

## Goal

- Keep the old behavior available as `get_staging_info_legacy`.
- Make `get_staging_info` stop “splitting” stages into:
  - an “engine-only stage” (engines > 0, `prop_mass_kg == 0`)
  - followed by a “fuel-only stage” (engines == 0, `prop_mass_kg > 0`)
- Prevent the “mass clamps to 0.1 kg” failure mode that yields absurd Δv.
- Provide automated unit tests and an in-game comparison procedure to validate improvement.

## What was implemented (current repo state)

### 1) Tool split

- `get_staging_info` now uses the updated algorithm.
- `get_staging_info_legacy` preserves the previous behavior for comparisons.

Implementation locations:
- `mcp_server/utils/krpc_utils/readers.py` (algorithm + legacy)
- `mcp_server/general_tools_impl/blueprints_parts_and_staging.py` (tool impl wrappers)
- `mcp_server/general_tools.py` (MCP tool exports)

### 2) Algorithm change (high-level)

The new `readers.staging_info(conn)` does:

1. Iterate stage numbers `s` from `vessel.control.current_stage` down to `0`.
2. Model the **stage event** at `s` first by subtracting dry mass of parts with `decouple_stage == s` (jettisoned when stage `s` is activated).
3. For engines ignited at stage `s` (`engine.part.stage == s`), approximate the propellant burned **before the next stage event** as propellant stored in `resources_in_decouple_stage(s - 1)` (filtered by the stage’s `engine.propellant_names`).
4. If `resources_in_decouple_stage(s - 1)` yields no propellant mass (common for final stages / tanks with `decouple_stage = -1`), fall back to `Engine.propellants[*].total_resource_available` (converted to kg via `Resources.density`).

This keeps “engines and fuel in the same stage entry” for typical staging layouts and avoids subtracting fuel in stages with no ignited engines.

## Automated tests (no KSP required)

Run:

```powershell
python -m pytest -q
```

New coverage:
- `tests/test_staging_info_split_and_fallback.py`
  - Verifies the legacy split (fuel shows up in the wrong stage).
  - Verifies the new behavior shifts fuel onto the engine stage.
  - Verifies the fallback path for “final stage fuel” using `Engine.propellants.total_resource_available`.

## In-game tests (KSP + kRPC required)

### Prerequisites

1. Start KSP and load a save in a flight scene with an active vessel.
2. Restart the MCP server so tool changes are live:
   - From repo root run `restart_mcp_server.bat`

### Test A: One-command comparison via manual script

Run (PowerShell):

```powershell
python tests\manual\krpc_staging_info_compare_test.py --address 127.0.0.1 --full
```

What to look for in the printed summaries:
- `bad_engines_no_prop` should drop (ideally to 0 for typical staged rockets).
- `bad_prop_no_engines` should drop (ideally to 0 for typical staged rockets).
- `total_delta_v_m_s` should become more plausible (no single-stage absurd spikes).

### Test B: Tool-level comparison (GeePT MCP)

Call these two tools against the same vessel and compare stage rows:

- `get_staging_info()`
- `get_staging_info_legacy()`

Suggested acceptance checks:
- For any stage row where `engines > 0`, `prop_mass_kg` should usually be > 0 (except edge cases like empty stages or non-propellant engines).
- For any stage row where `engines == 0`, `prop_mass_kg` should usually be 0 (because no engines ignite in that stage).
- No row should report obviously impossible behavior (e.g., `m1_kg` collapsing to near-zero with a multi‑km/s Δv spike).

### Test C: Compare against in-game Δv (sanity)

For a few representative craft, compare the new `get_staging_info` output to:
- the in-game staging Δv readout (bottom-right staging UI), and/or
- Kerbal Engineer Redux / MechJeb if installed.

Don’t expect exact matches; you’re looking for:
- correct stage alignment (fuel with its engines)
- no extreme Δv outliers caused by math artifacts
- stage-to-stage totals that are “in the right ballpark”

## Recommended test craft set

To gain confidence, validate at least these patterns:

1. Simple 2-stage rocket (stack decoupler between stages)
2. Radial boosters (symmetry, radial decouplers, crossfeed off)
3. SRB boosters (SolidFuel)
4. Crossfeed / fuel-duct craft (fuel lines)
5. (Optional) Asparagus staging

## Interpreting results: “better than legacy”

The updated implementation is “better” if it:

- Eliminates the stage split symptom in the bug report (engine-only stage followed by fuel-only stage).
- Prevents the “m1 clipped to 0.1 kg” → absurd Δv behavior by avoiding mis-attributed propellant subtraction.
- Produces more stable summaries for planning tools that rely on staging estimates.

If you want, we can add a dedicated MCP tool that returns a structured diff (`legacy` vs `current`) and a simple “quality score” so you can run comparisons directly from chat without running the manual script.
