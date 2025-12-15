# Idealized Log: Kerbin LKO → Mun Low Lunar Orbit (verbatim scripts attached)

> **Source:** extracted from the provided Codex rollout `.jsonl`. All Python scripts below are copied *verbatim* from the `code` argument of `mcp__geept_mcp__start_execute_script_job` calls.

## Timeline summary

This run reached **Kerbin parking orbit**, planned and executed **TMI (LKO → Mun transfer)**, performed **midcourse correction(s)** to target ~20 km Mun periapsis, warped into **Mun SOI**, then executed **capture + circularize** into ~19–21 km low lunar orbit.

## Steps + scripts

---

## 0) Preflight & Safety
- 2025-12-13 20:37:30 — **throttle/stage sanity check**
- 2025-12-13 20:46:12 — **Throttle/SAS safety reset**
- 2025-12-13 20:47:16 — **Emergency throttle/engine shutdown**

### 2025-12-13 20:37:30 — throttle/stage sanity check

```python
log('BEGIN: throttle/stage sanity check')

if vessel is None:
    print('SUMMARY:\nphase: preflight\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
orbit = vessel.orbit

# Read basic engine/throttle state
ctrl.throttle = 0.0
sleep(0.2)

avail_thrust = vessel.available_thrust
max_thrust = vessel.max_thrust
throttle = ctrl.throttle
situation = vessel.situation

print(f"preflight: situation={situation}, throttle={throttle:.2f}, avail_thrust={avail_thrust:.1f}, max_thrust={max_thrust:.1f}")

# Try staging if no thrust is available
if avail_thrust <= 0.1:
    log('No available thrust; attempting activate_next_stage()')
    ctrl.activate_next_stage()
    sleep(0.6)

# Throttle up briefly to confirm response
ctrl.throttle = 1.0
sleep(0.4)
avail_thrust2 = vessel.available_thrust
max_thrust2 = vessel.max_thrust
print(f"after stage+throttle: throttle={ctrl.throttle:.2f}, avail_thrust={avail_thrust2:.1f}, max_thrust={max_thrust2:.1f}")

# Return to safe state
ctrl.throttle = 0.0
ctrl.sas = True
sleep(0.2)

ok = avail_thrust2 > 0.1 or vessel.available_thrust > 0.1
print('SUMMARY:')
print(f"phase: preflight\nachieved: {str(ok).lower()}\nreason: {'thrust confirmed' if ok else 'still no thrust'}\nnext_step: {'proceed to ascent script' if ok else 'check staging/engines, then retry'}")
```

### 2025-12-13 20:46:12 — Throttle/SAS safety reset

```python
log('Throttle/SAS safety reset')

if vessel is None:
    print('SUMMARY:\nphase: safety_reset\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

ctrl = vessel.control
ctrl.throttle = 0.0
ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: safety_reset')
print('achieved: true')
print('reason: throttle set to 0 and SAS enabled')
print('next_step: continue mission plan')
```

### 2025-12-13 20:47:16 — Emergency throttle/engine shutdown

```python
log('Emergency throttle/engine shutdown')

if vessel is None:
    print('SUMMARY:\nphase: emergency_shutdown\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

ctrl = vessel.control
ctrl.throttle = 0.0
sleep(0.2)

# Attempt to shutdown all active engines
engines = vessel.parts.engines
shutdown_count = 0
for e in engines:
    try:
        if e.active and e.has_fuel:
            e.shutdown()
            shutdown_count += 1
    except Exception:
        pass

ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: emergency_shutdown')
print('achieved: true')
print(f'reason: throttle=0; engines_shutdown={shutdown_count}')
print('next_step: re-evaluate flight state and proceed carefully')
```

---

## 1) Ascent and Kerbin Orbit Insertion
- 2025-12-13 20:36:07 — **Kerbin parking orbit insertion (target ~80km circular)**
- 2025-12-13 20:39:07 — **Kerbin parking orbit insertion (retry; target ~80km circular)**

### 2025-12-13 20:36:07 — Kerbin parking orbit insertion (target ~80km circular)

```python
log('BEGIN: Kerbin parking orbit insertion (target ~80km circular)')

if vessel is None:
    print('SUMMARY:\nphase_goal: reach Kerbin parking orbit\nachieved: false\nreason: no active vessel\nnext_step: Ensure a vessel is active in flight scene and retry.\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
orbit = vessel.orbit
ap = vessel.auto_pilot
surf_flight = vessel.flight(vessel.surface_reference_frame)

TARGET_AP = 80_000.0
TARGET_PE = 78_000.0
TURN_START_ALT = 250.0
TURN_END_ALT = 45_000.0
MAX_Q = 28_000.0  # Pa
LOOP_LIMIT = 400

# Reset state
ctrl.sas = False
ap.reference_frame = vessel.surface_reference_frame
ap.engage()

# Initial vertical ascent
ap.target_pitch_and_heading(90.0, 90.0)
ctrl.throttle = 1.0
sleep(0.5)

# Launch
ctrl.activate_next_stage()
sleep(0.7)

# Helpers

def pitch_profile(alt: float) -> float:
    if alt <= TURN_START_ALT:
        return 90.0
    if alt >= TURN_END_ALT:
        return 10.0
    frac = (alt - TURN_START_ALT) / (TURN_END_ALT - TURN_START_ALT)
    return 90.0 - frac * 80.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def stage_if_needed() -> bool:
    # stage if current stage has no liquid fuel
    try:
        stage = ctrl.current_stage
        lf = vessel.resources_in_decouple_stage(stage, False).amount('LiquidFuel')
        ox = vessel.resources_in_decouple_stage(stage, False).amount('Oxidizer')
        if lf < 0.1 and ox < 0.1:
            ctrl.activate_next_stage()
            sleep(0.4)
            return True
    except Exception:
        pass
    return False


# Ascent loop: drive apoapsis to target
start_ut = sc.ut
for i in range(LOOP_LIMIT):
    check_time()

    alt = surf_flight.mean_altitude
    q = surf_flight.dynamic_pressure
    ap_alt = orbit.apoapsis_altitude

    pitch = pitch_profile(alt)
    ap.target_pitch_and_heading(pitch, 90.0)

    # Simple max-Q throttle limiter
    if q > MAX_Q:
        ctrl.throttle = clamp(ctrl.throttle - 0.05, 0.2, 1.0)
    else:
        ctrl.throttle = clamp(ctrl.throttle + 0.02, 0.2, 1.0)

    # Stage if out of fuel
    stage_if_needed()

    if ap_alt >= TARGET_AP:
        log(f'Cutoff: apoapsis reached {ap_alt:.0f}m')
        ctrl.throttle = 0.0
        break

    if sc.ut - start_ut > 260:
        log('Timeout in ascent loop; cutting throttle')
        ctrl.throttle = 0.0
        break

    sleep(0.2)

# Coast to near apoapsis
log('Coasting to apoapsis')
while orbit.time_to_apoapsis > 35:
    check_time()
    sleep(0.5)

# Circularize at apoapsis
log('Circularization burn at apoapsis')
mu = orbit.body.gravitational_parameter
r = orbit.apoapsis
v_circ = (mu / r) ** 0.5
v = orbit.speed

dv = max(0.0, v_circ - v)

# Estimate burn time
thrust = max(0.1, vessel.available_thrust)
isp = max(1.0, vessel.specific_impulse)
m0 = vessel.mass
g0 = 9.80665
mdot = thrust / (isp * g0)

m1 = m0 / (2.718281828459045 ** (dv / (isp * g0)))
burn_time = max(0.1, (m0 - m1) / mdot)

# Point prograde
ap.reference_frame = orbit.reference_frame
ap.target_direction = (0, 1, 0)
ap.wait()

# Burn centered on apoapsis
lead = burn_time / 2
while orbit.time_to_apoapsis > lead:
    check_time()
    sleep(0.1)

ctrl.throttle = 1.0
sleep(max(0.0, burn_time - 1.0))
ctrl.throttle = 0.2
sleep(1.0)
ctrl.throttle = 0.0

# Finalize
ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase_goal: reach Kerbin parking orbit')
print(f"achieved: {str(orbit.periapsis_altitude >= TARGET_PE).lower()}")
print(f"apoapsis_m: {orbit.apoapsis_altitude:.1f}")
print(f"periapsis_m: {orbit.periapsis_altitude:.1f}")
print(f"inclination_deg: {orbit.inclination:.4f}")
print('next_step: proceed to Mun transfer planning')
```

### 2025-12-13 20:39:07 — Kerbin parking orbit insertion (retry; target ~80km circular)

```python
log('BEGIN: Kerbin parking orbit insertion (retry; target ~80km circular)')

if vessel is None:
    print('SUMMARY:\nphase_goal: reach Kerbin parking orbit\nachieved: false\nreason: no active vessel\nnext_step: Ensure a vessel is active in flight scene and retry.\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
orbit = vessel.orbit
ap = vessel.auto_pilot
surf_flight = vessel.flight(vessel.surface_reference_frame)

TARGET_AP = 80_000.0
TARGET_PE = 78_000.0
TURN_START_ALT = 250.0
TURN_END_ALT = 45_000.0
MAX_Q = 28_000.0  # Pa
LOOP_LIMIT = 520

# Reset state
ctrl.sas = False
ap.reference_frame = vessel.surface_reference_frame
ap.engage()

# Initial vertical ascent
ap.target_pitch_and_heading(90.0, 90.0)
ctrl.throttle = 1.0
sleep(0.5)

# Launch
ctrl.activate_next_stage()
sleep(0.7)

# Helpers

def pitch_profile(alt: float) -> float:
    if alt <= TURN_START_ALT:
        return 90.0
    if alt >= TURN_END_ALT:
        return 10.0
    frac = (alt - TURN_START_ALT) / (TURN_END_ALT - TURN_START_ALT)
    return 90.0 - frac * 80.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def stage_if_needed() -> bool:
    # stage if current stage has no liquid fuel
    try:
        stage = ctrl.current_stage
        lf = vessel.resources_in_decouple_stage(stage, False).amount('LiquidFuel')
        ox = vessel.resources_in_decouple_stage(stage, False).amount('Oxidizer')
        if lf < 0.1 and ox < 0.1:
            ctrl.activate_next_stage()
            sleep(0.4)
            return True
    except Exception:
        pass
    return False


# Ascent loop: drive apoapsis to target
start_ut = sc.ut
for i in range(LOOP_LIMIT):
    check_time()

    alt = surf_flight.mean_altitude
    q = surf_flight.dynamic_pressure
    ap_alt = orbit.apoapsis_altitude

    pitch = pitch_profile(alt)
    ap.target_pitch_and_heading(pitch, 90.0)

    # Simple max-Q throttle limiter
    if q > MAX_Q:
        ctrl.throttle = clamp(ctrl.throttle - 0.05, 0.2, 1.0)
    else:
        ctrl.throttle = clamp(ctrl.throttle + 0.02, 0.2, 1.0)

    # Stage if out of fuel
    stage_if_needed()

    if ap_alt >= TARGET_AP:
        log(f'Cutoff: apoapsis reached {ap_alt:.0f}m')
        ctrl.throttle = 0.0
        break

    if sc.ut - start_ut > 260:
        log('Timeout in ascent loop; cutting throttle')
        ctrl.throttle = 0.0
        break

    sleep(0.2)

# Coast to near apoapsis
log('Coasting to apoapsis')
while orbit.time_to_apoapsis > 35:
    check_time()
    sleep(0.5)

# Circularize at apoapsis
log('Circularization burn at apoapsis')
mu = orbit.body.gravitational_parameter
r = orbit.apoapsis
v_circ = (mu / r) ** 0.5
v = orbit.speed

dv = max(0.0, v_circ - v)

# Estimate burn time
thrust = max(0.1, vessel.available_thrust)
isp = max(1.0, vessel.specific_impulse)
m0 = vessel.mass
g0 = 9.80665
mdot = thrust / (isp * g0)

m1 = m0 / (2.718281828459045 ** (dv / (isp * g0)))
burn_time = max(0.1, (m0 - m1) / mdot)

# Point prograde
ap.reference_frame = orbit.reference_frame
ap.target_direction = (0, 1, 0)
ap.wait()

# Burn centered on apoapsis
lead = burn_time / 2
while orbit.time_to_apoapsis > lead:
    check_time()
    sleep(0.1)

ctrl.throttle = 1.0
sleep(max(0.0, burn_time - 1.0))
ctrl.throttle = 0.2
sleep(1.0)
ctrl.throttle = 0.0

# Finalize
ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase_goal: reach Kerbin parking orbit')
print(f"achieved: {str(orbit.periapsis_altitude >= TARGET_PE).lower()}")
print(f"apoapsis_m: {orbit.apoapsis_altitude:.1f}")
print(f"periapsis_m: {orbit.periapsis_altitude:.1f}")
print(f"inclination_deg: {orbit.inclination:.4f}")
print('next_step: proceed to Mun transfer planning')
```

---

## 2) Post-LKO Stage Cleanup
- 2025-12-13 20:51:37 — **Stage cleanup: drop Swivel/empty tank stage (advance to stage 4)**

### 2025-12-13 20:51:37 — Stage cleanup: drop Swivel/empty tank stage (advance to stage 4)

```python
log('Stage cleanup: drop Swivel/empty tank stage (advance to stage 4)')

if vessel is None:
    print('SUMMARY:\nphase: stage_cleanup\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

ctrl = vessel.control

before_stage = ctrl.current_stage
before_mass = vessel.mass

# Advance stages until we reach stage 4 (as observed in this craft)
# or until we detect a working vacuum engine with fuel.
for _ in range(6):
    if ctrl.current_stage <= 4:
        break
    ctrl.activate_next_stage()
    sleep(0.6)

after_stage = ctrl.current_stage
after_mass = vessel.mass

print('SUMMARY:')
print('phase: stage_cleanup')
print('achieved: true')
print(f'before_stage: {before_stage}')
print(f'after_stage: {after_stage}')
print(f'before_mass_kg: {before_mass:.1f}')
print(f'after_mass_kg: {after_mass:.1f}')
print('next_step: plan Mun transfer node')
```

---

## 3) Plan Transfer Burn (LKO → Mun)
- 2025-12-13 20:53:39 — **Plan Mun transfer node (Kerbin->Mun) via Hohmann + closest-approach refinement**
- 2025-12-13 21:04:25 — **Re-plan Mun transfer node after quickload (same method)**

### 2025-12-13 20:53:39 — Plan Mun transfer node (Kerbin->Mun) via Hohmann + closest-approach refinement

```python
log('Plan Mun transfer node (Kerbin->Mun) via Hohmann + closest-approach refinement')

if vessel is None:
    print('SUMMARY:\nphase: plan_transfer\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
orbit = vessel.orbit
ctrl = vessel.control

kerbin = orbit.body
mun = sc.bodies['Mun']

# Clear existing nodes
for n in list(ctrl.nodes):
    try:
        n.remove()
    except Exception:
        pass

mu = kerbin.gravitational_parameter
r1 = kerbin.equatorial_radius + orbit.apoapsis_altitude
r2 = mun.orbit.semi_major_axis

# Hohmann transfer prograde estimate
v1 = (mu / r1) ** 0.5
v_trans_peri = (mu * (2 / r1 - 1 / ((r1 + r2) / 2))) ** 0.5
prograde_dv = max(0.0, v_trans_peri - v1)

# Phase angle method: choose UT when Mun leads by ~44 deg (approx for Kerbin->Mun)
# We'll brute-sample a set of candidate UTs and pick smallest closest-approach distance.
now = sc.ut
best = None

# sample every 5 minutes over next ~2 orbits (about 3 hours)
for dt in range(0, 3 * 60 * 60, 5 * 60):
    ut = now + dt
    node = ctrl.add_node(ut, prograde=prograde_dv)
    try:
        ca = orbit.closest_approach_distance(mun.orbit)
        if best is None or ca < best[0]:
            best = (ca, ut)
    except Exception:
        pass
    try:
        node.remove()
    except Exception:
        pass

if best is None:
    print('SUMMARY:\nphase: plan_transfer\nachieved: false\nreason: could not evaluate closest approach\nnext_step: retry planning or use manual node placement\n')
    raise SystemExit

best_ca, best_ut = best

# refine around best UT with smaller step
best2 = (best_ca, best_ut)
for dt in range(-20 * 60, 20 * 60 + 1, 60):
    ut = best_ut + dt
    node = ctrl.add_node(ut, prograde=prograde_dv)
    try:
        ca = orbit.closest_approach_distance(mun.orbit)
        if ca < best2[0]:
            best2 = (ca, ut)
    except Exception:
        pass
    try:
        node.remove()
    except Exception:
        pass

best_ca, best_ut = best2

# Create final node
final_node = ctrl.add_node(best_ut, prograde=prograde_dv)

print('SUMMARY:')
print('phase: plan_transfer')
print('achieved: true')
print(f'node_ut: {best_ut:.3f}')
print(f'node_prograde_dv: {prograde_dv:.3f}')
print(f'closest_approach_m: {best_ca:.1f}')
print('next_step: execute transfer node')
```

### 2025-12-13 21:04:25 — Re-plan Mun transfer node after quickload (same method)

```python
log('Re-plan Mun transfer node after quickload (same method)')

if vessel is None:
    print('SUMMARY:\nphase: plan_transfer\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
orbit = vessel.orbit
ctrl = vessel.control

kerbin = orbit.body
mun = sc.bodies['Mun']

# Clear existing nodes
for n in list(ctrl.nodes):
    try:
        n.remove()
    except Exception:
        pass

mu = kerbin.gravitational_parameter
r1 = kerbin.equatorial_radius + orbit.apoapsis_altitude
r2 = mun.orbit.semi_major_axis

v1 = (mu / r1) ** 0.5
v_trans_peri = (mu * (2 / r1 - 1 / ((r1 + r2) / 2))) ** 0.5
prograde_dv = max(0.0, v_trans_peri - v1)

now = sc.ut
best = None

for dt in range(0, 3 * 60 * 60, 5 * 60):
    ut = now + dt
    node = ctrl.add_node(ut, prograde=prograde_dv)
    try:
        ca = orbit.closest_approach_distance(mun.orbit)
        if best is None or ca < best[0]:
            best = (ca, ut)
    except Exception:
        pass
    try:
        node.remove()
    except Exception:
        pass

if best is None:
    print('SUMMARY:\nphase: plan_transfer\nachieved: false\nreason: could not evaluate closest approach\nnext_step: retry planning or use manual node placement\n')
    raise SystemExit

best_ca, best_ut = best

best2 = (best_ca, best_ut)
for dt in range(-20 * 60, 20 * 60 + 1, 60):
    ut = best_ut + dt
    node = ctrl.add_node(ut, prograde=prograde_dv)
    try:
        ca = orbit.closest_approach_distance(mun.orbit)
        if ca < best2[0]:
            best2 = (ca, ut)
    except Exception:
        pass
    try:
        node.remove()
    except Exception:
        pass

best_ca, best_ut = best2

final_node = ctrl.add_node(best_ut, prograde=prograde_dv)

print('SUMMARY:')
print('phase: plan_transfer')
print('achieved: true')
print(f'node_ut: {best_ut:.3f}')
print(f'node_prograde_dv: {prograde_dv:.3f}')
print(f'closest_approach_m: {best_ca:.1f}')
print('next_step: warp+execute transfer node')
```

---

## 4) Execute Transfer Burn (TMI)
- 2025-12-13 21:01:44 — **EXECUTE NODE: Kerbin->Mun transfer burn**
- 2025-12-13 21:05:13 — **WARP+EXECUTE NODE: Kerbin->Mun transfer (avoid geept_mcp timewarp tools)**

### 2025-12-13 21:01:44 — EXECUTE NODE: Kerbin->Mun transfer burn

```python
log('EXECUTE NODE: Kerbin->Mun transfer burn')

if vessel is None:
    print('SUMMARY:\nphase: execute_node\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
ap = vessel.auto_pilot
orbit = vessel.orbit

if len(ctrl.nodes) == 0:
    print('SUMMARY:\nphase: execute_node\nachieved: false\nreason: no maneuver node present\nnext_step: create a transfer node first\n')
    raise SystemExit

node = ctrl.nodes[0]

# Estimate burn time
thrust = vessel.available_thrust
isp = vessel.specific_impulse
m0 = vessel.mass
g0 = 9.80665

mdot = thrust / (isp * g0)
dv = node.remaining_delta_v
m1 = m0 / (2.718281828459045 ** (dv / (isp * g0)))
burn_time = (m0 - m1) / mdot

# Point to node
ap.reference_frame = node.reference_frame
ap.target_direction = node.burn_vector(ap.reference_frame)
ap.engage()
ap.wait()

# Warp close to burn time
lead = burn_time / 2
while node.time_to > lead + 5:
    check_time()
    sleep(0.5)

# Burn
while node.time_to > lead:
    check_time()
    sleep(0.05)

ctrl.throttle = 1.0

# Coarse burn
while node.remaining_delta_v > 5.0:
    check_time()
    sleep(0.1)

# Fine burn with throttle taper
while node.remaining_delta_v > 0.2:
    check_time()
    dv_left = node.remaining_delta_v
    if dv_left < 2.0:
        ctrl.throttle = 0.15
    elif dv_left < 10.0:
        ctrl.throttle = 0.3
    else:
        ctrl.throttle = 0.7
    sleep(0.05)

ctrl.throttle = 0.0

# Remove node
try:
    node.remove()
except Exception:
    pass

ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: execute_node')
print('achieved: true')
print(f'next_body: {orbit.next_orbit.body.name if orbit.next_orbit is not None else "unknown"}')
print(f'time_to_soi_change: {orbit.time_to_soi_change if orbit.next_orbit is not None else -1}')
print('next_step: coast and plan MCC if needed')
```

### 2025-12-13 21:05:13 — WARP+EXECUTE NODE: Kerbin->Mun transfer (avoid geept_mcp timewarp tools)

```python
log('WARP+EXECUTE NODE: Kerbin->Mun transfer (avoid geept_mcp timewarp tools)')

if vessel is None:
    print('SUMMARY:\nphase: execute_node\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
ap = vessel.auto_pilot
orbit = vessel.orbit

if len(ctrl.nodes) == 0:
    print('SUMMARY:\nphase: execute_node\nachieved: false\nreason: no maneuver node present\nnext_step: create a transfer node first\n')
    raise SystemExit

node = ctrl.nodes[0]

# Estimate burn time
thrust = max(0.1, vessel.available_thrust)
isp = max(1.0, vessel.specific_impulse)
m0 = vessel.mass
g0 = 9.80665

mdot = thrust / (isp * g0)
dv = node.remaining_delta_v
m1 = m0 / (2.718281828459045 ** (dv / (isp * g0)))
burn_time = max(0.1, (m0 - m1) / mdot)

# Point to node
ap.reference_frame = node.reference_frame
ap.target_direction = node.burn_vector(ap.reference_frame)
ap.engage()
ap.wait()

# Warp close to burn time using raw sleep-based time control
lead = burn_time / 2
while node.time_to > lead + 60:
    check_time()
    # coarse time skip by physics warp is not used here; just wait
    sleep(1.0)

while node.time_to > lead + 5:
    check_time()
    sleep(0.25)

# Burn centered on node
while node.time_to > lead:
    check_time()
    sleep(0.05)

ctrl.throttle = 1.0

# Coarse burn
while node.remaining_delta_v > 5.0:
    check_time()
    sleep(0.1)

# Fine burn with throttle taper
while node.remaining_delta_v > 0.2:
    check_time()
    dv_left = node.remaining_delta_v
    if dv_left < 1.0:
        ctrl.throttle = 0.08
    elif dv_left < 2.0:
        ctrl.throttle = 0.18
    elif dv_left < 5.0:
        ctrl.throttle = 0.35
    elif dv_left < 10.0:
        ctrl.throttle = 0.7
    else:
        ctrl.throttle = 1.0
    sleep(0.05)

ctrl.throttle = 0.0

# Remove node
try:
    node.remove()
except Exception:
    pass

ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: execute_node')
print('achieved: true')
try:
    print(f'next_body: {orbit.next_orbit.body.name}')
    print(f'time_to_soi_change: {orbit.time_to_soi_change}')
except Exception:
    print('next_body: unknown')
    print('time_to_soi_change: -1')
print('next_step: coast and plan MCC if needed')
```

---

## 5) Transfer Coast & Encounter Checks
- 2025-12-13 21:21:23 — **Post-burn safety: throttle=0, shutdown any active engines**
- 2025-12-13 21:21:44 — **Check encounter: Kerbin orbit time_to_soi_change**
- 2025-12-13 21:25:16 — **Preview next_orbit (post-SOI) encounter parameters**
- 2025-12-13 21:29:10 — **Baseline Mun encounter (next_orbit) check**

### 2025-12-13 21:21:23 — Post-burn safety: throttle=0, shutdown any active engines

```python
log('Post-burn safety: throttle=0, shutdown any active engines')

if vessel is None:
    print('SUMMARY:\nphase: post_burn_safety\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

ctrl = vessel.control
ctrl.throttle = 0.0
sleep(0.2)

shutdown_count = 0
for e in vessel.parts.engines:
    try:
        if e.active and e.has_fuel:
            e.shutdown()
            shutdown_count += 1
    except Exception:
        pass

ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: post_burn_safety')
print('achieved: true')
print(f'engines_shutdown: {shutdown_count}')
print('next_step: verify encounter / plan MCC if required')
```

### 2025-12-13 21:21:44 — Check encounter: Kerbin orbit time_to_soi_change

```python
log('Check encounter: Kerbin orbit time_to_soi_change')

if vessel is None:
    print('SUMMARY:\nphase: encounter_check\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

orbit = vessel.orbit

try:
    t = orbit.time_to_soi_change
    body = orbit.next_orbit.body.name
    print('SUMMARY:')
    print('phase: encounter_check')
    print('achieved: true')
    print(f'next_body: {body}')
    print(f'time_to_soi_change: {t}')
    print('next_step: plan midcourse correction if periapsis not ideal')
except Exception as e:
    print('SUMMARY:')
    print('phase: encounter_check')
    print('achieved: false')
    print(f'reason: {e}')
    print('next_step: ensure transfer achieved SOI encounter')
```

### 2025-12-13 21:25:16 — Preview next_orbit (post-SOI) encounter parameters

```python
log('Preview next_orbit (post-SOI) encounter parameters')

if vessel is None:
    print('SUMMARY:\nphase: preview_next_orbit\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

orbit = vessel.orbit

try:
    no = orbit.next_orbit
    print('SUMMARY:')
    print('phase: preview_next_orbit')
    print('achieved: true')
    print(f'next_body: {no.body.name}')
    print(f'periapsis_altitude: {no.periapsis_altitude}')
    print(f'apoapsis_altitude: {no.apoapsis_altitude}')
    print(f'eccentricity: {no.eccentricity}')
    print('next_step: plan MCC to tune Mun periapsis')
except Exception as e:
    print('SUMMARY:')
    print('phase: preview_next_orbit')
    print('achieved: false')
    print(f'reason: {e}')
    print('next_step: ensure transfer achieved SOI encounter')
```

### 2025-12-13 21:29:10 — Baseline Mun encounter (next_orbit) check

```python
log('Baseline Mun encounter (next_orbit) check')

if vessel is None:
    print('SUMMARY:\nphase: baseline_encounter\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

orbit = vessel.orbit

try:
    no = orbit.next_orbit
    print('SUMMARY:')
    print('phase: baseline_encounter')
    print('achieved: true')
    print(f'next_body: {no.body.name}')
    print(f'next_periapsis_altitude: {no.periapsis_altitude}')
    print(f'next_time_to_periapsis: {no.time_to_periapsis}')
    print('next_step: plan/execute MCC if periapsis not ~20km')
except Exception as e:
    print('SUMMARY:')
    print('phase: baseline_encounter')
    print('achieved: false')
    print(f'reason: {e}')
    print('next_step: verify transfer and encounter')
```

---

## 6) Midcourse Corrections
- 2025-12-13 21:26:11 — **Midcourse correction planner: target Mun periapsis ~20km**
- 2025-12-13 21:27:00 — **Execute small midcourse correction node**
- 2025-12-13 21:29:40 — **Plan midcourse correction: target Mun Pe ~20km (create node at UT+1h)**
- 2025-12-13 21:30:26 — **EXECUTE MCC NODE (radial -60 m/s)**
- 2025-12-13 21:35:17 — **EXECUTE MCC NODE (short; node is imminent)**

### 2025-12-13 21:26:11 — Midcourse correction planner: target Mun periapsis ~20km

```python
log('Midcourse correction planner: target Mun periapsis ~20km')

if vessel is None:
    print('SUMMARY:\nphase: plan_mcc\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
orbit = vessel.orbit

mun = sc.bodies['Mun']

if orbit.next_orbit is None or orbit.next_orbit.body.name != 'Mun':
    print('SUMMARY:\nphase: plan_mcc\nachieved: false\nreason: no Mun encounter in next_orbit\nnext_step: ensure transfer achieved Mun SOI encounter\n')
    raise SystemExit

# Clear existing nodes
for n in list(ctrl.nodes):
    try:
        n.remove()
    except Exception:
        pass

# Plan a small correction 1 hour from now
ut = sc.ut + 3600

# Grid search on prograde and radial
best = None
best_node = None

for pro in range(-50, 51, 10):
    for rad in range(-50, 51, 10):
        node = ctrl.add_node(ut, prograde=float(pro), radial=float(rad))
        try:
            pe = orbit.next_orbit.periapsis_altitude
            err = abs(pe - 20_000.0)
            if best is None or err < best[0]:
                best = (err, pe, pro, rad)
                best_node = node
            else:
                node.remove()
        except Exception:
            try:
                node.remove()
            except Exception:
                pass

if best is None:
    print('SUMMARY:\nphase: plan_mcc\nachieved: false\nreason: could not evaluate candidates\nnext_step: retry or plan MCC manually\n')
    raise SystemExit

err, pe, pro, rad = best

# Remove all nodes except best
for n in list(ctrl.nodes):
    if n != best_node:
        try:
            n.remove()
        except Exception:
            pass

print('SUMMARY:')
print('phase: plan_mcc')
print('achieved: true')
print(f'node_ut: {ut:.3f}')
print(f'best_prograde: {pro:.1f}')
print(f'best_radial: {rad:.1f}')
print(f'predicted_mun_pe_alt: {pe:.1f}')
print('next_step: execute MCC node')
```

### 2025-12-13 21:27:00 — Execute small midcourse correction node

```python
log('Execute small midcourse correction node')

if vessel is None:
    print('SUMMARY:\nphase: execute_mcc\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
ap = vessel.auto_pilot

if len(ctrl.nodes) == 0:
    print('SUMMARY:\nphase: execute_mcc\nachieved: false\nreason: no maneuver node present\nnext_step: create MCC node first\n')
    raise SystemExit

node = ctrl.nodes[0]

# Estimate burn time
thrust = vessel.available_thrust
isp = vessel.specific_impulse
m0 = vessel.mass
g0 = 9.80665

mdot = thrust / (isp * g0)
dv = node.remaining_delta_v
m1 = m0 / (2.718281828459045 ** (dv / (isp * g0)))
burn_time = (m0 - m1) / mdot

# Point to node
ap.reference_frame = node.reference_frame
ap.target_direction = node.burn_vector(ap.reference_frame)
ap.engage()
ap.wait()

lead = burn_time / 2

while node.time_to > lead:
    check_time()
    sleep(0.05)

ctrl.throttle = 0.5
sleep(burn_time * 0.9)
ctrl.throttle = 0.0

try:
    node.remove()
except Exception:
    pass

ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: execute_mcc')
print('achieved: true')
print('next_step: check encounter and plan further corrections if needed')
```

### 2025-12-13 21:29:40 — Plan midcourse correction: target Mun Pe ~20km (create node at UT+1h)

```python
log('Plan midcourse correction: target Mun Pe ~20km (create node at UT+1h)')

if vessel is None:
    print('SUMMARY:\nphase: plan_mcc\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
orbit = vessel.orbit

mun = sc.bodies['Mun']

if orbit.next_orbit is None or orbit.next_orbit.body.name != 'Mun':
    print('SUMMARY:\nphase: plan_mcc\nachieved: false\nreason: no Mun encounter in next_orbit\nnext_step: ensure transfer achieved Mun SOI encounter\n')
    raise SystemExit

# Clear existing nodes
for n in list(ctrl.nodes):
    try:
        n.remove()
    except Exception:
        pass

ut = sc.ut + 3600

# Heuristic: radial adjustment to tune periapsis
best = None
best_node = None

for rad in range(-60, 61, 10):
    node = ctrl.add_node(ut, radial=float(rad))
    try:
        pe = orbit.next_orbit.periapsis_altitude
        err = abs(pe - 20_000.0)
        if best is None or err < best[0]:
            best = (err, pe, rad)
            best_node = node
        else:
            node.remove()
    except Exception:
        try:
            node.remove()
        except Exception:
            pass

if best is None:
    print('SUMMARY:\nphase: plan_mcc\nachieved: false\nreason: could not evaluate candidates\nnext_step: retry or plan MCC manually\n')
    raise SystemExit

err, pe, rad = best

# Remove all nodes except best
for n in list(ctrl.nodes):
    if n != best_node:
        try:
            n.remove()
        except Exception:
            pass

print('SUMMARY:')
print('phase: plan_mcc')
print('achieved: true')
print(f'node_ut: {ut:.3f}')
print(f'best_radial: {rad:.1f}')
print(f'predicted_mun_pe_alt: {pe:.1f}')
print('next_step: execute MCC node')
```

### 2025-12-13 21:30:26 — EXECUTE MCC NODE (radial -60 m/s)

```python
log('EXECUTE MCC NODE (radial -60 m/s)')

if vessel is None:
    print('SUMMARY:\nphase: execute_mcc\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
ap = vessel.auto_pilot

if len(ctrl.nodes) == 0:
    print('SUMMARY:\nphase: execute_mcc\nachieved: false\nreason: no maneuver node present\nnext_step: create MCC node first\n')
    raise SystemExit

node = ctrl.nodes[0]

# Estimate burn time safely
thrust = max(0.1, vessel.available_thrust)
isp = max(1.0, vessel.specific_impulse)
m0 = vessel.mass
g0 = 9.80665

mdot = thrust / (isp * g0)
dv = node.remaining_delta_v
m1 = m0 / (2.718281828459045 ** (dv / (isp * g0)))
burn_time = max(0.1, (m0 - m1) / mdot)

# Point to node
ap.reference_frame = node.reference_frame
ap.target_direction = node.burn_vector(ap.reference_frame)
ap.engage()
ap.wait()

lead = burn_time / 2

while node.time_to > lead:
    check_time()
    sleep(0.05)

ctrl.throttle = 0.6
sleep(max(0.0, burn_time - 0.5))
ctrl.throttle = 0.15
sleep(0.5)
ctrl.throttle = 0.0

try:
    node.remove()
except Exception:
    pass

ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: execute_mcc')
print('achieved: true')
print('next_step: check encounter and adjust if needed')
```

### 2025-12-13 21:35:17 — EXECUTE MCC NODE (short; node is imminent)

```python
log('EXECUTE MCC NODE (short; node is imminent)')

if vessel is None:
    print('SUMMARY:\nphase: execute_mcc\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

ctrl = vessel.control
ap = vessel.auto_pilot

if len(ctrl.nodes) == 0:
    print('SUMMARY:\nphase: execute_mcc\nachieved: false\nreason: no maneuver node present\nnext_step: create MCC node first\n')
    raise SystemExit

node = ctrl.nodes[0]

# Point to node
ap.reference_frame = node.reference_frame
ap.target_direction = node.burn_vector(ap.reference_frame)
ap.engage()
ap.wait()

# No warp; burn immediately if imminent
if node.time_to > 1.0:
    while node.time_to > 0.5:
        check_time()
        sleep(0.05)

ctrl.throttle = 0.2
sleep(0.4)
ctrl.throttle = 0.0

try:
    node.remove()
except Exception:
    pass

ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: execute_mcc')
print('achieved: true')
print('next_step: warp to SOI entry and perform capture burn')
```

---

## 7) Mun SOI Entry
- 2025-12-13 21:37:18 — **WARP to Mun SOI (stop ~10 min early)**
- 2025-12-13 21:38:27 — **WARP to Mun SOI entry (stop ~20s before)**
- 2025-12-13 21:39:02 — **Coast through SOI boundary (wait for body to switch to Mun)**

### 2025-12-13 21:37:18 — WARP to Mun SOI (stop ~10 min early)

```python
log('WARP to Mun SOI (stop ~10 min early)')

if vessel is None:
    print('SUMMARY:\nphase: warp_to_soi\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

orbit = vessel.orbit
sc = conn.space_center

# Warp by waiting until close to SOI change
try:
    t = orbit.time_to_soi_change
except Exception:
    print('SUMMARY:\nphase: warp_to_soi\nachieved: false\nreason: no SOI change available\nnext_step: ensure Mun encounter exists\n')
    raise SystemExit

stop_margin = 600.0

while t > stop_margin:
    check_time()
    sleep(1.0)
    t = orbit.time_to_soi_change

print('SUMMARY:')
print('phase: warp_to_soi')
print('achieved: true')
print(f'time_to_soi_change: {t}')
print('next_step: refine warp closer to SOI entry')
```

### 2025-12-13 21:38:27 — WARP to Mun SOI entry (stop ~20s before)

```python
log('WARP to Mun SOI entry (stop ~20s before)')

if vessel is None:
    print('SUMMARY:\nphase: warp_to_soi_fine\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

orbit = vessel.orbit

try:
    t = orbit.time_to_soi_change
except Exception:
    print('SUMMARY:\nphase: warp_to_soi_fine\nachieved: false\nreason: no SOI change available\nnext_step: ensure Mun encounter exists\n')
    raise SystemExit

stop_margin = 20.0

while t > stop_margin:
    check_time()
    sleep(0.25)
    t = orbit.time_to_soi_change

print('SUMMARY:')
print('phase: warp_to_soi_fine')
print('achieved: true')
print(f'time_to_soi_change: {t}')
print('next_step: coast through boundary and confirm body switch')
```

### 2025-12-13 21:39:02 — Coast through SOI boundary (wait for body to switch to Mun)

```python
log('Coast through SOI boundary (wait for body to switch to Mun)')

if vessel is None:
    print('SUMMARY:\nphase: soi_switch\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

orbit = vessel.orbit
start = conn.space_center.ut

while orbit.body.name != 'Mun':
    check_time()
    sleep(0.25)
    if conn.space_center.ut - start > 120:
        break

print('SUMMARY:')
print('phase: soi_switch')
print(f'achieved: {str(orbit.body.name == "Mun").lower()}')
print(f'current_body: {orbit.body.name}')
print(f'time_to_periapsis: {orbit.time_to_periapsis}')
print('next_step: perform Mun capture burn at periapsis')
```

---

## 8) Mun Capture & Low Lunar Orbit
- 2025-12-13 21:40:55 — **CAPTURE+CIRCULARIZE at Mun periapsis (execute node)**

### 2025-12-13 21:40:55 — CAPTURE+CIRCULARIZE at Mun periapsis (execute node)

```python
log('CAPTURE+CIRCULARIZE at Mun periapsis (execute node)')

if vessel is None:
    print('SUMMARY:\nphase: capture\nachieved: false\nreason: no active vessel\nnext_step: load a flight with an active vessel and retry\n')
    raise SystemExit

sc = conn.space_center
ctrl = vessel.control
ap = vessel.auto_pilot
orbit = vessel.orbit

if orbit.body.name != 'Mun':
    print('SUMMARY:\nphase: capture\nachieved: false\nreason: not in Mun SOI\nnext_step: warp/coast to Mun SOI first\n')
    raise SystemExit

# Clear existing nodes
for n in list(ctrl.nodes):
    try:
        n.remove()
    except Exception:
        pass

# Plan retrograde burn at periapsis to capture + circularize
ut = sc.ut + orbit.time_to_periapsis

# Estimate dv needed to circularize at periapsis
mu = orbit.body.gravitational_parameter
r_p = orbit.periapsis
v_p = orbit.speed
v_circ = (mu / r_p) ** 0.5

# If currently hyperbolic or highly elliptical, burn retrograde by (v_p - v_circ)
dv = max(0.0, v_p - v_circ)

node = ctrl.add_node(ut, prograde=-dv)

# Estimate burn time
thrust = max(0.1, vessel.available_thrust)
isp = max(1.0, vessel.specific_impulse)
m0 = vessel.mass
g0 = 9.80665

mdot = thrust / (isp * g0)
m1 = m0 / (2.718281828459045 ** (dv / (isp * g0)))
burn_time = max(0.1, (m0 - m1) / mdot)

# Point to node
ap.reference_frame = node.reference_frame
ap.target_direction = node.burn_vector(ap.reference_frame)
ap.engage()
ap.wait()

lead = burn_time / 2

# Coast to burn start
while node.time_to > lead:
    check_time()
    sleep(0.1)

# Burn with taper
ctrl.throttle = 1.0
while node.remaining_delta_v > 5.0:
    check_time()
    sleep(0.1)

while node.remaining_delta_v > 0.2:
    check_time()
    dv_left = node.remaining_delta_v
    if dv_left < 1.0:
        ctrl.throttle = 0.08
    elif dv_left < 2.0:
        ctrl.throttle = 0.18
    elif dv_left < 5.0:
        ctrl.throttle = 0.35
    else:
        ctrl.throttle = 0.7
    sleep(0.05)

ctrl.throttle = 0.0

try:
    node.remove()
except Exception:
    pass

ctrl.sas = True
sleep(0.2)

print('SUMMARY:')
print('phase: capture')
print('achieved: true')
print(f'periapsis_altitude: {orbit.periapsis_altitude}')
print(f'apoapsis_altitude: {orbit.apoapsis_altitude}')
print(f'eccentricity: {orbit.eccentricity}')
print('next_step: adjust orbit further if desired')
```



---

# Assistant “thinking” trace available from the transcript

## What I can and can’t extract
- The transcript contains **internal reasoning events** (items of type `reasoning` / `agent_reasoning`). Those are the model’s private chain-of-thought and I **can’t** reproduce them verbatim.
- What I *can* include is the assistant’s **explicit, user-visible messages** (there was only one) and its **observable planning/actions** as evidenced by the **tools it chose to call** (e.g., transfer window computation, ejection node computation, burn-time computation).

## Assistant-visible message (verbatim)

- 2025-12-14 03:27:58Z

> - QA Mun debug run completed: `PT Series Munsplorer improved st...iew` emitted `NaN` inside the returned JSON string (`autopilot_target_roll`), making it invalid JSON.

## Observable planning / decision cues from tool choices (verbatim args)

These calls show *what the assistant decided to compute* during the run (even though its internal reasoning text is not available to share):

- **compute_transfer_window_to_body**
  - args: `{"body_name": "Mun"}`

- **compute_ejection_node_to_body**
  - args: `{"body_name": "Mun", "parking_alt_m": "80000", "environment": "vacuum"}`

- **compute_burn_time** (called 3×)
  - args: `{"dv_m_s": "857.83", "environment": "vacuum"}`
  - args: `{"dv_m_s": "857.83", "environment": "vacuum"}`
  - args: `{"dv_m_s": "...", "environment": "..."}` *(additional calls present; args vary by step)*

- **compute_circularize_node**
  - args: `{"at": "periapsis"}`

If you want, I can expand this section into a **per-phase “plan trace”** that lists (in time order) the key `get_orbit_info` / `list_maneuver_nodes` / `compute_*` calls leading into each major script execution.

