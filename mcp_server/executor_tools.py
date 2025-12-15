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
from .utils.json_utils import dumps as json_dumps
from .utils.krpc_helpers import DEFAULT_KRPC_ADDRESS
from .general_tools_impl import (
    connection_and_save,
    status_and_time,
    flight_and_control, 
    target_control, 
    launch_and_vessel,
    maneuver_nodes
    )

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
    allow_imports: bool = False,
    hard_timeout_sec: float | None = None,
    logging_mode = None,
) -> dict:

    """
    Start a background job that runs execute_script with live log streaming.

    Important args:
      code: Python script code to execute (see Script Contract below)
      timeout_sec: Optional soft timeout for script execution (seconds); Stops the script on `check_time()` call if time exceeded.
      hard_timeout_sec: Optional hard timeout (seconds); kills the script if exceeded at exact time.
      allow_imports: If true, allow standard library and third-party imports in the script
      logging_mode: Select predefined logging modes for common flight phases ("enum": [None, "orbital_ascent", "atmospheric_flight", "powered_descent", "rendezvous"])

    Script Contract:
      - Do NOT import kRPC or connect manually (unless you set allow_imports=True).
      - Injected globals are already present: `conn`, `vessel` (may be None), `time`, `math`, `sleep(s)`, `deadline`, `check_time()`, `logging`, and `log(msg)`.
      - Use standard `print()` and/or Python `logging` (both are captured). Imports are disabled by default, but `logging` is pre-injected and allowed.
      - Use bounded loops and call `check_time()` periodically; the runner enforces a hard wall-time timeout.

    Usage pattern:
        1. Call start_execute_script_job(...) to enqueue the script; capture the returned job_id.
        2. Poll get_job_status(job_id) for log/print output as the script runs (alternate checks with vessel status tools
           like `get_status_overview` / `get_flight_snapshot` to keep tabs on the rocket).
        3. If something goes wrong, immediately call cancel_job(job_id), revert/restore as needed (revert_to_launch,
           load checkpoint), then plan the next step.
        4. When the job finishes, call read_resource(result_resource) to download the same JSON payload execute_script returns.

    Operational behavior:
      - On start: best-effort unpause so physics runs.
      - On end (success, failure, or exception): best-effort pause.
      - Soft timeout: your script should call `check_time()` inside loops; on TimeoutError
        the runner pauses and returns `ok=false` with `pre_pause_flight`.
      - Hard timeout: if `hard_timeout_sec` elapses, the parent kills the runner, pauses the
        game, and returns a minimal `diagnostics` block plus a `follow_up` hint to call
        `get_diagnostics` for a rich snapshot while the game is paused.
    """

    if logging_mode == 'orbital_ascent':
        log_call = "_asc"
    elif logging_mode == 'atmospheric_flight':
        log_call = "_atm"
    elif logging_mode == 'powered_descent': 
        log_call = "_des"
    elif logging_mode == 'rendezvous':
        log_call = "_ren"
    else:
        log_call = ""

    res = start_execute_script_job_impl(
        code=code,
        address=address,
        rpc_port=rpc_port,
        stream_port=stream_port,
        name=name,
        timeout_sec=timeout_sec,
        allow_imports=allow_imports,
        hard_timeout_sec=hard_timeout_sec,
    )

    # Preserve the canonical internal id separately; some callers append a suffix
    # to request enhanced logging/monitoring during get_job_status polling.
    canonical_job_id = res.get("job_id")
    res["canonical_job_id"] = canonical_job_id
    res["job_id_suffix"] = log_call
    if isinstance(canonical_job_id, str) and log_call:
        res["job_id"] = canonical_job_id + log_call

    # Fallback: return as-is if an unexpected type shows up (maintains prior behavior without crashing).
    return json_dumps(res)

# Expose the low-level runner for tests (monkeypatched in unit tests)
_run_execute_script = core_run_execute_script

# Direct executive action tools 🔌-------------------------------------------------------------------

# Save/load and flight reset tools ----------------------------------------------------------------

@mcp.tool()
def revert_to_launch(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Revert the current flight to launch (KSP's Revert to Launch).

When to use:
  - Reset a mission after a failed ascent, returning the rocket to the launch pad.

Notes:
  - This calls SpaceCenter.revert_to_launch(). If revert is disabled or not available in the current scene,
    returns a message indicating it cannot revert."""
    return connection_and_save.revert_to_launch(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def save_llm_checkpoint(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, tag: str | None = None, prefix: str = 'LLM') -> str:
    """Save a game checkpoint under a unique LLM-namespaced name.

Behavior:
  - Generates a unique save name like: "<prefix>_YYYYmmddTHHMMSSZ_<id>".
  - Uses SpaceCenter.save(name) instead of quicksave() to avoid overwriting the user's quicksave.

Args:
  tag: Optional label included in the generated name for readability.
  prefix: Namespace prefix (default "LLM").

Returns JSON: { ok, save_name, note? }."""
    return connection_and_save.save_llm_checkpoint(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout, tag=tag, prefix=prefix)


@mcp.tool()
def load_llm_checkpoint(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, save_name: str = '', require_llm_prefix: bool = True, pause_after: bool = True) -> str:
    """Load a previously saved checkpoint by name using SpaceCenter.load(name).

Safeguards:
  - By default, only loads names starting with "LLM_" (set require_llm_prefix=false to override).

Returns JSON: { ok, loaded?: save_name, error? }."""
    return connection_and_save.load_llm_checkpoint(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout, save_name=save_name, require_llm_prefix=require_llm_prefix, pause_after=pause_after)

@mcp.tool()
def quicksave(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Save a quicksave (SpaceCenter.quicksave()).

Notes:
  - This overwrites the game's single quicksave slot. Prefer save_llm_checkpoint to create namespaced saves."""
    return connection_and_save.quicksave(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def quickload(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, pause_after: bool = True) -> str:
    """Load from the quicksave slot (SpaceCenter.quickload()).

Notes:
  - Prefer load_llm_checkpoint for named saves to avoid conflict with a player's quicksave."""
    return connection_and_save.quickload(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout, pause_after=pause_after)

# 🛰️⏱️ Status & time 🛰️⏱️ ---------------------------------------------------------------------

@mcp.tool()
def set_timewarp_rate(address: str = DEFAULT_KRPC_ADDRESS, rate: float = 1.0, mode: str | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Set the current timewarp rate (and optionally switch warp mode).

When to use:
  - Adjust how fast KSP advances time when waiting on long events.
  - Reset the time speed after a fire-and-forget warp_to call once you verify UT with get_time_status.

Args:
  rate: Desired timewarp rate; 1.0 is realtime, >1 is warp (0 stops time).
  mode: Optional name of the warp mode to select ('physics', 'rails', 'none').

Returns:
  Human-readable status string describing what was set or why the change failed."""
    return status_and_time.set_timewarp_rate(address=address, rate=rate, mode=mode, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def set_sas_mode(address: str = DEFAULT_KRPC_ADDRESS, mode: str | None = None, enable_sas: bool = True, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Set SAS on/off and select an SAS hold mode.

    Args:
      mode: One of the SAS modes (stability_assist, prograde, retrograde, normal, anti_normal,
        radial, anti_radial, target, anti_target, maneuver). Case- and dash/underscore-insensitive.
      enable_sas: If true, toggle SAS on before setting the mode.

    Returns:
      Human-readable status string (success or error). Includes whether the requested orientation was aligned.

    Notes:
      - Best-effort unpauses, lets SAS align, and then re-applies the pause so you can change heading while the game starts paused.
      - The tool always pauses the game after alignment so navigation stays predictable even if you were running unpaused."""
    return flight_and_control.set_sas_mode(address=address, mode=mode, enable_sas=enable_sas, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

# 🎯🛰️ Target control 🎯🛰️ ---------------------------------------------------------------------


@mcp.tool()
def set_target_body(address: str = DEFAULT_KRPC_ADDRESS, body_name: str | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Set the active vessel's target body (also tries SpaceCenter.target_body).

Args:
  body_name: Exact body name (e.g., 'Mun')

Returns:
  Human‑readable status string or an error if not found."""
    return target_control.set_target_body(address=address, body_name=body_name, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def set_target_vessel(address: str = DEFAULT_KRPC_ADDRESS, vessel_name: str | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Set the active vessel's target vessel by name (case‑insensitive). Chooses nearest if multiple.
Also attempts to set SpaceCenter.target_vessel.

Args:
  vessel_name: Exact or case‑insensitive vessel name

Returns:
  Human‑readable status string or error if not found."""
    return target_control.set_target_vessel(address=address, vessel_name=vessel_name, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def clear_target(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Clear target_docking_port, target_vessel, and target_body if set.

Returns:
  Human‑readable status string: 'Cleared target.' or 'No target to clear.'"""
    return target_control.clear_target(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def launch_vessel(address: str = DEFAULT_KRPC_ADDRESS, craft_directory: str = 'VAB', name: str | None = None, launch_site: str = 'LaunchPad', recover: bool = True, crew: list[str] | None = None, flag_url: str = '', rpc_port: int = 50000, stream_port: int = 50001, conn_name: str | None = None, timeout: float = 10.0) -> str:
    """Launch a saved vessel (.craft) to a site via SpaceCenter.launch_vessel.

Args:
  craft_directory: "VAB" or "SPH"
  name: Craft filename without ".craft" (must exist in the save's Ships/<dir> folder)
  launch_site: "LaunchPad" or "Runway"
  recover: If true, recover an existing vessel on the site before launch
  crew: Optional list of Kerbal names to assign
  flag_url: Optional asset URL for mission flag

Returns JSON: { ok, active_vessel?, error? }."""
    return launch_and_vessel.launch_vessel(address=address, craft_directory=craft_directory, name=name, launch_site=launch_site, recover=recover, crew=crew, flag_url=flag_url, rpc_port=rpc_port, stream_port=stream_port, conn_name=conn_name, timeout=timeout)

# 🧭🧮 Maneuver nodes 🧭🧮 ---------------------------------------------------------------------

@mcp.tool()
def set_maneuver_node(address: str = DEFAULT_KRPC_ADDRESS, ut: float | None = None, prograde: float = 0.0, normal: float = 0.0, radial: float = 0.0, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Create a maneuver node at a specific UT with given vector components.

    When to use:
      - Apply a proposed burn from compute_* helpers to the game.
      - LLM: After creating the node, set SAS to target via set_sas_mode before executing the burn.

    Args:
      ut: Universal time for the node
      prograde: Prograde component (m/s)
      normal: Normal component (m/s)
  radial: Radial component (m/s)

Returns:
  JSON echo of the created node parameters."""
    return maneuver_nodes.set_maneuver_node(address=address, ut=ut, prograde=prograde, normal=normal, radial=radial, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def update_maneuver_node(address: str = DEFAULT_KRPC_ADDRESS, node_index: int = 0, ut: float | None = None, prograde: float | None = None, normal: float | None = None, radial: float | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Edit an existing maneuver node (default: first node).

Args:
  node_index: 0‑based index (default: 0)
  ut/prograde/normal/radial: Components to update (None to leave unchanged)

Returns:
  JSON echo of the updated node: { index, ut, prograde, normal, radial }."""
    return maneuver_nodes.update_maneuver_node(address=address, node_index=node_index, ut=ut, prograde=prograde, normal=normal, radial=radial, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)


@mcp.tool()
def delete_maneuver_nodes(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """Remove all maneuver nodes for the active vessel.

When to use:
  - Cleanup after executing nodes or starting a new plan.

Returns:
  Human‑readable status string with count removed."""
    return maneuver_nodes.delete_maneuver_nodes(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)

@mcp.tool()
def warp_to(address: str = DEFAULT_KRPC_ADDRESS, ut: float | None = None, lead_time_s: float = 0.0, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Best‑effort warp‑to.

    When to use:
      - Warp to a node or event time with optional lead time.

    Args:
      ut: Target universal time to arrive at
      lead_time_s: Seconds to arrive before UT (e.g., half burn time)

    Returns:
      Human-readable status string, or a message if unsupported.

    Notes:
      - This tool starts a background warp job and returns immediately with a job id in the message.
      - Poll get_job_status(job_id) for progress; cancel_job(job_id) will attempt to reset warp back to realtime.
      - **Important**: Rails warps will not work in atmosphere; the job will fail fast with a clear error.
    """
    return maneuver_nodes.warp_to(address=address, ut=ut, lead_time_s=lead_time_s, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout)
# TODO: We should have two warp tools, one to warp to specific time and one to warp to maneuver node.
