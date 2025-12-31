from __future__ import annotations

import time
from typing import Any, Callable, Dict

from ..mcp_context import mcp
from ..utils.helper_utils import utc_timestamp
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS
from .job_artifacts import job_resource_uri, save_job_artifact
from .jobs import job_registry
from ..utils.krpc_utils import readers
from ..utils.krpc_utils.client import KRPCConnectionError, connect_to_game


def _start_reader_job(
    *,
    kind: str,
    params: Dict[str, Any],
    reader: Callable[..., Dict[str, Any]],
    reader_kwargs: Dict[str, Any] | None = None,
    ) -> str:
    reader_kwargs = reader_kwargs or {}

    def job_fn(handle):
        job_id = handle.job_id
        handle.log(
            f"[{kind}] Connecting to kRPC at {params['address']}:{params['rpc_port']}/{params['stream_port']}"
        )
        try:
            conn = connect_to_game(
                params["address"],
                rpc_port=params["rpc_port"],
                stream_port=params["stream_port"],
                name=params.get("name"),
                timeout=params["timeout"],
            )
        except KRPCConnectionError as exc:
            handle.log(f"[{kind}] Connection failed: {exc}")
            raise

        try:
            handle.log(f"[{kind}] Reader running...")
            data = reader(conn, **reader_kwargs)
            artifact_payload = {
                "job_id": job_id,
                "kind": kind,
                "requested_at": utc_timestamp(),
                "params": params,
                "result": data,
            }
            save_job_artifact(job_id, artifact_payload)
            handle.log(f"[{kind}] Artifact saved; exposing as resource.")
            handle.set_result_resource(job_resource_uri(job_id))
        finally:
            try:
                conn.close()
            except Exception:
                pass

    metadata = {"kind": kind, "params": params}
    job_id = job_registry.create_job(job_fn, metadata=metadata)
    return json_dumps(
        {
            "job_id": job_id,
            "status": "PENDING",
            "note": "Job started. Poll get_job_status(job_id) until it completes.",
        }
    )


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _safe_float(x) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _safe_int(x) -> int | None:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _default_rails_rates() -> list[float]:
    # Stock-like rails warp rates (factor 0..7).
    return [1.0, 5.0, 10.0, 50.0, 100.0, 1000.0, 10000.0, 100000.0]


def _default_physics_rates() -> list[float]:
    # Stock-like physics warp rates (factor 0..3).
    return [1.0, 2.0, 3.0, 4.0]


def _get_rate_table(sc, *, rails: bool, max_factor: int) -> list[float]:
    attr = "rails_warp_factors" if rails else "physics_warp_factors"
    rates = None
    if hasattr(sc, attr):
        try:
            raw = list(getattr(sc, attr))
            parsed = []
            for item in raw:
                val = _safe_float(item)
                if val is not None and val > 0:
                    parsed.append(val)
            if parsed:
                rates = parsed
        except Exception:
            rates = None
    if rates is None:
        rates = _default_rails_rates() if rails else _default_physics_rates()
    try:
        return rates[: max_factor + 1]
    except Exception:
        return rates


def _choose_factor(*, target_rate: float, rates: list[float]) -> int:
    """
    Choose a warp factor given a desired warp multiplier and a discrete rate table.

    Important:
      - KSP warp rates are discrete (e.g. rails: 1x, 5x, 10x, ...).
      - If we simply pick the highest rate <= target_rate, then any target_rate in (1, 5)
        maps to 1x, causing long realtime "waiting" far from the target UT.

    Strategy:
      Choose the factor whose implied arrival time best matches the requested target real time.
      In terms of multipliers, this means minimizing abs(target_rate / rate - 1).
    """
    if not rates:
        return 0

    try:
        desired = float(target_rate)
    except Exception:
        desired = 1.0

    best_idx = 0
    best_err = float("inf")
    best_rate = None
    for i, r in enumerate(rates):
        try:
            rate = float(r)
        except Exception:
            continue
        if not (rate > 0):
            continue

        # Relative error vs ideal: remaining/rate ~= remaining/desired.
        # Scale-free form: desired/rate ~= 1.
        err = abs((desired / rate) - 1.0)

        if (err + 1e-12) < best_err:
            best_idx = i
            best_err = err
            best_rate = rate
            continue

        # Tie-break toward faster warp when errors are effectively equal.
        if abs(err - best_err) <= 1e-12:
            if best_rate is None or rate > best_rate:
                best_idx = i
                best_rate = rate

    return best_idx


def _nearest_factor_index(*, rate: float, rates: list[float]) -> int:
    if not rates:
        return 0
    best_idx = 0
    best_err = float("inf")
    for i, r in enumerate(rates):
        rr = _safe_float(r)
        if rr is None or rr <= 0:
            continue
        err = abs(float(rate) - rr)
        if err < best_err:
            best_idx = i
            best_err = err
    return best_idx


def _compute_desired_rate(
    *,
    remaining_game_s: float,
    settle_at_s: float,
    target_real_time_s: float,
    elapsed_wall_s: float,
    min_wall_budget_s: float = 0.5,
) -> float:
    """
    Compute the desired warp multiplier for a warp job iteration.

    Note:
      - `target_real_time_s` is a total wall-time goal, not a per-step goal.
      - When we're behind schedule (elapsed_wall_s > target_real_time_s), we should not
        collapse to 1x far from the target; instead, keep warping (bounded by safety).
      - Within `settle_at_s` of the target UT, always request realtime to minimize overshoot.
    """
    remaining = float(remaining_game_s)
    if remaining <= float(settle_at_s):
        return 1.0

    target_total = max(1.0, float(target_real_time_s))
    budget = max(float(min_wall_budget_s), target_total - float(elapsed_wall_s))
    desired = remaining / budget if budget > 0 else remaining
    return max(1.0, float(desired))


def _compute_sleep_s(
    *,
    remaining_game_s: float,
    settle_at_s: float,
    expected_rate: float,
    base_sleep_s: float = 0.25,
    min_sleep_s: float = 0.02,
) -> float:
    """
    Choose a polling interval for the warp loop.

    Rationale: at high warp rates and small remaining times, using a fixed 0.25 s step can
    overshoot the target UT by a large margin. We shrink the poll interval when close.
    """
    remaining = float(remaining_game_s)
    base = float(base_sleep_s)
    expected = max(1.0, float(expected_rate))

    # Far from target, keep the loop coarse.
    close_threshold = max(30.0, 5.0 * float(settle_at_s))
    if remaining > close_threshold:
        return base

    # Near target, cap the expected game-time advance per poll.
    max_game_step = max(0.5, float(settle_at_s) / 2.0)
    return max(float(min_sleep_s), min(base, max_game_step / expected))


def _set_warp_factor(sc, *, rails: bool, factor: int) -> None:
    attr = "rails_warp_factor" if rails else "physics_warp_factor"
    setattr(sc, attr, int(factor))


def _reset_warp(sc) -> None:
    # Best-effort return to realtime.
    try:
        tw = getattr(sc, "warp", None)
        if tw is not None and hasattr(tw, "rate"):
            tw.rate = 1.0
    except Exception:
        pass
    for attr in ("rails_warp_factor", "physics_warp_factor"):
        try:
            if hasattr(sc, attr):
                setattr(sc, attr, 0)
        except Exception:
            pass


@mcp.tool()
def start_part_tree_job(
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    *,
    timeout: float = 5.0,
) -> str:
    """
    Start a background job that captures the full vessel part tree via kRPC readers.part_tree.

    Usage pattern:
        1. Call start_part_tree_job(...) to enqueue the work; it returns a job_id immediately.
        2. Poll get_job_status(job_id) until status is SUCCEEDED.
        3. Call read_resource on the returned result_resource (resource://jobs/<id>.json) to download the JSON artifact.
        4. Use the downloaded part tree for planning, then continue with other tools/scripts as needed.
    """
    params = {
        "address": address,
        "rpc_port": rpc_port,
        "stream_port": stream_port,
        "name": name,
        "timeout": timeout,
    }
    return _start_reader_job(kind="part_tree", params=params, reader=readers.part_tree)


# Removed from the blessed MCP tool surface: get_stage_plan is fast enough and returns the
# UI-matching schema (rounded DV + relevant_parts). Keeping the job starter as internal code
# in case we want to reintroduce a long-running variant later.
# @mcp.tool()
def start_stage_plan_job(
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    *,
    timeout: float = 5.0,
    environment: str = "current",
) -> str:
    """Internal helper (not exposed as an MCP tool)."""
    params = {
        "address": address,
        "rpc_port": rpc_port,
        "stream_port": stream_port,
        "name": name,
        "timeout": timeout,
        "environment": environment,
    }
    reader_kwargs = {"environment": environment}
    return _start_reader_job(
        kind="stage_plan",
        params=params,
        reader=readers.stage_plan_approx,
        reader_kwargs=reader_kwargs,
    )


def _start_warp_job_impl(*, params: dict) -> str:
    ut = params.get("ut")
    if ut is None:
        raise ValueError("ut is required")

    address = params["address"]
    rpc_port = params["rpc_port"]
    stream_port = params["stream_port"]
    name = params.get("name")
    timeout = params.get("timeout", 5.0)

    def job_fn(handle):
        job_id = handle.job_id
        target_ut = float(params["ut"]) - max(0.0, float(params.get("lead_time_s", 0.0)))
        requested_mode = str(params.get("mode") or "rails").lower().strip()
        rails = requested_mode != "physics"

        def cancel_cb() -> None:
            try:
                conn2 = connect_to_game(
                    address,
                    rpc_port=rpc_port,
                    stream_port=stream_port,
                    name=name,
                    timeout=timeout,
                )
                try:
                    _reset_warp(conn2.space_center)
                finally:
                    try:
                        conn2.close()
                    except Exception:
                        pass
            except Exception:
                pass

        handle.register_cancel_callback(cancel_cb)
        handle.log(f"[warp] Connecting to kRPC at {address}:{rpc_port}/{stream_port}")
        try:
            conn = connect_to_game(
                address,
                rpc_port=rpc_port,
                stream_port=stream_port,
                name=name,
                timeout=timeout,
            )
        except KRPCConnectionError as exc:
            handle.log(f"[warp] Connection failed: {exc}")
            raise

        try:
            sc = conn.space_center
            v = getattr(sc, "active_vessel", None)
            if v is None:
                raise RuntimeError("No active vessel; cannot warp.")

            paused_before = None
            try:
                paused_before = bool(conn.krpc.paused)
            except Exception:
                paused_before = None
            if paused_before is True:
                try:
                    conn.krpc.paused = False
                except Exception:
                    pass

            # Preflight checks for rails warp.
            if rails:
                in_atmo = False
                try:
                    in_atmo = bool(v.flight().atmosphere)
                except Exception:
                    in_atmo = False
                if in_atmo:
                    raise RuntimeError("Cannot use rails warp while in atmosphere. Climb above the atmosphere first.")
                try:
                    throttle = float(v.control.throttle)
                except Exception:
                    throttle = 0.0
                if throttle > 1e-3:
                    raise RuntimeError("Cannot start rails warp with throttle > 0. Set throttle to 0 or use mode='physics'.")

            # Best-effort: if Warp object exists, set mode up front but keep control via factor/rate loop.
            tw = getattr(sc, "warp", None)
            if tw is not None and hasattr(tw, "mode") and hasattr(tw, "rate"):
                try:
                    warp_mode_enum = getattr(sc, "WarpMode", None)
                    if warp_mode_enum is not None:
                        selection = getattr(warp_mode_enum, "rails" if rails else "physics", None)
                        if selection is not None:
                            tw.mode = selection
                except Exception:
                    pass

            max_factor = 7 if rails else 3
            if rails and hasattr(sc, "maximum_rails_warp_factor"):
                try:
                    max_factor = int(getattr(sc, "maximum_rails_warp_factor"))
                except Exception:
                    max_factor = 7
            rates = _get_rate_table(sc, rails=rails, max_factor=max_factor)

            handle.log(f"[warp] Target UT={target_ut:.3f} (requested ut={float(params['ut']):.3f}, lead={float(params.get('lead_time_s', 0.0)):.1f}s), mode={'rails' if rails else 'physics'}")
            start_wall = time.time()
            last_ut = _safe_float(getattr(sc, "ut", None))
            no_progress_s = 0.0
            last_log_wall = 0.0
            current_factor: int | None = None
            last_observed_rate = None

            while True:
                if handle.is_cancel_requested():
                    handle.log("[warp] Cancel requested; resetting warp to realtime.")
                    break

                now_ut = _safe_float(getattr(sc, "ut", None))
                if now_ut is None:
                    raise RuntimeError("Unable to read current UT from kRPC.")
                remaining = target_ut - now_ut
                if remaining <= 0:
                    break

                max_wall_time_s = params.get("max_wall_time_s")
                if max_wall_time_s is not None and (time.time() - start_wall) > float(max_wall_time_s):
                    raise RuntimeError(f"Warp exceeded max_wall_time_s={max_wall_time_s}.")

                settle_at_s = float(params.get("settle_at_s", 2.0))
                target_real_time_s = max(1.0, float(params.get("target_real_time_s", 10.0)))
                elapsed_wall = time.time() - start_wall
                desired_rate = _compute_desired_rate(
                    remaining_game_s=remaining,
                    settle_at_s=settle_at_s,
                    target_real_time_s=target_real_time_s,
                    elapsed_wall_s=elapsed_wall,
                )

                desired_factor = _choose_factor(target_rate=desired_rate, rates=rates)
                if current_factor != desired_factor:
                    _set_warp_factor(sc, rails=rails, factor=desired_factor)
                    current_factor = desired_factor

                observed_rate = _safe_float(getattr(sc, "warp_rate", None))
                if observed_rate is None and 0 <= desired_factor < len(rates):
                    observed_rate = rates[desired_factor]

                expected_rate = None
                try:
                    expected_rate = float(rates[desired_factor]) if 0 <= desired_factor < len(rates) else None
                except Exception:
                    expected_rate = None

                sleep_s = _compute_sleep_s(
                    remaining_game_s=remaining,
                    settle_at_s=settle_at_s,
                    expected_rate=float(expected_rate or observed_rate or 1.0),
                )

                # Detect "warp didn't engage" conditions.
                if last_ut is not None and now_ut <= last_ut + 1e-6:
                    no_progress_s += float(sleep_s)
                else:
                    no_progress_s = 0.0
                last_ut = now_ut

                # If we keep requesting >1x but the reported rate never leaves ~1x, assume warp is blocked.
                if desired_factor > 0:
                    if observed_rate is not None and observed_rate <= 1.01:
                        last_observed_rate = last_observed_rate or observed_rate
                    if no_progress_s >= 2.0:
                        raise RuntimeError("UT did not advance while warp >1x; warp may be blocked (atmosphere/throttle/altitude/physics constraints).")
                    if last_observed_rate is not None and observed_rate is not None and observed_rate <= 1.01 and (time.time() - start_wall) >= 2.0:
                        raise RuntimeError("Warp rate stayed at ~1x despite requesting >1x; warp is likely blocked (altitude/atmosphere/throttle).")

                # Throttle log volume: print at most 2 Hz, and always when close.
                wall = time.time() - start_wall
                if wall - last_log_wall >= 0.5 or remaining <= 30:
                    last_log_wall = wall

                    factor_attr = "rails_warp_factor" if rails else "physics_warp_factor"
                    observed_factor = _safe_int(getattr(sc, factor_attr, None))
                    effective_factor = None
                    try:
                        if observed_rate is not None:
                            effective_factor = _nearest_factor_index(rate=float(observed_rate), rates=rates)
                    except Exception:
                        effective_factor = None
                    handle.log(
                        f"[warp] UT={now_ut:.1f} remaining={remaining:.1f}s "
                        f"desired_rate={desired_rate:g} requested_factor={desired_factor} "
                        f"observed_factor={observed_factor} observed_rate={observed_rate:g} "
                        f"effective_factor={effective_factor}"
                    )

                time.sleep(float(sleep_s))

            _reset_warp(sc)
            final_time = readers.time_status(conn) if hasattr(readers, "time_status") else {}
            final_ut = _safe_float(getattr(sc, "ut", None))

            artifact_payload = {
                "job_id": job_id,
                "kind": "warp",
                "requested_at": utc_timestamp(),
                "params": params,
                "result": {
                    "target_ut": target_ut,
                    "final_ut": final_ut,
                    "reached": (final_ut is not None and final_ut >= target_ut),
                    "time_status": final_time,
                    "cancel_requested": handle.is_cancel_requested(),
                },
            }
            save_job_artifact(job_id, artifact_payload)
            handle.set_result_resource(job_resource_uri(job_id))
            handle.log(f"[warp] Artifact saved; exposing as resource {job_resource_uri(job_id)}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    metadata = {"kind": "warp", "params": params}
    return job_registry.create_job(job_fn, metadata=metadata)


@mcp.tool()
def start_warp_job(
    ut: float | None = None,
    lead_time_s: float = 0.0,
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    *,
    timeout: float = 5.0,
    mode: str = "rails",
    target_real_time_s: float = 10.0,
    settle_at_s: float = 2.0,
    max_wall_time_s: float | None = None,
) -> str:
    """
    Start a background job that timewarps toward a target UT and can be monitored/cancelled.

    This exists to work around clients with a hard 60s tool-call limit: the job returns
    immediately with a job_id while the server continues warping in the background.

    Args:
      ut: Target universal time to arrive at
      lead_time_s: Seconds to arrive before UT (e.g., half burn time)
      mode: 'rails' (default) or 'physics'
      target_real_time_s: Heuristic: try to reach the target in about this many real seconds
      settle_at_s: Slow down within this remaining time (seconds) to avoid overshoot
      max_wall_time_s: Optional safety cap; abort job if exceeded (None disables)

    Returns:
      JSON: { job_id, status, note }.
    """
    if ut is None:
        raise ValueError("ut is required")

    params = {
        "ut": float(ut),
        "lead_time_s": float(lead_time_s),
        "address": address,
        "rpc_port": rpc_port,
        "stream_port": stream_port,
        "name": name,
        "timeout": timeout,
        "mode": mode,
        "target_real_time_s": float(target_real_time_s),
        "settle_at_s": float(settle_at_s),
        "max_wall_time_s": None if max_wall_time_s is None else float(max_wall_time_s),
    }

    job_id = _start_warp_job_impl(params=params)
    return json_dumps(
        {
            "job_id": job_id,
            "status": "PENDING",
            "note": "Warp job started. Poll get_job_status(job_id) for logs or get_job_status(job_id+'_warp') for telemetry/ETA; cancel_job(job_id) resets warp to realtime.",
        }
    )
