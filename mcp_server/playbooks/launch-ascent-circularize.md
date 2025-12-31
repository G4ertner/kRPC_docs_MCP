Launch → Ascent → Circularize Playbook

Purpose: guide GeePT through the SCRIBE loop—observe, plan, execute, and adapt—while delivering a low-Kerbin orbit injection.

Core Loop (see master prompt)
- Check vessel makeup & state.
- Draft a step-by-step plan (gravity turn + circularization).
- Fetch any snippets/docs that de-risk the script.
- Execute one deterministic script with logs + SUMMARY.
- Review telemetry; decide next mission phase or retry.

0) Preflight & Safety
- Tooling warm-up: krpc_get_status; get_status_overview; get_vessel_blueprint (optionally export blueprint diagram).
- Verify staging tree, engine availability, and propellant; throttle=0, SAS/RCS as required.
- Capture baseline telemetry (dynamic_pressure_pa, g_force, current TWR). Abort if anomalies detected.

1) Telemetry Sweep & Mission Plan
- Call get_status_overview to snapshot vessel/environment/orbit/aero/time.
- Use get_engine_status and get_resource_breakdown if staging or propellant margins look uncertain.
- Optional: search_ksp_wiki("gravity turn") or snippets_search for ascent helpers when you need references.
- Draft plan bullets for Commander: launch heading, turn start/end altitudes, target apoapsis/periapsis, throttle envelopes, abort gates.

2) Script Preparation
- Keep loops bounded; call check_time(); add structured log lines.
- Rely on injected globals (`conn`, `vessel`, `sleep`, `math`, `logging`, etc.).
- Pull snippets when useful (e.g., Art Whaley autostage helpers). Respect license filters.
- Decide which constants belong in-script (target altitudes, gains) versus values read live (gravity, thrust, resources).

3) Example GeePT Execution (150 km target)

**Commander prompt**: “Computer, get me to an orbit of 150 km!”

**GeePT thinking**  
- Phase assess: LKO ascent within single script scope.  
- Data request: get_status_overview → confirm we are on pad, mass, available thrust, staging depth.  
- Plan: two-point gravity turn (start 7 km, finish 60 km), throttle feedback via dynamic pressure, reactive circularization burn that hugs apoapsis arrival.  
- Safety: stage only when dry; keep loops under 220 s (ascent) and 180 s (circularize); log every ~2 s.  
- Snippets: leverage stage-dry pattern (adapted from Art Whaley demo); no license conflicts.

**GeePT script**:
```python
log("BEGIN: streamlined 150 km ascent demo")

if vessel is None:
    print("SUMMARY: aborted — no active vessel in scene")
else:
    sc = conn.space_center
    orbit = vessel.orbit
    flight_surface = vessel.flight(vessel.surface_reference_frame)

    TARGET_ALT = 150_000.0
    TURN_START = 7_000.0
    TURN_END = 60_000.0
    TERMINAL_STAGE = 0
    KP_PE = 0.00018  # throttle gain for circularization
    STAGE_FUELS = ("LiquidFuel", "Oxidizer", "SolidFuel")

    def stage_dry():
        if vessel.control.current_stage <= TERMINAL_STAGE:
            return False
        try:
            resources = vessel.resources_in_decouple_stage(
                vessel.control.current_stage - 1,
                cumulative=False,
            )
        except Exception:
            return False
        saw_fuel = False
        for name in STAGE_FUELS:
            try:
                if resources.max(name) > 0.1:
                    saw_fuel = True
                    if resources.amount(name) > 0.5:
                        return False
            except Exception:
                continue
        return saw_fuel

    def maybe_stage(label: str):
        if stage_dry() or vessel.available_thrust < 0.5:
            log(f"STAGE: {label}")
            vessel.control.activate_next_stage()
            sleep(0.5)

    def turn_pitch(alt: float) -> float:
        if alt <= TURN_START:
            return 90.0
        if alt >= TURN_END:
            return 5.0
        fraction = (alt - TURN_START) / (TURN_END - TURN_START)
        return 90.0 - fraction * 85.0

    ap = vessel.auto_pilot
    ap.reference_frame = vessel.surface_reference_frame
    ap.engage()
    ap.stopping_time = (1, 1, 1)
    ap.target_pitch_and_heading(90, 90)

    vessel.control.sas = False
    vessel.control.rcs = False
    vessel.control.throttle = 1.0
    log("ASCENT: throttle up, gravity turn armed")

    ascent_t0 = sc.ut
    while orbit.apoapsis_altitude < TARGET_ALT and sc.ut - ascent_t0 < 220:
        check_time()
        alt = flight_surface.mean_altitude
        ap.target_pitch_and_heading(turn_pitch(alt), 90)
        maybe_stage("ascent burnout")
        if sc.ut % 2 < 0.2:
            log(
                f"ASCENT: alt={alt:.0f}m Ap={orbit.apoapsis_altitude:.0f}m "
                f"stage={vessel.control.current_stage} throttle={vessel.control.throttle:.2f}"
            )
        sleep(0.2)

    vessel.control.throttle = 0.0
    if orbit.apoapsis_altitude < TARGET_ALT - 2_000:
        print(
            f"""SUMMARY:
phase: streamlined 150km orbit
achieved: false
apoapsis_m: {orbit.apoapsis_altitude:.1f}
periapsis_m: {orbit.periapsis_altitude:.1f}
note: Apoapsis short—Commander, add thrust or flatten the turn sooner.
next_step: Adjust ascent profile and retry.
"""
        )
        raise SystemExit

    log("COAST: apoapsis reached, throttling down")
    try:
        lead = max((orbit.time_to_apoapsis or 0) - 4.0, 0.0)
        if lead > 0.5:
            sc.warp_to(sc.ut + lead)
    except Exception as exc:
        log(f"WARN: warp skipped ({exc})")

    ap.reference_frame = vessel.orbital_reference_frame
    ap.target_direction = (0, 1, 0)
    try:
        ap.wait()
    except Exception:
        pass

    log("CIRC: prograde burn with reactive throttle")
    burn_t0 = sc.ut
    while sc.ut - burn_t0 < 180:
        check_time()
        pe_error = TARGET_ALT - orbit.periapsis_altitude
        if pe_error <= 0:
            break
        tta = orbit.time_to_apoapsis or 0.0
        throttle_cmd = max(0.2, min(0.95, KP_PE * pe_error))
        if tta > 6.0:
            throttle_cmd = min(throttle_cmd, 0.4)
        elif tta < 2.0:
            throttle_cmd = min(throttle_cmd, 0.25)
        vessel.control.throttle = throttle_cmd
        log(
            f"CIRC: Pe={orbit.periapsis_altitude:.0f}m Ap={orbit.apoapsis_altitude:.0f}m "
            f"tta={tta:.1f}s thrtl={throttle_cmd:.2f}"
        )
        maybe_stage("circularization burnout")
        sleep(0.2)

    vessel.control.throttle = 0.0
    vessel.control.sas = True
    try:
        ap.disengage()
    except Exception:
        pass

    achieved = (
        abs(orbit.apoapsis_altitude - TARGET_ALT) < 4_000
        and abs(orbit.periapsis_altitude - TARGET_ALT) < 4_000
    )
    tta = orbit.time_to_apoapsis or float("nan")
    next_step = (
        "Commander, set transfer node or payload actions."
        if achieved
        else "Commander, re-run ascent with tweaks or add Δv margin."
    )
    print(
        f"""SUMMARY:
phase: streamlined 150km orbit
achieved: {str(achieved).lower()}
apoapsis_m: {orbit.apoapsis_altitude:.1f}
periapsis_m: {orbit.periapsis_altitude:.1f}
time_to_ap_s: {tta:.1f}
next_step: {next_step}
"""
    )
```

4) Post-Script Analysis
- Review SUMMARY and log transcript; confirm Δv balance and staging behavior.
- If achieved: tee up maneuver planning (compute_transfer_window_to_body, etc.).
- If shortfall: inspect telemetry (log altitudes, throttle responses). Adjust TURN_START/TURN_END or KP_PE; consider snippets_search for alternate throttle/TWR controllers.
- Optionally save state (save_llm_checkpoint) before iterating.

5) Useful Follow-up Resources
- compute_circularize_node(at='apoapsis') for analytical burn targeting.
- compute_burn_time(dv_m_s) to time warp-to-node precisely.
- get_stage_plan for deeper staging accounting.

Notes
- Always respect licensing when ingesting snippets (exclude_restricted=true if needed).
- If MechJeb or other automation mods expose kRPC APIs, consider delegating ascent or circularization but still wrap with GeePT logging and SUMMARY.
