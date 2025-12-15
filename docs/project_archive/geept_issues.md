# geept_mcp issues (debug notes)

This file documents tool-call issues observed during an orbital-ascent test run from the Kerbin launch pad (localhost / kRPC `50000/50001`).

Screenshots are saved under `artifacts/screenshots/` with filenames matching the issue number.

---

## Issue 001 — `start_execute_script_job` returns a `job_id` with a suffix, but `get_job_status` reports a different `job_id`

**Screenshot:** `artifacts/screenshots/issue_001.png`

**Summary**
- `start_execute_script_job` returned a `job_id` ending with a suffix (example: `_asc`), while `get_job_status` later reported the `job_id` without that suffix.
- This is confusing for users, and it makes it unclear which identifier is canonical for later calls (polling / cancellation / artifact lookup).

**Tool called**
- `mcp__geept_mcp__start_execute_script_job`

**Arguments**
```json
{
  "address": "127.0.0.1",
  "rpc_port": 50000,
  "stream_port": 50001,
  "name": "GeePT",
  "logging_mode": "orbital_ascent",
  "timeout_sec": "55",
  "hard_timeout_sec": "58",
  "unpause_on_start": true,
  "pause_on_end": true
}
```

**Script code used**
```python
# GeePT: Ascent to target apoapsis (~155 km)
# Contract: uses injected conn/vessel/sleep/check_time/log

sc = conn.space_center
v = vessel
body = v.orbit.body
flight = v.flight(body.reference_frame)

TARGET_APO_M = 155_000.0
MAX_Q_PA = 20_000.0

print(f"INIT: vessel={v.name} situation={v.situation} body={body.name}")
print(f"INIT: stage={v.control.current_stage} mass_kg={v.mass:.1f}")

# Configure autopilot
ap = v.auto_pilot
ap.engage()
ap.target_roll = 0.0
ap.target_pitch_and_heading(90.0, 90.0)

# Stabilize controls
v.control.sas = True
v.control.rcs = False
v.control.throttle = 1.0

# Launch
print("ACTION: countdown")
for t in [3, 2, 1]:
    check_time()
    print(f"T-{t}...")
    sleep(0.5)

print("ACTION: activate stage (launch)")
v.control.activate_next_stage()
sleep(0.2)

# Helper: stage if engines are flameout/no-fuel
def should_stage_now():
    engines = v.parts.engines
    active = [e for e in engines if e.active]
    if not active:
        return False
    # If all active engines report no fuel or flameout, we stage
    return all((not e.has_fuel) or e.flameout for e in active)

# Ascent guidance loop (bounded by timeout)
print("GUIDANCE: ascent running")
last_stage = v.control.current_stage

while True:
    check_time()
    f = v.flight(body.reference_frame)
    o = v.orbit

    alt = f.mean_altitude
    apo = o.apoapsis_altitude
    q = f.dynamic_pressure
    pitch = 90.0

    # Simple gravity turn schedule
    if alt < 1_000:
        pitch = 90.0
    elif alt < 10_000:
        pitch = 90.0 - (alt - 1_000) * (35.0 / 9_000.0)   # 90 -> 55
    elif alt < 25_000:
        pitch = 55.0 - (alt - 10_000) * (25.0 / 15_000.0) # 55 -> 30
    elif alt < 50_000:
        pitch = 30.0 - (alt - 25_000) * (25.0 / 25_000.0) # 30 -> 5
    else:
        pitch = 5.0

    ap.target_pitch_and_heading(max(0.0, min(90.0, pitch)), 90.0)

    # Max-Q throttle limiter
    if q > MAX_Q_PA:
        v.control.throttle = max(0.25, v.control.throttle - 0.05)
    elif q < MAX_Q_PA * 0.7:
        v.control.throttle = min(1.0, v.control.throttle + 0.03)

    # Staging check
    if should_stage_now() and v.control.current_stage == last_stage:
        print(f"ACTION: staging (stage {v.control.current_stage} -> next)")
        v.control.throttle = 0.2
        sleep(0.2)
        v.control.activate_next_stage()
        sleep(0.6)
        v.control.throttle = 1.0
        last_stage = v.control.current_stage

    if apo >= TARGET_APO_M:
        print(f"GOAL: apoapsis reached {apo/1000:.1f} km (target {TARGET_APO_M/1000:.1f} km)")
        v.control.throttle = 0.0
        break

    # Periodic telemetry
    if int(sc.ut) % 2 == 0:
        print(f"TEL: alt={alt/1000:.1f}km apo={apo/1000:.1f}km v={f.speed:.0f}m/s q={q/1000:.1f}kPa thr={v.control.throttle:.2f} pitch_cmd={pitch:.1f}")

    sleep(0.2)

# Coast setup
v.control.throttle = 0.0
v.control.sas = True
print(f"COAST: time_to_apoapsis={v.orbit.time_to_apoapsis:.1f}s")

print("SUMMARY:")
print("Phase goal: Raise apoapsis to ~155 km")
print("Outcome (achieved: yes/no): yes")
print(f"Key telemetry: apoapsis_km={v.orbit.apoapsis_altitude/1000:.2f} periapsis_km={v.orbit.periapsis_altitude/1000:.2f} tta_s={v.orbit.time_to_apoapsis:.1f}")
print("Recommended next action: Create circularization node at apoapsis and burn to ~150 km circular orbit")
```

**Tool return (start)**
```json
{
  "job_id": "07f235190b4f42da84f38ea3ce875479_asc",
  "status": "PENDING",
  "note": "Script job started. Poll get_job_status(job_id) for live logs, and call cancel_job(job_id) + revert/load if the burn goes sideways."
}
```

**Follow-up tool called**
- `mcp__geept_mcp__get_job_status`

**Arguments**
```json
{ "job_id": "07f235190b4f42da84f38ea3ce875479_asc" }
```

**Observed return (excerpt)**
```json
{
  "job_id": "07f235190b4f42da84f38ea3ce875479",
  "status": "SUCCEEDED",
  "result_resource": "resource://jobs/07f235190b4f42da84f38ea3ce875479.json"
}
```

**Steps to reproduce**
1. Call `start_execute_script_job(...)` (any valid script).
2. Copy the returned `job_id` (noting any suffix like `_asc`).
3. Call `get_job_status(job_id)` with that value.
4. Observe that the returned payload reports a different `job_id` string (suffix removed).

**Observed issue**
- `job_id` is not stable/canonical across tool calls.

**Expected behavior**
- Either:
  - `start_execute_script_job` returns the canonical id that `get_job_status` also returns, OR
  - `get_job_status` echoes the exact id used, and any “display suffix” is provided in a separate field.

**Notes**
- This impacts downstream automation that stores and compares job ids, and it complicates `cancel_job(job_id)` behavior expectations.

---

## Issue 002 — Successful jobs emit a full traceback in logs (`start_stage_plan_job` / job runner)

**Screenshot:** `artifacts/screenshots/issue_002.png`

**Summary**
- `start_stage_plan_job` succeeded (`status: SUCCEEDED`, `ok: true`) but the job logs included a long asyncio/socket shutdown traceback, which looks like a failure to end users.

**Tool called**
- `mcp__geept_mcp__start_stage_plan_job`

**Arguments**
```json
{
  "address": "127.0.0.1",
  "rpc_port": 50000,
  "stream_port": 50001,
  "name": "GeePT",
  "environment": "vacuum",
  "timeout": 30
}
```

**Tool return (start)**
```json
{
  "job_id": "18bbcfe22ed54e5fbb4733693d0788fc",
  "status": "PENDING",
  "note": "Job started. Poll get_job_status(job_id) until it completes."
}
```

**Follow-up tool called**
- `mcp__geept_mcp__get_job_status`

**Observed return (excerpt)**
```json
{
  "status": "SUCCEEDED",
  "ok": true,
  "result_resource": "resource://jobs/18bbcfe22ed54e5fbb4733693d0788fc.json",
  "logs": [
    "…",
    "Traceback (most recent call last):",
    "… events.py …",
    "… self._sock.shutdown(socket.SHUT_RDWR) …",
    "INFO Terminating session: None",
    "…",
    "[stage_plan] Artifact saved; exposing as resource."
  ]
}
```

**Steps to reproduce**
1. Call `start_stage_plan_job(environment=\"vacuum\")`.
2. Poll `get_job_status(job_id)` until completion.
3. Inspect `logs` even when `status == \"SUCCEEDED\"`.

**Observed issue**
- The job logs contain an exception traceback despite a successful completion.

**Expected behavior**
- On success, logs should not include a traceback (or it should be clearly labeled as a handled/benign shutdown path).

**Notes**
- This looks like a resource cleanup bug or an exception that should be suppressed/handled.
- Even if benign, it will cause users to mistrust the artifact output.

---

## Issue 003 — `get_vessel_blueprint` Isp values are ambiguous/misleading compared to stage plan environment

**Screenshot:** `artifacts/screenshots/issue_003.png`

**Summary**
- `get_vessel_blueprint` reported LV-909 “Terrier” `specific_impulse_s ≈ 86.8` while the vacuum stage plan reports `combined_isp_s = 345.0` for Terrier stages.
- The blueprint response does not clearly label the Isp environment (sea level vs vacuum vs current), which can mislead mission planning.

**Tools called**
- `mcp__geept_mcp__get_vessel_blueprint`
- `mcp__geept_mcp__start_stage_plan_job` (environment = `vacuum`)

**Arguments (blueprint)**
```json
{
  "address": "127.0.0.1",
  "rpc_port": 50000,
  "stream_port": 50001,
  "name": "GeePT"
}
```

**Observed return (excerpt from blueprint)**
```json
{
  "meta": { "situation": "pre_launch" },
  "engines": [
    {
      "name": "LV-909 \"Terrier\" Liquid Fuel Engine",
      "specific_impulse_s": 86.80795288085938
    }
  ]
}
```

**Observed return (excerpt from vacuum stage plan artifact)**
```json
{
  "result": {
    "stages": [
      { "stage": 4, "combined_isp_s": 345.0 },
      { "stage": 3, "combined_isp_s": 345.0 }
    ]
  }
}
```

**Steps to reproduce**
1. On the launch pad (`situation: pre_launch`), call `get_vessel_blueprint`.
2. Call `start_stage_plan_job(environment=\"vacuum\")` and read the artifact.
3. Compare Terrier Isp values between the blueprint and the vacuum stage plan.

**Observed issue**
- The blueprint’s Isp values are not explicitly tied to an environment, and they can differ drastically from the vacuum planning numbers.

**Expected behavior**
- Blueprint should either:
  - include explicit Isp environment metadata (e.g., `isp_environment: "current"`), OR
  - provide both sea-level and vacuum Isp for each engine to avoid ambiguity, OR
  - expose “current body pressure” used for the Isp calculation in the response.

**Notes**
- The Terrier Isp value `~86.8s` matches sea-level-ish values, so the number itself may be correct; the issue is the lack of context and the ease of misinterpretation when mixed with vacuum planning outputs.

