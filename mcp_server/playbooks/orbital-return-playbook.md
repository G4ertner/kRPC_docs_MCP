# Perfect Reentry Playbook

## Mission Summary
- **Target:** Operate the  vessel out of its Kerbin orbit and reentry the vessel with heat shield first through the atmosphere, to then land near KSC (0° lat/0° lon).
- **Readiness:** SAS remains enabled; always call `set_sas_mode('retrograde', reference_frame=vessel.orbital_reference_frame)` before burns/entry so the navball’s retrograde marker matches the actual vector.

## Vessel Snapshot
**Reason:** Get an understanding of the vessel's structure and current staging situation
**Tools:** get_stage_plan, get_part_tree
**Example:**
- Mass ~29.7 t; only the vacuum engine/tank stage and the capsule with heat shield/parachute stack remain thanks to the latest quicksave.
- Reaction wheels/RCS units are ready for attitude corrections; ~30 units of monopropellant stay available for fine alignment nudges.
- Only the capsule’s stage 0 plus the engine stage are left, so staging down before the atmosphere automatically exposes the heat shield and parachutes.

## Pre-Burn Checklist
1. Dispose of any lingering stages that are not needed for the deorbit burn (e.g. burnt main stages or booster stages). Only the final vacuum stage should remain for the reentry burn. If not even that stage is available, work with RCS.
2. Confirm the stage plan shows stage 2 as the active engine stage with propellant and that stage 1 is empty or staged; record `current_stage` so the burn is fired in the right stage.
3. **Calculate point deorbit burn:** 
   - Find the best point in the orbit to conduct the deorbit burn to aim for a landing as near to KSC as possible.
   - target a periapsis of 25–35 km for a shallow and safe reentry profile
   - Set a node for the deorbit burn
4. **Warp to Deorbit burn node**
5. Orient the vessel to retrograde using the `set_sas_mode` tool

## Reentry Procedure
1. **Retro Burn (target periapsis 25–35 km).**
   - Keep **SAS locked to retrograde** (via `set_sas_mode` or in the `vessel.orbital_reference_frame`)
   - keep throttle low (0.18–0.35) until heading/pitch error is within 10 degrees of the retrograde vector, and throttle down to about 0.12 if the error grows.
   - Log orientation errors approximately every five seconds using check_time in the loop.
   - When periapsis reads between 25 and 35 km, cut throttle and **stage down** to the capsule immediately by firing any remaining stages above stage 0.

2. **Entry Prep (80–90 km, we want ~3–4 minutes lead).**
   - Warp to roughly 85km, just before the ship enters the atmosphere. As soon as you hit 70km, the game will stop warp automatically.
   - keep SAS locked in vessel.orbital_reference_frame, and reestablish the retrograde heading.
   - Confirm the heat shield is the only leading surface and only stage 0 remains active.
   - Log heading/pitch error values and ensure they stay under about 10 degrees before hitting the atmosphere.

3. **Atmospheric Capture (70–30 km).**
   - Keep throttle at zero and maintain the retrograde hold by persistently calling set_sas_mode in the orbital frame.
   - Monitor dynamic pressure and g-force; if either spikes, verify the orientation error and relax the target if needed to keep from tumbling.
   - At about 9 km, stage the heat shield decoupler once heating dies down and log that event.

4. **Chute Sequence (<4 km).**
   - After the heat shield is off and nose is retrograde, activate stage 0 once vertical speed is manageable for parachute deployment.
   - Allow drogue and main chutes to deploy sequentially through staging and confirm each deployment via log output.
   - Keep log statements to call out distance to the ground and once the distance does not change anymore, assume the ship has landed (0 meters for sea level, anything above for land).
   - **Important:** Keep in a catch in case an anomalies with catastrophic outcomes. You want your script to exit gracefully if something goes wrong.

5. **Landing & Recovery.**
   - Time the entry corridor to fly over KSC, log touchdown latitude and longitude, and compute the surface distance back to 0° lat/0° lon.
   - After touchdown, close off decouplers and produce a SUMMARY block stating the periapsis, touchdown coordinates, distance to KSC, and any anomalies.

## Safeguards & Lessons
- Always call set_sas_mode('retrograde', reference_frame=vessel.orbital_reference_frame) before burns or entry; the default frame may interpret retrograde as a normal or radial axis.
- Compare heading and pitch directly to flight.retrograde rather than to flight.prograde so the guard cannot see a 180-degree difference.
- Stage off every booster above the capsule immediately after the retro burn so the heat shield faces the flow.
- Log heading error, pitch error, periapsis, apoapsis, and current stage at key events so the next LLM can determine the ship’s state precisely.
