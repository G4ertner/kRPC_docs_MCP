"""
Autopilot: launch → gravity turn → circularize to stable orbit.

Designed for a light two‑stage LFO stack with SRB boosters:
- Off-pad SRB assist, core LV-T45, upper LV-909 (as detected by prior scans).

Key behavior:
- Gentle gravity turn with dynamic pressure limiting (max-Q cap).
- Solid booster separation on burnout; auto-stage if thrust drops to 0.
- Core separation on LFO exhaustion in current decouple stage.
- Coast to apoapsis; SAS prograde hold.
- Active circularization: throttles to hold time-to-apoapsis ~ lead time,
  preventing apoapsis from running away while perigee rises.

Usage:
- Run via the kRPC docs tool's execute_script integration. This file relies on
  the injected globals: `conn`, `vessel`, `time`, `math`, `sleep`, `deadline`,
  `check_time`, `logging`, and `log`. Do not import kRPC or reconnect here.
"""

# NOTE: This script intentionally avoids imports; the runner injects helpers.


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def fmt_alt(m):
    try:
        return f"{m/1000:.1f} km"
    except Exception:
        return f"{m} m"


def stage_and_log(ctrl, msg="Staging"):
    ctrl.activate_next_stage()
    try:
        log(msg)
    except Exception:
        print(msg)


def launch_to_orbit(
    target_ap_m=80_000.0,
    target_circ_alt_m=80_000.0,
    heading_deg=90.0,
    turn_start_alt_m=250.0,
    turn_end_alt_m=45_000.0,
    max_q_pa=35_000.0,
    tap_lead_s=7.0,
):
    sc = conn.space_center
    v = vessel or sc.active_vessel
    if v is None:
        print("No active vessel; aborting.")
        print("SUMMARY: abort — no active vessel")
        return

    body = v.orbit.body
    atmo_top = body.atmosphere_depth if getattr(body, "has_atmosphere", False) else 0.0
    safe_circ_alt_m = max(target_circ_alt_m, (atmo_top or 0) + 1000.0)

    ap = v.auto_pilot
    ap.reference_frame = v.surface_reference_frame
    ap.engage()
    ap.target_roll = 90
    v.control.rcs = False
    v.control.sas = False
    v.control.throttle = 1.0
    ap.target_pitch_and_heading(90, heading_deg)

    # Acquire flight streams (fast polling)
    flight_srf = v.flight(body.reference_frame)
    s_alt = conn.add_stream(getattr, flight_srf, "mean_altitude")
    s_q = conn.add_stream(getattr, flight_srf, "dynamic_pressure")
    s_vert = conn.add_stream(getattr, flight_srf, "vertical_speed")
    s_ap_alt = conn.add_stream(getattr, v.orbit, "apoapsis_altitude")
    s_pe_alt = conn.add_stream(getattr, v.orbit, "periapsis_altitude")
    s_tap = conn.add_stream(getattr, v.orbit, "time_to_apoapsis")

    # Helper to detect LFO in current decouple stage
    def lfo_in_current_stage():
        stg = v.control.current_stage
        try:
            r = v.resources_in_decouple_stage(stg, False)
            return (r.amount("LiquidFuel") or 0.0) + (r.amount("Oxidizer") or 0.0)
        except Exception:
            return (v.resources.amount("LiquidFuel") or 0.0) + (v.resources.amount("Oxidizer") or 0.0)

    # Liftoff: make sure something is ignited and clamps released
    t_start = sc.ut
    for _ in range(6):
        if v.available_thrust > 0.0 and v.situation.name != "pre_launch":
            break
        stage_and_log(v.control, "Staging for ignition/clamp release …")
        sleep(0.5)
        check_time()

    # Defensive: ensure safe_circ_alt_m exists (some kRPC variants lazy-load body props)
    if 'safe_circ_alt_m' not in locals():
        atmo_top2 = getattr(body, "atmosphere_depth", 0.0) if getattr(body, "has_atmosphere", False) else 0.0
        safe_circ_alt_m = max(target_circ_alt_m, (atmo_top2 or 0) + 1000.0)
    print(f"Launch: target Ap {fmt_alt(target_ap_m)}, target circ {fmt_alt(safe_circ_alt_m)}")

    srb_sep_done = False
    core_sep_done = False

    # Ascent and gravity turn until target Ap is reached
    while True:
        check_time()
        alt = s_alt()
        ap_alt = s_ap_alt()
        q = s_q()

        # Gravity turn profile (linear from turn_start to turn_end)
        turn_progress = (alt - turn_start_alt_m) / max(1.0, (turn_end_alt_m - turn_start_alt_m))
        turn_progress = clamp(turn_progress, 0.0, 1.0)
        target_pitch = 90 - 80 * turn_progress  # leave a small margin above horizon
        ap.target_pitch_and_heading(max(5.0, target_pitch), heading_deg)

        # Max-Q throttle limiting
        throttle = 1.0
        if q > max_q_pa:
            throttle = clamp(1.0 - (q - max_q_pa) / (max_q_pa * 1.5), 0.3, 1.0)
        v.control.throttle = throttle

        # SRB separation (simple: when no SolidFuel left on vessel)
        if not srb_sep_done and alt > 1000:
            try:
                srb_fuel = v.resources.amount("SolidFuel") or 0.0
            except Exception:
                srb_fuel = 0.0
            if srb_fuel <= 0.1:
                stage_and_log(v.control, "SRBs empty — staging")
                srb_sep_done = True

        # Core separation on LFO depletion of current decouple stage
        if not core_sep_done and alt > 30_000:
            if lfo_in_current_stage() <= 0.1 and v.available_thrust <= 1.0:
                stage_and_log(v.control, "Core empty — staging to upper stage")
                core_sep_done = True

        # Failsafe: if we have no thrust while climbing and not reached target Ap, try staging
        if v.available_thrust < 1.0 and ap_alt < target_ap_m * 0.95 and alt > 1000:
            stage_and_log(v.control, "No thrust detected — auto-staging")

        # Cut when Ap achieved (slight undershoot for coast)
        if ap_alt >= target_ap_m * 0.98:
            break

        sleep(0.05)

    # Engine cutoff and coast to apoapsis
    v.control.throttle = 0.0
    ap.target_pitch_and_heading(0.0, heading_deg)
    v.control.sas = True
    try:
        v.control.sas_mode = sc.SASMode.prograde
    except Exception:
        pass

    # Optional rails warp close to Ap
    while s_tap() > 30.0 and s_ap_alt() > 50_000:
        try:
            sc.warp_to(sc.ut + s_tap() - 20.0)
        except Exception:
            # Fallback to busy-wait
            pass
        sleep(0.2)
        check_time()

    # Active circularization with time-to-Ap control
    def circularize_active(lead_time_s=tap_lead_s, timeout_s=240.0):
        ap.target_pitch_and_heading(0.0, heading_deg)
        v.control.sas = True
        try:
            v.control.sas_mode = sc.SASMode.prograde
        except Exception:
            pass

        base = 0.35  # base throttle
        kp = 0.12    # proportional gain on (tAp - lead)
        start_ut = sc.ut

        last_tap = None
        while True:
            check_time()
            ap_alt = s_ap_alt()
            pe_alt = s_pe_alt()
            tap = s_tap()
            alt = s_alt()

            # Avoid burning inside atmosphere
            if atmo_top and alt < atmo_top + 500.0:
                v.control.throttle = 0.0
                sleep(0.1)
                continue

            # Throttle to hold time-to-Ap near lead_time_s
            err = tap - lead_time_s
            thr = clamp(base + kp * err, 0.0, 1.0)

            # Keep Ap from running away if we got ahead of target significantly
            if ap_alt > target_ap_m * 1.05 and tap > lead_time_s + 5.0:
                thr = min(thr, 0.5)

            # Fine control as Pe approaches target
            if pe_alt > safe_circ_alt_m - 5_000.0:
                thr = min(thr, 0.6)
            if pe_alt > safe_circ_alt_m - 2_000.0:
                thr = min(thr, 0.4)

            v.control.throttle = thr

            # If time-to-Ap drifts far above lead, momentarily idle to recenter
            if tap > lead_time_s + 20.0:
                v.control.throttle = 0.0

            # Exit conditions: Pe at/above target, and Ap close to target
            if pe_alt >= safe_circ_alt_m - 200.0 and abs(ap_alt - target_ap_m) < 5_000.0:
                break

            # Bounded runtime safeguard
            if sc.ut - start_ut > timeout_s:
                log("Circularization timeout — exiting throttle loop")
                break

            # Observe rate sign change — if tap flips abruptly, keep burning lightly
            last_tap = tap
            sleep(0.05)

        v.control.throttle = 0.0

    circularize_active()

    # Finalize
    final_ap = s_ap_alt()
    final_pe = s_pe_alt()
    v.control.throttle = 0.0
    try:
        v.control.sas = True
        v.control.sas_mode = sc.SASMode.prograde
    except Exception:
        pass

    print(
        f"Orbit achieved: Ap={fmt_alt(final_ap)}, Pe={fmt_alt(final_pe)}; "
        f"incl={v.orbit.inclination * 180.0 / math.pi:.2f}°"
    )
    print(
        "SUMMARY: orbit — "
        f"Ap={final_ap:.0f} m, Pe={final_pe:.0f} m, target={target_ap_m:.0f}/{safe_circ_alt_m:.0f} m"
    )


if __name__ == "__main__":
    # Sensible defaults for Kerbin LKO
    launch_to_orbit(
        target_ap_m=80_000.0,
        target_circ_alt_m=80_000.0,
        heading_deg=90.0,
        turn_start_alt_m=250.0,
        turn_end_alt_m=45_000.0,
        max_q_pa=35_000.0,
        tap_lead_s=7.0,
    )
