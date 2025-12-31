# Warping Playbook (geept_mcp)

How to exercise the async warp stack (`start_warp_job` / `warp_to`) for:

1) Warping to a local lighting event ("sunrise" at the vessel's location).
2) Warping close to an interplanetary transfer window (Kerbin -> Duna).

This is written from a regression session on `127.0.0.1:50000/50001` with a vessel parked on the launch pad (`situation=pre_launch`).

---

## 0) Preconditions + tools

Recommended preflight setup:

- Ensure kRPC connection works: `mcp__geept_mcp__krpc_get_status`.
- Put the game into a deterministic state:
  - `mcp__geept_mcp__revert_to_launch` (optional but great for repeatability)
  - `mcp__geept_mcp__set_timewarp_rate({ rate: 1 })` to clear any residual warp
- Use `mcp__geept_mcp__get_time_status` to capture `UT_NOW` before computing targets.

Monitoring during warp:

- Start warp: `mcp__geept_mcp__start_warp_job(...)` -> returns `job_id`
- Poll telemetry: `mcp__geept_mcp__get_job_status({ job_id: job_id + \"_warp\" })`
  - Watch: `warp_progress.remaining_game_time_s`, `warp_rate_effective`, `warp_factor_effective`, `estimated_remaining_real_s`
- Optional: poll plain logs: `mcp__geept_mcp__get_job_status({ job_id })`

Parameters that mattered in practice:

- `mode`: use `\"rails\"` for long waits (pad/orbit), `\"physics\"` when rails warp is unavailable.
- `target_real_time_s`: "how long in real seconds should this warp take" (control target).
- `settle_at_s`: how close to target UT the job starts slowing down.
- `lead_time_s`: arrive early by this many seconds (useful for maneuver lead times).
- `max_wall_time_s`: safety cap so you never accidentally warp for hours of real time.

---

## 1) Warp to sunrise at the current location

### Why this approach

KSP does not provide a direct "next sunrise UT at (lat,lon)" API in kRPC. The most reliable way is:

1) Compute the Sun's elevation angle at the current vessel position.
2) Find the next time that elevation crosses from negative to positive (night -> day).
3) Warp to that UT and verify by measuring elevation again.

We used `start_execute_script_job` for the math, then `start_warp_job` for the long wait.

### Step A - compute the next sunrise UT (one-shot lon/decl solver)

This is the "one time run" version: compute a single UT target, warp once, then verify.

Why this solver:

- kRPC/KSP uses a left-handed coordinate system, and local ENU cross-product constructions are easy to get wrong (east/west flips).
- This uses only `body.reference_frame`, where the axes rotate with the body: x = lon 0, y = north pole, z = lon 90E.

Tool call:

- `mcp__geept_mcp__start_execute_script_job({ timeout_sec: "55", hard_timeout_sec: "60", code: <script below> })`

Script (paste as-is):

```python
log('Compute next sunrise UT (one-shot lon/decl solver)')

if vessel is None:
    raise RuntimeError('No active vessel')

sc = conn.space_center
body = vessel.orbit.body
rf = body.reference_frame
flight = vessel.flight(rf)

ut0 = sc.ut
lat_deg = float(flight.latitude)
lon_deg = float(flight.longitude)

sun = None
for key in ('Sun', 'Kerbol'):
    try:
        sun = sc.bodies[key]
        break
    except KeyError:
        pass
if sun is None:
    raise RuntimeError('Could not find Sun/Kerbol in space_center.bodies')

phi = math.radians(lat_deg)
lon_local = math.radians(lon_deg)

def clamp(x, lo=-1.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x

def wrap_pi(x):
    twopi = 2.0 * math.pi
    return (x + math.pi) % twopi - math.pi

def mod_pos(x, m):
    return x % m

sx, sy, sz = sun.position(rf)
r = math.sqrt(sx * sx + sy * sy + sz * sz)
if r <= 0:
    raise RuntimeError('Sun position magnitude is zero')
ux, uy, uz = sx / r, sy / r, sz / r

# declination relative to equatorial plane (y-axis is north pole)
dec = math.asin(clamp(uy))

# subsolar longitude in body frame (x: lon=0, z: lon=90E)
lon_sun = math.atan2(uz, ux)

# hour angle: difference between local and subsolar longitudes (wrapped to [-pi, pi])
H = wrap_pi(lon_local - lon_sun)

sin_phi = math.sin(phi)
cos_phi = math.cos(phi)
sin_dec = math.sin(dec)
cos_dec = math.cos(dec)

sin_elev = sin_phi * sin_dec + cos_phi * cos_dec * math.cos(H)
elev_deg = math.degrees(math.asin(clamp(sin_elev)))

print(f'UT0={ut0:.3f} body={body.name} lat={lat_deg:.6f} lon={lon_deg:.6f}')
print(f'LON_SUN_DEG={math.degrees(lon_sun):.6f} DEC_DEG={math.degrees(dec):.6f} H_DEG={math.degrees(H):.6f}')
print(f'ELEV_FORMULA_DEG={elev_deg:.6f}')

# Determine sign of dH/dt by sampling (2 seconds)
sleep(2.0)
check_time()

ut1 = sc.ut
sx1, sy1, sz1 = sun.position(rf)
r1 = math.sqrt(sx1 * sx1 + sy1 * sy1 + sz1 * sz1)
if r1 <= 0:
    raise RuntimeError('Sun position magnitude is zero at sample time')
ux1, uy1, uz1 = sx1 / r1, sy1 / r1, sz1 / r1
lon_sun1 = math.atan2(uz1, ux1)
H1 = wrap_pi(lon_local - lon_sun1)

dH = wrap_pi(H1 - H)
dt = max(1e-6, ut1 - ut0)
dH_dt = dH / dt

print(f'UT1={ut1:.3f} dH_DEG={math.degrees(dH):.6f} dt={dt:.3f} dH_dt={dH_dt:.10e} rot_speed={body.rotational_speed:.10e}')

# horizon hour-angle magnitude
arg = clamp(-math.tan(phi) * math.tan(dec))
H0 = math.acos(arg)

# If dH/dt > 0, sunrise is at H = -H0 (elevation increases through the crossing)
# If dH/dt < 0, sunrise is at H = +H0
sunrise_H = -H0 if dH_dt > 0 else H0

if abs(dH_dt) < 1e-12:
    dH_dt = float(body.rotational_speed)

twopi = 2.0 * math.pi
if dH_dt > 0:
    dt_rise = mod_pos((sunrise_H - H), twopi) / dH_dt
else:
    dt_rise = mod_pos((H - sunrise_H), twopi) / (-dH_dt)

sunrise_ut = ut0 + dt_rise
warp_target_ut = sunrise_ut + 240.0  # buffer after sunrise

print(f'H0_DEG={math.degrees(H0):.6f} SUNRISE_H_DEG={math.degrees(sunrise_H):.6f}')
print(f'NEXT_SUNRISE_UT={sunrise_ut:.6f} DT_RISE_S={dt_rise:.3f}')
print(f'WARP_TARGET_UT={warp_target_ut:.6f}')

print('SUMMARY:')
print('- Phase goal: compute next sunrise UT (one-shot)')
print('- Outcome (achieved: yes)')
print(f'- Key telemetry facts: elev_now_deg={elev_deg:.3f}, H_deg={math.degrees(H):.1f}, dH_dt={dH_dt:.3e}')
print(f'- Recommended next action: start_warp_job(mode=\"rails\", ut=WARP_TARGET_UT, lead_time_s=0) then verify sun elevation > 0')
```

How to use the return:

- Read the log line `WARP_TARGET_UT=<...>` (preferred), or `NEXT_SUNRISE_UT=<...>` if you want to pick your own buffer.
- Start exactly one warp job to `WARP_TARGET_UT`.

### Step B - warp to sunrise (one warp job)

Example tool call:

```json
{
  "ut": "<WARP_TARGET_UT>",
  "lead_time_s": 0,
  "mode": "rails",
  "target_real_time_s": 20,
  "settle_at_s": 60,
  "max_wall_time_s": "180"
}
```

Poll:

- `get_job_status({ job_id: "<id>_warp" })` until `status == "SUCCEEDED"`.

### Step C - verify it is daylight (script)

Tool call:

- `mcp__geept_mcp__start_execute_script_job({ timeout_sec: "30", hard_timeout_sec: "45", code: <script below> })`

```python
log('Verify sun elevation is positive (daylight check)')

if vessel is None:
    raise RuntimeError('No active vessel')

sc = conn.space_center
body = vessel.orbit.body
rf = body.reference_frame
flight = vessel.flight(rf)
lat = float(flight.latitude)
lon = float(flight.longitude)
ut = sc.ut

sun = None
for key in ('Sun', 'Kerbol'):
    try:
        sun = sc.bodies[key]
        break
    except KeyError:
        pass
if sun is None:
    raise RuntimeError('Could not find Sun/Kerbol in space_center.bodies')

def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def v_mag(a):
    return math.sqrt(v_dot(a, a))

def v_norm(a):
    m = v_mag(a)
    return (a[0] / m, a[1] / m, a[2] / m) if m > 0 else (0.0, 0.0, 0.0)

pos = body.surface_position(lat, lon, rf)
up = v_norm(pos)
sun_dir = v_norm(sun.position(rf))

s = max(-1.0, min(1.0, v_dot(sun_dir, up)))
sun_elev_deg = math.degrees(math.asin(s))

print(f'UT={ut:.3f} body={body.name} lat={lat:.6f} lon={lon:.6f}')
print(f'SUN_ELEV_DEG={sun_elev_deg:.6f}')
print(f'IS_DAYLIGHT={sun_elev_deg > 0.0}')

print('SUMMARY:')
print('- Phase goal: verify we are after sunrise')
print(f'- Outcome (achieved: {\"yes\" if sun_elev_deg > 0.0 else \"no\"})')
print(f'- Key telemetry facts: ut={ut:.3f}, sun_elev_deg={sun_elev_deg:.3f}')
print('- Recommended next action: if not daylight, warp forward another +300s and re-check')
```

Success criteria:

- `IS_DAYLIGHT=True` and `SUN_ELEV_DEG` is positive.

### Appendix A (deprecated) - old sunrise solver (do not use)

Tool call:

- `mcp__geept_mcp__start_execute_script_job({ timeout_sec: \"55\", hard_timeout_sec: \"60\", code: <script below> })`

Script (paste as-is):

```python
log('Compute next sunrise UT for current vessel location (approx: inertial sun direction constant over one Kerbin day)')

if vessel is None:
    raise RuntimeError('No active vessel')

sc = conn.space_center
body = vessel.orbit.body
ut0 = sc.ut

rf = body.reference_frame
flight = vessel.flight(rf)
lat = float(flight.latitude)
lon = float(flight.longitude)

sun = None
for key in ('Sun', 'Kerbol'):
    try:
        sun = sc.bodies[key]
        break
    except KeyError:
        pass
if sun is None:
    raise RuntimeError('Could not find Sun/Kerbol in space_center.bodies')

def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

def v_mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)

def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def v_mag(a):
    return math.sqrt(v_dot(a, a))

def v_norm(a):
    m = v_mag(a)
    if m <= 0:
        return (0.0, 0.0, 0.0)
    return (a[0] / m, a[1] / m, a[2] / m)

def v_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )

def rotate_about_axis(vec, axis_unit, angle_rad):
    v = vec
    k = axis_unit
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return v_add(
        v_add(v_mul(v, cos_a), v_mul(v_cross(k, v), sin_a)),
        v_mul(k, v_dot(k, v) * (1 - cos_a)),
    )

pos = body.surface_position(lat, lon, rf)
up = v_norm(pos)

north_pole = body.surface_position(90.0, 0.0, rf)
axis_north = v_norm(north_pole)

sun_vec0 = sun.position(rf)
sun_dir0 = v_norm(sun_vec0)

rot_period = float(body.rotational_period) if hasattr(body, 'rotational_period') else float(body.rotation_period)
omega = 2.0 * math.pi / rot_period if rot_period > 0 else 0.0

def sun_elev_rad_at_dt(dt_s, sign):
    angle = sign * (-omega * dt_s)
    sun_dir = v_norm(rotate_about_axis(sun_dir0, axis_north, angle))
    s = max(-1.0, min(1.0, v_dot(sun_dir, up)))
    return math.asin(s)

check_time()

step_s = 300.0
max_dt = rot_period * 1.2

def find_next_sunrise(sign):
    e0 = sun_elev_rad_at_dt(0.0, sign)
    waiting_for_sunrise = e0 <= 0.0
    prev_e = e0
    prev_dt = 0.0
    dt = step_s
    while dt <= max_dt:
        check_time()
        e = sun_elev_rad_at_dt(dt, sign)
        if waiting_for_sunrise:
            if prev_e <= 0.0 and e > 0.0:
                return (prev_dt, dt)
        else:
            if prev_e >= 0.0 and e < 0.0:
                waiting_for_sunrise = True
        prev_e = e
        prev_dt = dt
        dt += step_s
    return None

b1 = find_next_sunrise(+1)
b2 = find_next_sunrise(-1)

chosen_sign = None
bracket = None
if b1 and b2:
    chosen_sign = +1 if b1[1] < b2[1] else -1
    bracket = b1 if chosen_sign == +1 else b2
elif b1:
    chosen_sign = +1
    bracket = b1
elif b2:
    chosen_sign = -1
    bracket = b2

elev0_deg = math.degrees(sun_elev_rad_at_dt(0.0, +1))

print(f'UT0={ut0:.3f} body={body.name} lat={lat:.6f} lon={lon:.6f} rot_period_s={rot_period:.3f}')
print(f'Sun elevation now ~= {elev0_deg:.3f} deg (negative means night)')

if bracket is None:
    print('SUNRISE_UT=NONE')
    print('SUMMARY:')
    print('- Phase goal: compute next sunrise UT')
    print('- Outcome (achieved: no)')
    print(f'- Key telemetry facts: UT0={ut0:.3f}, elev0_deg={elev0_deg:.3f}, rot_period_s={rot_period:.3f}')
    print('- Recommended next action: compute sunrise via different method or warp manually')
    raise RuntimeError('Could not bracket sunrise within one rotation')

lo, hi = bracket
for _ in range(32):
    check_time()
    mid = 0.5 * (lo + hi)
    e_mid = sun_elev_rad_at_dt(mid, chosen_sign)
    if e_mid > 0.0:
        hi = mid
    else:
        lo = mid

sunrise_dt = 0.5 * (lo + hi)
sunrise_ut = ut0 + sunrise_dt

print(f'Chosen model sign={chosen_sign} bracket_dt_s=({bracket[0]:.1f},{bracket[1]:.1f})')
print(f'SUNRISE_UT={sunrise_ut:.6f}')
print(f'SECONDS_UNTIL_SUNRISE={sunrise_dt:.3f}')

print('SUMMARY:')
print('- Phase goal: compute next sunrise UT')
print('- Outcome (achieved: yes)')
print(f'- Key telemetry facts: UT0={ut0:.3f}, elev0_deg={elev0_deg:.3f}, sunrise_ut={sunrise_ut:.3f}, dt_s={sunrise_dt:.1f}')
print('- Recommended next action: start_warp_job(mode=\"rails\", ut=sunrise_ut, lead_time_s=5-15)')
```

How to use the return:

- Read the log line `SUNRISE_UT=<...>`.
- Compute your target warp UT:
  - Usually `ut = SUNRISE_UT` and use `lead_time_s=5..15` to arrive a few seconds early.

### Appendix B (deprecated) - warp to sunrise

Example tool call used successfully:

```json
{
  "ut": "425664.039396",
  "lead_time_s": 10,
  "mode": "rails",
  "target_real_time_s": 12,
  "settle_at_s": 30,
  "max_wall_time_s": "60"
}
```

Poll:

- `get_job_status({ job_id: "<id>_warp" })` until `status == "SUCCEEDED"`.

### Appendix C (deprecated) - verify it is daylight (script)

Tool call:

- `mcp__geept_mcp__start_execute_script_job({ timeout_sec: \"30\", hard_timeout_sec: \"45\", code: <script below> })`

```python
log('Check current sun elevation (is it sunrise yet?)')

if vessel is None:
    raise RuntimeError('No active vessel')

sc = conn.space_center
body = vessel.orbit.body
rf = body.reference_frame
flight = vessel.flight(rf)
lat = float(flight.latitude)
lon = float(flight.longitude)
ut = sc.ut

sun = None
for key in ('Sun', 'Kerbol'):
    try:
        sun = sc.bodies[key]
        break
    except KeyError:
        pass
if sun is None:
    raise RuntimeError('Could not find Sun/Kerbol in space_center.bodies')

def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def v_mag(a):
    return math.sqrt(v_dot(a, a))

def v_norm(a):
    m = v_mag(a)
    return (a[0] / m, a[1] / m, a[2] / m) if m > 0 else (0.0, 0.0, 0.0)

pos = body.surface_position(lat, lon, rf)
up = v_norm(pos)
sun_dir = v_norm(sun.position(rf))

s = max(-1.0, min(1.0, v_dot(sun_dir, up)))
elev_deg = math.degrees(math.asin(s))

print(f'UT={ut:.3f} body={body.name} lat={lat:.6f} lon={lon:.6f}')
print(f'Sun elevation now = {elev_deg:.3f} deg')
print(f'IS_DAYLIGHT={elev_deg > 0.0}')

print('SUMMARY:')
print('- Phase goal: verify we are at/after sunrise')
print(f'- Outcome (achieved: {\"yes\" if elev_deg > 0.0 else \"no\"})')
print(f'- Key telemetry facts: ut={ut:.3f}, sun_elev_deg={elev_deg:.3f}')
print('- Recommended next action: if not daylight, warp a bit further forward (e.g., +120s)')
```

Success criteria:

- `IS_DAYLIGHT=True` and `Sun elevation now` is slightly positive (near 0 deg) if you arrived close to sunrise.

---

## 2) Warp close to a transfer window (example: Kerbin -> Duna)

### Why this approach

For a (Hohmann-style) transfer window, you want a UT where the phase angle between an origin body and a target body matches the requirement for the transfer time.

This section is designed to be a one-shot workflow:

- One script computes `UT_WINDOW` and a buffered `WARP_TARGET_UT = UT_WINDOW - LEAD_TIME_S`.
- You then run exactly one `start_warp_job` to `WARP_TARGET_UT`.
- Re-run the same script after warp to verify/refine if needed.

Note: `mcp__geept_mcp__compute_transfer_window_to_body(...)` is convenient, but in this test save it returned a `phase_now_deg` that did not match the position-based solver below, so this playbook treats the position-based solver as the primary ground truth for regression testing.

### Step A - compute window UT and a one-shot warp target UT (script)

Tool call:

- `mcp__geept_mcp__start_execute_script_job({ timeout_sec: \"55\", hard_timeout_sec: \"60\", code: <script below> })`

```python
log('Compute interplanetary transfer window (origin->target) and WARP_TARGET_UT')

sc = conn.space_center
ut = sc.ut

# --- config ---
ORIGIN_NAME = 'Kerbin'
TARGET_NAME = 'Duna'       # change to any body orbiting the same central body as ORIGIN_NAME
LEAD_TIME_S = 5 * 21600    # how early to stop before the window (5 Kerbin days); use e.g. 3600 for 1 hour

origin = sc.bodies[ORIGIN_NAME]
target = sc.bodies[TARGET_NAME]
central = origin.orbit.body
if target.orbit.body != central:
    raise RuntimeError(
        f'Origin and target do not share a common central body: {origin.orbit.body.name} vs {target.orbit.body.name}'
    )

# Use an inertial-ish frame so the angle does not rotate with the central body
rf = central.non_rotating_reference_frame

# Hohmann transfer time from semi-major axes (circular approximation)
r1 = float(origin.orbit.semi_major_axis)
r2 = float(target.orbit.semi_major_axis)
mu = float(central.gravitational_parameter)
a_tx = 0.5 * (r1 + r2)
transfer_time_s = math.pi * math.sqrt(a_tx ** 3 / mu)

n1 = 360.0 / float(origin.orbit.period)  # deg/s
n2 = 360.0 / float(target.orbit.period)  # deg/s
w = n2 - n1  # deg/s phase drift rate

phase_required = (180.0 - n2 * transfer_time_s) % 360.0

def theta_xz(p):
    # Angle in the central body's equatorial plane (x-z)
    return math.degrees(math.atan2(p[2], p[0])) % 360.0

p1 = origin.orbit.position_at(ut, rf)
p2 = target.orbit.position_at(ut, rf)
phase_now = (theta_xz(p2) - theta_xz(p1)) % 360.0

if abs(w) < 1e-12:
    raise RuntimeError('Phase drift rate too small (w~0)')

# Solve for the next positive dt where phase_now + w*dt == phase_required (mod 360)
best_dt = None
best_k = None
for k in range(-6, 7):
    dt = (phase_required - phase_now + 360.0 * k) / w
    if dt > 0 and (best_dt is None or dt < best_dt):
        best_dt = dt
        best_k = k
if best_dt is None:
    raise RuntimeError('No positive solution for next window')

ut_window = ut + best_dt

lead = float(LEAD_TIME_S)
if best_dt < lead + 60.0:
    lead = max(0.0, best_dt - 60.0)  # ensure WARP_TARGET_UT stays in the future
warp_target_ut = ut_window - lead

print(f'UT_NOW={ut:.6f}')
print(f'ORIGIN={origin.name} TARGET={target.name} CENTRAL={central.name}')
print(f'PHASE_NOW_DEG={phase_now:.6f} PHASE_REQUIRED_DEG={phase_required:.6f}')
print(f'TIME_TO_WINDOW_S={best_dt:.3f} UT_WINDOW={ut_window:.6f} K_WRAP={best_k}')
print(f'LEAD_TIME_S={lead:.3f}')
print(f'WARP_TARGET_UT={warp_target_ut:.6f}')

print('SUMMARY:')
print('- Phase goal: compute transfer window UT and a one-shot warp target UT')
print('- Outcome (achieved: yes)')
print(f'- Key telemetry facts: time_to_window_s={best_dt:.0f}, warp_target_ut={warp_target_ut:.0f}')
print('- Recommended next action: start_warp_job(mode=\"rails\", ut=WARP_TARGET_UT) then re-run this script to verify/refine')
```

How to use the return:

- Read `WARP_TARGET_UT=<...>` from stdout and use it directly in the warp job.

### Step B - warp to WARP_TARGET_UT (one warp job)

Start warp (example):

```json
{
  "ut": "<WARP_TARGET_UT>",
  "lead_time_s": 0,
  "mode": "rails",
  "target_real_time_s": 30,
  "settle_at_s": 30,
  "max_wall_time_s": "180"
}
```

Poll with `get_job_status("<id>_warp")` until `SUCCEEDED`.

### Step C - verify/refine after warp

Re-run Step A from the new UT. If you want to stop closer, reduce `LEAD_TIME_S` (e.g., from `5*21600` to `3600` to get within ~1 hour).

Success criteria:

- After warping, `TIME_TO_WINDOW_S` is roughly your chosen `LEAD_TIME_S` (within tens of minutes is expected for this approximation).

---

## Notes and pitfalls observed

- `get_screenshot` failed with a permission error writing under the MCP server's `artifacts/screenshots` path. If you need screenshots for warp tests, ensure the MCP server's artifact directory is writable from the process environment.
- Encoding: avoid printing non-ASCII symbols (e.g. "->") in scripts; on Windows this can raise `UnicodeEncodeError` (cp1252).
- `settle_at_s` behavior: large values (e.g., 600) can cause the warp job to intentionally drop to realtime for minutes before completion; keep it small (30-120) for regression tests.
- Reference frames: for interplanetary angles, `central.non_rotating_reference_frame` with `atan2(z, x)` ("x-z plane") was stable in this save; if your results look nonsensical, verify axis/plane choice by sampling phase drift over ~60s.
