from __future__ import annotations

import sys

from .mcp_context import mcp
from .executor_impl.core import (
    execute_script_impl,
    start_execute_script_job_impl,
    _run_execute_script as core_run_execute_script,
)

# Import implementation modules so their resources are registered
from .executor_impl import job_artifacts as _job_artifacts
from .executor_impl import job_tools as _job_tools
from .executor_impl import jobs as _jobs
from .executor_impl import script_jobs as _script_jobs
from .utils.krpc_helpers import DEFAULT_KRPC_ADDRESS

# Expose implementation modules under the historical mcp_server.executor_tools.*
job_artifacts = _job_artifacts
job_tools = _job_tools
jobs = _jobs
script_jobs = _script_jobs

sys.modules[__name__ + ".job_artifacts"] = _job_artifacts
sys.modules[__name__ + ".job_tools"] = _job_tools
sys.modules[__name__ + ".jobs"] = _jobs
sys.modules[__name__ + ".script_jobs"] = _script_jobs

@mcp.tool()
def start_execute_script_job(
    code: str,
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    *,
    timeout_sec: float | None = None,
    pause_on_end: bool = True,
    unpause_on_start: bool = True,
    allow_imports: bool = False,
    hard_timeout_sec: float | None = None,
) -> str:

    """
    Start a background job that runs execute_script with live log streaming.

    Script Contract:
      - Do NOT import kRPC or connect manually (unless you set allow_imports=True).
      - Injected globals: `conn`, `vessel` (may be None), `time`, `math`, `sleep(s)`, `deadline`, `check_time()`, `logging`, and `log(msg)`.
      - Use standard `print()` and/or Python `logging` (both are captured). Imports are disabled by default, but `logging` is pre-injected and allowed.
      - Always include a `SUMMARY:` block at the end (a single line or a block starting with `SUMMARY:`) so the agent can quickly understand outcomes.
      - Use bounded loops and call `check_time()` periodically; the runner enforces a hard wall-time timeout.

    Usage pattern:
        1. Call start_execute_script_job(...) to enqueue the script; capture the returned job_id.
        2. Poll get_job_status(job_id) for log/print output as the script runs (alternate checks with vessel status tools
           like get_status_overview / get_flight_snapshot to keep tabs on the rocket).
        3. If something goes wrong, immediately call cancel_job(job_id), revert/restore as needed (revert_to_launch,
           load checkpoint), then plan the next step.
        4. When the job finishes, call read_resource(result_resource) to download the same JSON payload execute_script returns.

    Operational behavior:
      - On start: best-effort unpause (unpause_on_start=true by default) so physics runs.
      - On end (success, failure, or exception): best-effort pause; includes `pre_pause_flight`
        with velocities sampled immediately before pausing so speeds are informative.
      - Soft timeout: your script should call `check_time()` inside loops; on TimeoutError
        the runner pauses and returns `ok=false` with `pre_pause_flight`.
      - Hard timeout: if `hard_timeout_sec` elapses, the parent kills the runner, pauses the
        game, and returns a minimal `diagnostics` block plus a `follow_up` hint to call
        `get_diagnostics` for a rich snapshot while the game is paused.
    """

    return start_execute_script_job_impl(
        code=code,
        address=address,
        rpc_port=rpc_port,
        stream_port=stream_port,
        name=name,
        timeout_sec=timeout_sec,
        pause_on_end=pause_on_end,
        unpause_on_start=unpause_on_start,
        allow_imports=allow_imports,
        hard_timeout_sec=hard_timeout_sec,
    )




# Expose the low-level runner for tests (monkeypatched in unit tests)
_run_execute_script = core_run_execute_script
