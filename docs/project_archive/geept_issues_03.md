# GeePT MCP Issues

## Issue 1: Hard timeout during ascent script (asyncio ƒ?oException in callbackƒ?? spam)
- **Summary**: Commander, the ascent script launched through `start_execute_script_job` never returned on its ownƒ?"after 240ƒ?_s the hard timeout forcibly killed the job even though the craft was still throttling toward orbit, and the log stream was peppered with repeated `Exception in callback` messages from Pythonƒ?Ts asyncio machinery.
- **Tool**: `start_execute_script_job`
- **Arguments**: `{"address": "127.0.0.1", "rpc_port": 50000, "stream_port": 50001, "code": "<Kerbal ascent loop (see job params)", "timeout_sec": 180.0, "hard_timeout_sec": 240.0, "allow_imports": false, "unpause_on_start": true}`
- **Return**: Job reported `status: SUCCEEDED`, but `result.ok = false` because `error: {"message": "Hard timeout reached", "type": "TimeoutError"}` and `stderr` ended with `TimeoutExpired: hard timeout reached; process killed`. The transcript also shows the autoloop logging `ASCENT`/`LOOP` events and the repeated `ERROR Exception in callback` lines in stderr during each `get_job_status` poll.
- **Steps to Reproduce**:
  1. Start from the current ƒ?oPT Series Munsplorer improved stagingƒ?? craft on Kerbin (any ascent phase).
  2. Call `start_execute_script_job` with the ascent loop script that throttles to apo ƒ% 90ƒ?_km / peri ƒ% 70ƒ?_km and logs every 6ƒ?_s.
  3. Monitor until the hard timeout fires (~240ƒ?_s) while the vessel is still climbing; Observe the `TimeoutExpired` shutdown alongside streaming `Exception in callback` entries.
- **Observed behavior**: After ~240ƒ?_s the tool kills the script and leaves the craft still escaping Kerbin, log spam shows repeated `Exception in callback` stack traces from `asyncio.base_events.py`, and there is no clean `SUMMARY:` output. The diagnostics snapshot at pause shows periapsis ~71ƒ?_km and apoapsis wildly negative (escape status), indicating the orbit condition never completed.
- **Expected behavior**: The scripted loop should exit once the target apo/peri is reached (and return a tidy `SUMMARY:`), or at least fail gracefully if it canƒ?Tt reach the target, without relying on a hard timeout. The repeated asyncio ƒ?oException in callbackƒ?? logs should not flood the stream while the job runs successfully.
- **Screenshot**: ![Issue 1 (hard timeout during ascent)](artifacts/screenshots/issue1.png)
- **Additional info**: `get_diagnostics` after failure confirms the vessel was at ~453ƒ?_km altitude, throttle 100%, and still burning; stage events logged two stage events before timeout, so the vehicle was executing normally except for the script never exiting.

## Issue 2: Energy stabilization execute_script job never yields summary while spamming `Exception in callback`
- **Summary**: Commander, the energy-stabilization loop never reached a terminating condition even though the vessel was clearly escaping Kerbin, and each `get_job_status` poll showed `Exception in callback` tracebacks from `asyncio.base_events`, forcing me to cancel the job (while `error: Need to regain control to continue mission planning` was delivered) before we could continue.
- **Tool**: `execute_script`
- **Arguments**: `{"address": "127.0.0.1", "rpc_port": 50000, "stream_port": 50001, "code": "<loop that throttles at 0.5, logs orbit stats, and exits when apoapsis/semimajor axis become positive>", "timeout_sec": 90.0, "hard_timeout_sec": 120.0, "allow_imports": false, "unpause_on_start": true}`
- **Return**: Job status `CANCELLED` with `error: Need to regain control to continue mission planning`; logs show repeated `LOG LOOP: ...` entries plus the same `ERROR Exception in callback` stack trace recorded near the beginning of the run, and no `SUMMARY:` block was emitted because the script was interrupted manually.
- **Steps to Reproduce**:
  1. Start from the PT Series Munsplorer on an ascent trajectory with an unclosed Kerbin orbit (apoapsis negative).
  2. Call `execute_script` with the stabilization loop that logs orbit stats every 5 s while keeping throttle at 0.5 and awaiting the orbit to close.
  3. Watch the tool log show `Exception in callback` spam repeatedly, never emit a `SUMMARY:`, and never reach a stabilized orbit despite the craft escaping Kerbin; eventually the job must be canceled to regain control.
- **Observed behavior**: `execute_script` keeps streaming telemetry without ever satisfying its exit condition, the stderr log is flooded with `Exception in callback` stack traces from `asyncio` during each poll, and the job finally reports `error: Need to regain control to continue mission planning` once cancelled.
- **Expected behavior**: The script should either exit cleanly when the positive apoapsis condition is met or fail gracefully if the orbit cannot be closed; it should not emit repeated `Exception in callback` errors while running, and the returned payload should include the `SUMMARY:` block so we can automatically plan the next step.
- **Screenshot**: ![Issue 2 (energy stabilization blocking)](artifacts/screenshots/issue2.png)
- **Additional info**: The diagnostics snapshot after cancellation shows the vessel at ~725 km altitude, apoapsis still negative, periapsis ~77 km, and throttle still at 0.5, proving the orbit never stabilized while the job loop never concluded.
