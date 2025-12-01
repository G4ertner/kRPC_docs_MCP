# Issue 1: SyntaxError when ending script with raw `SUMMARY`

- **Summary:** Stage 1 ascent script failed immediately because I left a literal `SUMMARY:` label outside of a string, so the Python interpreter rejected the job instead of running the ascent logic.
- **Screenshot:** `artifacts/screenshots/issue-1.png`
- **Tool:** `start_execute_script_job`
- **Arguments:**
  - `address`: `127.0.0.1`
  - `code`: stage-1 ascent script (see code block below)
  - `hard_timeout_sec`: `60`
  - `timeout_sec`: `60`
  - `unpause_on_start`: `true`
- **Tool output:** The job log ended with `SyntaxError: invalid syntax` pointing at the stray `SUMMARY:` token, so the script never executed.
- **Steps to reproduce:**
  1. Submit the Stage 1 ascent script via `start_execute_script_job` as above.
  2. Observe that the runner raises `SyntaxError` at the trailing `SUMMARY:` line before any ascent logic runs.
- **Observed issue:** The script fails immediately with syntax error, preventing the ascent phase from even starting.
- **Expected behavior:** The script should execute, perform the ascent, and report the `SUMMARY` block via `print()` once complete.
- **Additional info:** The runner captures both stdout and stderr; the traceback and prefix `[[[EXEC_META]]]` are shown in the job log. Fix was to wrap the summary block in a string (e.g., `print("SUMMARY: ...")`).

**Script code:**
```python
log("BEGIN: Stage 1 — ascent to Kerbin LKO")
if vessel is None:
    print("SUMMARY:\nphase: stage1_ascent\nachieved: false\nreason: no active vessel\nnext_step: restart flight and try again")
else:
    sc = conn.space_center
    flight = vessel.flight(vessel.surface_reference_frame)
    orbit = vessel.orbit
    ap = vessel.auto_pilot
    ap.reference_frame = vessel.surface_reference_frame
    ap.reference_frame = vessel.surface_reference_frame
    ap.target_pitch_and_heading(90.0, 90.0)
    ap.engage()

    TARGET_ALT = 90_000.0
    TURN_START = 1_000.0
    TURN_END = 60_000.0
    LOOP_LIMIT = 220
    start_ut = sc.ut

    def pitch_for_alt(current_alt):
        if current_alt <= TURN_START:
            return 90.0
        if current_alt >= TURN_END:
            return 15.0
        frac = (current_alt - TURN_START) / (TURN_END - TURN_START)
        return 90.0 - frac * 75.0

    def stage_when_dry(label):
        if vessel.control.current_stage <= 0:
            return
        try:
            resources = vessel.resources_in_decouple_stage(
                vessel.control.current_stage - 1, cumulative=False
            )
        except Exception:
            return
        for fuel in ("LiquidFuel", "Oxidizer", "SolidFuel"):
            try:
                max_amount = resources.max(fuel)
                if max_amount <= 0.1:
                    continue
                amount = resources.amount(fuel)
            except Exception:
                continue
            if amount < 0.5:
                log(f"STAGE: {label} (dry detected)")
                vessel.control.activate_next_stage()
                sleep(0.5)
                return

    vessel.control.throttle = 1.0
    vessel.control.sas = False
    vessel.control.rcs = False

    log("ASCENT: throttle max, SAS off, gravity turn active")

    while sc.ut - start_ut < LOOP_LIMIT:
        check_time()
        alt = flight.mean_altitude
        orbit = vessel.orbit
        ap.target_pitch_and_heading(pitch_for_alt(alt), 90.0)
        stage_when_dry("ascent")
        if alt >= TARGET_ALT and orbit.apoapsis_altitude >= TARGET_ALT:
            break
        if sc.ut % 2 < 0.25:
            log(
                f"ASCENT: alt={alt:.0f}m ap={orbit.apoapsis_altitude:.0f}m "
                f"peri={orbit.periapsis_altitude:.0f}m stage={vessel.control.current_stage}"
            )
        sleep(0.25)

    vessel.control.throttle = 0.0
    vessel.control.sas = True
    try:
        ap.disengage()
    except Exception:
        pass

    orbit = vessel.orbit
    achieved = (
        orbit.apoapsis_altitude >= TARGET_ALT - 2_000
        and orbit.periapsis_altitude >= 30_000
    )
    print(
        "SUMMARY:\n"
        f"phase: stage1_ascent\n"
        f"achieved: {str(achieved).lower()}\n"
        f"apoapsis_m: {orbit.apoapsis_altitude:.1f}\n"
        f"periapsis_m: {orbit.periapsis_altitude:.1f}\n"
        f"time_until_ap: {orbit.time_to_apoapsis:.1f}\n"
        f"next_step: {'set maneuver toward transfer burn' if achieved else 'tweak ascent profile and rehearse'}\n"
    )
SUMMARY:
phase: stage1_ascent
achieved: yes
key_telemetry: apoapsis/periapsis altitudes above 80 km
recommended_next: plan transfer burn once stage plan confirmed
```

# Issue 2: `start_execute_script_job` hard-times out before ascent completes

- **Summary:** The Stage 1 ascent script ran for the full `hard_timeout_sec = 60` and was killed before the SUMMARY block could execute; the vessel was still accelerating toward Kerbin orbit (apoapsis ~30 km, periapsis well below zero).
- **Screenshot:** `artifacts/screenshots/issue-2.png`
- **Tool:** `start_execute_script_job`
- **Arguments:**
  - `address`: `127.0.0.1`
  - `code`: Stage 1 ascent script (see the job resource below)
  - `hard_timeout_sec`: `60`
  - `timeout_sec`: `60`
  - `unpause_on_start`: `true`
- **Tool output:** `error: { "message": "Hard timeout reached", "type": "TimeoutError" }` plus `stderr: "TimeoutExpired: hard timeout reached; process killed"`.
- **Steps to reproduce:**
  1. Launch the same Stage 1 ascent script via `start_execute_script_job` with the constants above (target apoapsis 90 km, while loop cap 220 s, throttle 1.0).
  2. Wait 60 s; while the vessel is still climbing, the job ends with the hard timeout before achieving orbit or printing a SUMMARY.
- **Observed issue:** The GeePT runner kills the script at 60 s even though it is still performing ascent work and has not met success criteria.
- **Expected behavior:** The script should be allowed to continue until it reaches the target (or an explicit failure condition), or the tools should expose the reason the 60 s limit is insufficient (e.g., adjust `hard_timeout_sec` based on phase duration).
- **Additional info:** `get_diagnostics` was called after the timeout (the data is logged), showing the vessel at ~13.4 km altitude, Mach 1.85, and still pitching into the turn. The issue blocks running deterministic ascent scripts with realistic gravity turns when the hard timeout is set too aggressively.
- **Actual script code:** see `resource://jobs/935d0500fbbf48ca82f7dc8a70222573.json` (contains the full script and metadata).

# Issue 3: Async callback errors surface during the long Stage 1 ascent job

- **Summary:** While running the longer Stage 1 ascent/job with `hard_timeout_sec=240`, the geept_mcp runner repeatedly logs `Exception in callback` tracebacks from `asyncio/base_events.py` whenever the script hits logging loops or stage changes, and the job ultimately ends in the same hard timeout even though the craft was still climbing toward LKO.
- **Screenshot:** `artifacts/screenshots/issue-3.png`
- **Tool:** `start_execute_script_job`
- **Arguments:**
  - `address`: `127.0.0.1`
  - `allow_imports`: `false`
  - `code`: Stage 1 ascent script (see code block below)
  - `hard_timeout_sec`: `240`
  - `timeout_sec`: `240`
  - `rpc_port`: `50000`
  - `stream_port`: `50001`
  - `unpause_on_start`: `true`
- **Tool output:** `get_job_status(job_id)` shows repeated `INFO    Processing request of type CallToolRequest` entries followed by an `Exception in callback` stack trace inside `asyncio.base_events` (lines 88-168) where the server closes sockets, then the job finishes with `error: {"type":"TimeoutError","message":"Hard timeout reached"}` and `stderr: "TimeoutExpired: hard timeout reached; process killed"`. The `result.diagnostics.pre_pause_flight` snapshot shows the vessel at ~100 km altitude, still sub-orbital, confirming the script had not completed and that the callback exception is unrelated to the craft.
- **Steps to reproduce:**
  1. Issue the Stage 1 ascent script via `start_execute_script_job` (code below) with `hard_timeout_sec = timeout_sec = 240` and default ports.
  2. Observe console logs; after ~28 s the server logs the `Exception in callback` trace every few seconds while the script is still logging ascent telemetry, but the script keeps running until the 240 s hard timeout triggers.
- **Observed issue:** The geept_mcp tooling surfaces asynchronous socket callback tracebacks even though the script is still executing and logging. These tracebacks are noisy, hint at a connection teardown, and coincide with the eventual hard timeout, which delays mission progress and makes it hard to distinguish real script problems from runner noise.
- **Expected behavior:** The script should execute for the requested duration without `Exception in callback` tracebacks, or at least the runner should handle logging/streaming without spurious asyncio errors when the vessel is healthy. If the job must terminate due to a timeout, that should be the only failure report.
- **Additional info:** The job's `result.follow_up` suggested `get_diagnostics`, which matched the status overview captured by `get_status_overview`. Despite the exception noise, the script kept logging multi-stage ascent telemetry and never hit a `SUMMARY` because the hard timeout finally killed it.
- **Actual script code:**
```python
log("BEGIN: Stage 1 - Kerbin ascent + gravity turn")
if vessel is None:
    print("SUMMARY:\nphase: stage1_ascent\nachieved: false\nreason: no active vessel\nnext_step: reload and try again")
else:
    sc = conn.space_center
    flight = vessel.flight(vessel.surface_reference_frame)
    orbit = vessel.orbit
    ap = vessel.auto_pilot
    ap.reference_frame = vehicle_surface_ref = vessel.surface_reference_frame
    ap.target_pitch_and_heading(90.0, 90.0)
    ap.engage()

    vessel.control.activate_next_stage()
    sleep(0.6)

    TARGET_APO = 90_000.0
    MIN_PERI = 70_000.0
    LOOP_LIMIT = 260
    start_ut = sc.ut

    def pitch_profile(current_alt):
        if current_alt <= 1_000.0:
            return 90.0
        if current_alt >= 60_000.0:
            return 15.0
        fraction = (current_alt - 1_000.0) / 59_000.0
        return 90.0 - fraction * 75.0

    def stage_when_dry(label):
        if vessel.control.current_stage <= 0:
            return
        try:
            resources = vessel.resources_in_decouple_stage(
                vessel.control.current_stage - 1,
                cumulative=False,
            )
        except Exception:
            return
        for fuel in ("LiquidFuel", "Oxidizer", "SolidFuel"):
            try:
                if resources.max(fuel) <= 0.1:
                    continue
                amount = resources.amount(fuel)
            except Exception:
                continue
            if amount < 0.5:
                log(f"STAGE: {label} (dry stage {vessel.control.current_stage})")
                vessel.control.activate_next_stage()
                sleep(0.6)
                return

    vessel.control.sas = False
    vessel.control.rcs = False
    vessel.control.throttle = 1.0
    log("ASCENT: throttle at max, SAS off, gravity turn live")

    while sc.ut - start_ut < LOOP_LIMIT:
        check_time()
        alt = flight.mean_altitude
        orbit = vessel.orbit
        ap.target_pitch_and_heading(pitch_profile(alt), 90.0)
        stage_when_dry("ascent")

        if orbit.apoapsis_altitude >= TARGET_APO and orbit.periapsis_altitude >= MIN_PERI:
            log("ASCENT: orbit target reached")
            break

        if orbit.apoapsis_altitude >= TARGET_APO * 0.9:
            vessel.control.throttle = min(0.35, vessel.control.throttle)
        if sc.ut % 2 < 0.25:
            log(
                f"ASCENT: alt={alt:.0f}m ap={orbit.apoapsis_altitude:.0f}m peri={orbit.periapsis_altitude:.0f}m stage={vessel.control.current_stage} throttle={vessel.control.throttle:.2f}"
            )
        sleep(0.25)

    vessel.control.throttle = 0.0
    vessel.control.sas = True
    try:
        ap.disengage()
    except Exception:
        pass

    orbit = vessel.orbit
    achieved = (
        orbit.apoapsis_altitude >= TARGET_APO - 1_000
        and orbit.periapsis_altitude >= MIN_PERI
    )
    summary = (
        "SUMMARY:\n"
        f"phase: stage1_ascent\n"
        f"achieved: {str(achieved).lower()}\n"
        f"apoapsis_m: {orbit.apoapsis_altitude:.1f}\n"
        f"periapsis_m: {orbit.periapsis_altitude:.1f}\n"
        f"time_until_ap: {orbit.time_to_apoapsis:.1f}\n"
        f"next_step: {'circularize when periapsis is above target' if achieved else 'adjust ascent parameters and retry'}\n"
    )
    print(summary)
```
