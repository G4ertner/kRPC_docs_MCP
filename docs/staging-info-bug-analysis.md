# Analysis of Issue 003 — `get_staging_info` stage grouping and delta‑v calculation

## Does the bug report make sense?

Yes. The behavior described in the report is not expected and reproduces consistently in the logs.

`get_staging_info` is splitting each *logical stage* into two entries:
- one stage entry with engines but no propellant
- another stage entry with propellant but no engines

The report also shows an implausibly high delta‑v (≈ 9.4 km/s) because the mass calculation can reduce a
stage’s final mass to `0.1 kg`, which is physically impossible for a real KSP vessel stage.

## Evidence from the logs

The attached `.jsonl` log shows `get_staging_info({})` producing output like:

- Stage 6: `engines=3` but `prop_mass_kg=0.0`
- Stage 5: `engines=0` but `prop_mass_kg=16000.0`
- Stage 4: `prop_mass_kg=8000.0` and `m1_kg` becomes `0.1 kg`, which results in `delta_v_m_s=9366.03…`

The separation of engines from their propellant clearly demonstrates the bug. The unrealistic delta‑v arises
because `m1_kg` is clipped to `0.1 kg` when the code subtracts propellant mass from the current mass and
then forces a minimum mass; this inadvertently treats an entire stage as almost weightless when the
propellant mass estimate exceeds the vessel mass.

## Root cause in the code

Inspection of the `krpc_utils` module in the MCP repository shows that `get_staging_info` computes masses
and delta‑v by looping through the vessel’s stages and calling helper functions:

- `_combined_isp_and_thrust_for_stage` groups engines by activation stage (`part.stage`) and sums thrust and
  specific impulse.
- `_stage_prop_mass_kg` calls `vessel.resources_in_decouple_stage(stage, cumulative=False)`, which returns
  resources *decoupled* at a particular stage rather than resources *accessible to engines activated in that
  stage*.

Because each part has two staging numbers (activation stage and decouple stage), resources attached via
decouplers often have `decouple_stage = stage - 1`. This mismatch causes propellant from a stage to be
reported in the previous stage.

The mass update logic then clips to a minimum mass:

```py
m1 = max(0.1, m0 - prop_mass)  # ensures non-zero mass
mass_current = max(0.1, m1 - drop_mass)
```

When `prop_mass > m0`, the result is artificially clipped to `0.1 kg`. The subsequent delta‑v calculation
using the Tsiolkovsky rocket equation therefore produces an enormous delta‑v because the ratio `m0 / m1`
becomes extremely large.

These design decisions—using decouple stages for propellant and enforcing an arbitrary minimum mass—explain
the anomalies seen in the bug report.

## Existing kRPC limitations and community discussions

kRPC does not provide a built‑in function to compute per‑stage delta‑v or a complete staging tree. Each
part tracks two staging indices (activation stage and decouple stage), and kRPC exposes them separately.
This leads to confusion when matching engines with the propellant available to them.

A GitHub issue from 2016 (`krpc/krpc#274`) describes the same problem: engines appear in one stage while
their fuel appears in the next because `vessel.resources_in_decouple_stage()` uses the decouple stage.

Contributors recommended avoiding `resources_in_decouple_stage` and instead using the engine’s
`propellants` list to determine what resources are reachable by that engine.

The kRPC `Propellant` object provides:
- `total_resource_available` (amount reachable by the engine, respecting fuel flow rules)
- `total_resource_capacity`

This approach directly answers “how much propellant can this engine burn?” and avoids guessing based on
decouple stages.

## Plan to address the issue

### 1) Acknowledge the limitation and document it

Update MCP documentation to explain that `get_staging_info` is an approximation because KSP and kRPC do not
expose a simple per‑stage delta‑v API. Highlight that `vessel.resources_in_decouple_stage()` returns
resources decoupled at a given stage and does not necessarily correspond to resources accessible to engines
activated in that stage.

### 2) Revise the propellant calculation

Instead of using `vessel.resources_in_decouple_stage`:

- For each engine in a stage, iterate through `engine.propellants`.
- For each propellant, use `propellant.total_resource_available`, convert to kg using resource densities,
  then sum across all propellants and engines.

This ensures only propellant reachable by those engines is counted, and it naturally handles cross‑feed
rules and radial boosters (which `resources_in_decouple_stage` cannot).

To compute dry mass after burning fuel, subtract the sum of all propellant masses actually consumed.
Avoid forcing `m1` / `mass_current` to `0.1 kg` when the propellant mass estimate exceeds the current mass.

### 3) Handle dropped mass and decouplers

Dry mass includes structural parts and empty fuel tanks that will be discarded when the stage is decoupled.

- Use `vessel.parts.in_decouple_stage(stage)` to find parts jettisoned at this stage and subtract their
  masses from `mass_current` for the *next* stage.
- Do not subtract dry mass from the current stage until after the engine burn is finished.

### 4) Test with multiple crafts and edge cases

Use the uploaded log and additional KSP vessels to verify that the revised algorithm:
- aligns engines and propellant in the same stage entry
- produces reasonable delta‑v values

Check cases with:
- radial boosters
- asparagus staging
- solid rocket boosters
- fuel cross‑feed

Compare computed delta‑v with KSP’s in‑game delta‑v indicator or tools like Kerbal Engineer Redux / MechJeb.

### 5) Consider kRPC’s stage plan APIs

kRPC provides `vessel.stage_plan` and `vessel.approximate_stage_plan` in newer versions. These return a
list of stages with total mass, dry mass, and available resources (with approximations). Evaluate whether
these methods produce better staging and delta‑v information than the current MCP approach.

## Community delta‑v calculators and what we can learn from them

Several community projects show how to compute stage‑by‑stage delta‑v more robustly than the current MCP
approach. One comprehensive example is `DeltaVLib.ks` (kOS), which parses vessel parts to build per‑stage
dictionaries of engines, fuel, and mass. Key aspects of its approach:

- Build dictionaries of parts/engines by stage, accumulating total mass and dry mass.
- Determine the range of stages an engine contributes to and add its thrust/mass‑flow contributions to
  every stage in that range (helps with asparagus and engines spanning multiple stages).
- Compute effective specific impulse and thrust per stage by combining engines.
- Apply the rocket equation per stage while maintaining a running total of mass above the stage:
  `Δv = 9.81 * Isp * ln((m_acc + m_stage)/(m_acc + m_stage_dry))`.

The key lesson is to calculate propellant availability from the engines’ perspective (what they can actually
draw), rather than from decouplers, and to process stages in sequence while tracking the mass stack above.

## Summary

The observed behavior in `get_staging_info` originates from mixing activation stages and decouple stages
when calculating propellant, and from forcing masses to a minimum of `0.1 kg`. This splits engines and fuel
across stages and can produce unrealistic delta‑v values.

To address this, group engines and propellant based on activation stages and use
`Engine.propellants.total_resource_available` to compute the mass of fuel actually available. Avoid
artificial mass clipping, handle dry‑mass drop after fuel depletion, and test against multiple vessels.
Document limitations and consider leveraging kRPC’s built‑in stage plan functions or community scripts.

## References

- Confusing issue with Engine & Resource stages · Issue #274 · krpc/krpc  
  https://github.com/krpc/krpc/issues/274
- Parts — kRPC documentation  
  https://krpc.github.io/krpc/python/api/space-center/parts.html
- `DeltaVLib.ks` (kOS)  
  https://github.com/ScranchNew/kOS-Launch-Scripts/blob/master/libraries/DeltaVLib.ks

