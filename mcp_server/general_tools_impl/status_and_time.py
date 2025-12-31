from __future__ import annotations

import time

from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_status_overview(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Combined snapshot of core vessel/game status in a single call.

    When to use:
      - Summarize state for planning, logging, or sanity checks.

    Returns:
      JSON: { vessel, environment, flight, orbit, time, attitude, aero, maneuver_nodes }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        out = {
            "vessel": readers.vessel_info(conn),
            "environment": readers.environment_info(conn),
            "flight": readers.flight_snapshot(conn),
            "orbit": readers.orbit_info(conn),
            "time": readers.time_status(conn),
            "attitude": readers.attitude_status(conn),
            "aero": readers.aero_status(conn),
            "maneuver_nodes": readers.maneuver_nodes_basic(conn),
        }
        return json_dumps(out)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _orbital_ascent_monitor(
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    timeout: float = 5.0,
    *,
    altitude_switch_m: float = 50_000.0,
) -> dict:
    """Internal helper: compact orbital-ascent monitoring snapshot for logs.

    Collects key ascent telemetry from orbit/flight/staging readers and returns
    a JSON string with the following fields:

      - apoapsis_altitude_m
      - periapsis_altitude_m
      - time_to_apoapsis_s
      - altitude_sea_level_m
      - velocity_m_s (surface below altitude_switch_m, orbital above when available)
      - velocity_mode: 'surface' | 'orbital'
      - pitch_deg
      - remaining_delta_v_m_s (sum of current and lower stages)
      - twr_surface (current stage, if available)

    This function is intended for internal use by ascent/autopilot helpers and
    is not exposed as an MCP tool.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        orbit = readers.orbit_info(conn) or {}
        flight = readers.flight_snapshot(conn) or {}
        staging = readers.staging_info(conn) or {}

        apo = orbit.get("apoapsis_altitude_m")
        pe = orbit.get("periapsis_altitude_m")
        tta = orbit.get("time_to_apoapsis_s")

        alt = flight.get("altitude_sea_level_m")
        v_surf = flight.get("speed_surface_m_s")
        v_orb = flight.get("speed_orbital_m_s")
        pitch = flight.get("pitch_deg")

        # Choose surface vs orbital speed based on altitude
        velocity_mode = "surface"
        velocity = v_surf
        try:
            if alt is not None and float(alt) >= float(altitude_switch_m) and v_orb is not None:
                velocity_mode = "orbital"
                velocity = v_orb
        except Exception:
            pass

        # Remaining Δv and current-stage TWR from staging info
        remaining_dv = None
        twr = None
        try:
            current_stage = staging.get("current_stage")
            stages = staging.get("stages") or []
            if current_stage is not None:
                total = 0.0
                for seg in stages:
                    s = seg.get("stage")
                    dv = seg.get("delta_v_m_s")
                    if s is None:
                        continue
                    # staging_info iterates stages from current down to 0, so
                    # s <= current_stage corresponds to "remaining" segments.
                    if dv is not None and s <= current_stage:
                        try:
                            total += float(dv)
                        except Exception:
                            continue
                    if s == current_stage and twr is None:
                        twr = seg.get("twr_surface")
                remaining_dv = total
        except Exception:
            pass

        snapshot = {
            "apoapsis_altitude_m": f"Apo: {apo} m",
            "periapsis_altitude_m": f"Peri: {pe} m",
            "time_to_apoapsis_s": f"Time to Apo: {tta} s",
            "altitude_sea_level_m": f"Alt: {alt} m",
            "velocity_m_s": f"V ({velocity_mode}): {velocity} m/s",
            "pitch_deg": f"Pitch: {pitch} deg",
            "remaining_delta_v_m_s": f"Δv: {remaining_dv} m/s",
            "twr_surface": f"TWR: {twr}",
        }

        return snapshot
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _warp_monitor(
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    timeout: float = 2.0,
    *,
    target_ut: float | None = None,
    preferred_mode: str | None = None,
) -> dict:
    """Internal helper: compact timewarp monitoring snapshot for logs/status polling.

    Best-effort readback of:
      - current UT
      - warp mode/rate (Warp object when available)
      - legacy warp_rate and factors (when exposed)
      - optional ETA to a target UT

    This function is intended for internal use by get_job_status suffix payloads
    and is not exposed as an MCP tool.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        sc = conn.space_center

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
            return [1.0, 5.0, 10.0, 50.0, 100.0, 1000.0, 10000.0, 100000.0]

        def _default_physics_rates() -> list[float]:
            return [1.0, 2.0, 3.0, 4.0]

        def _get_rate_table(*, rails: bool) -> list[float]:
            attr = "rails_warp_factors" if rails else "physics_warp_factors"
            rates = None
            if hasattr(sc, attr):
                try:
                    raw = list(getattr(sc, attr))
                    parsed: list[float] = []
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
            return rates

        def _nearest_factor(*, rate: float, rails: bool) -> tuple[int, float | None, float | None]:
            rates = _get_rate_table(rails=rails)
            if not rates:
                return 0, None, None
            best_i = 0
            best_r = _safe_float(rates[0]) or 1.0
            best_err = float("inf")
            for i, r in enumerate(rates):
                rr = _safe_float(r)
                if rr is None or rr <= 0:
                    continue
                err = abs(float(rate) - rr)
                if err < best_err:
                    best_i = i
                    best_r = rr
                    best_err = err
            rel = (best_err / best_r) if best_r else None
            return best_i, best_r, rel

        def _read_legacy_state() -> dict:
            state: dict = {}
            try:
                if hasattr(sc, "warp_rate"):
                    state["warp_rate"] = _safe_float(getattr(sc, "warp_rate", None))
            except Exception:
                pass
            for attr in ("rails_warp_factor", "physics_warp_factor"):
                try:
                    if hasattr(sc, attr):
                        state[attr] = _safe_int(getattr(sc, attr, None))
                except Exception:
                    pass
            return state

        def _infer_mode(*, tw_mode_name: str | None, legacy_state: dict, preferred: str | None) -> str | None:
            if tw_mode_name in {"rails", "physics"}:
                return tw_mode_name
            try:
                if (legacy_state.get("rails_warp_factor") or 0) > 0:
                    return "rails"
            except Exception:
                pass
            try:
                if (legacy_state.get("physics_warp_factor") or 0) > 0:
                    return "physics"
            except Exception:
                pass
            if preferred in {"rails", "physics"}:
                return preferred
            return None

        def _is_legacy_consistent(*, mode: str | None, legacy_state: dict, effective_rate: float) -> bool:
            # Realtime is always considered consistent.
            if effective_rate <= 1.01:
                return True

            if mode == "rails":
                f = legacy_state.get("rails_warp_factor")
                if f is None:
                    # Cannot validate factor; avoid claiming an inconsistency.
                    return True
                implied, _r, rel = _nearest_factor(rate=effective_rate, rails=True)
                return implied == int(f) or (rel is not None and rel <= 0.05)

            if mode == "physics":
                f = legacy_state.get("physics_warp_factor")
                if f is None:
                    # Cannot validate factor; avoid claiming an inconsistency.
                    return True
                implied, _r, rel = _nearest_factor(rate=effective_rate, rails=False)
                return implied == int(f) or (rel is not None and rel <= 0.05)

            rails_f = legacy_state.get("rails_warp_factor")
            phys_f = legacy_state.get("physics_warp_factor")
            if rails_f is None and phys_f is None:
                # No factors available; cannot validate.
                return True
            if rails_f is not None and int(rails_f) > 0:
                implied, _r, rel = _nearest_factor(rate=effective_rate, rails=True)
                return implied == int(rails_f) or (rel is not None and rel <= 0.05)
            if phys_f is not None and int(phys_f) > 0:
                implied, _r, rel = _nearest_factor(rate=effective_rate, rails=False)
                return implied == int(phys_f) or (rel is not None and rel <= 0.05)
            return False

        def _settle_legacy_state(
            *,
            tw_mode_name: str | None,
            preferred: str | None,
            effective_rate: float,
            wait_s: float = 0.25,
            poll_s: float = 0.02,
        ) -> tuple[dict, bool]:
            last = _read_legacy_state()
            mode = _infer_mode(tw_mode_name=tw_mode_name, legacy_state=last, preferred=preferred)
            if _is_legacy_consistent(mode=mode, legacy_state=last, effective_rate=effective_rate):
                return last, True

            deadline = time.monotonic() + max(0.0, float(wait_s))
            while time.monotonic() < deadline:
                time.sleep(max(0.0, float(poll_s)))
                cur = _read_legacy_state()
                mode = _infer_mode(tw_mode_name=tw_mode_name, legacy_state=cur, preferred=preferred)
                if _is_legacy_consistent(mode=mode, legacy_state=cur, effective_rate=effective_rate):
                    return cur, True
                last = cur
            return last, False

        out: dict = {"universal_time_s": getattr(sc, "ut", None)}

        # Warp object (newer kRPC)
        tw = getattr(sc, "warp", None)
        tw_rate: float | None = None
        tw_mode_name: str | None = None
        if tw is not None:
            try:
                out["timewarp_rate"] = getattr(tw, "rate", None)
                tw_rate = _safe_float(out.get("timewarp_rate"))
            except Exception:
                pass
            try:
                mode = getattr(tw, "mode", None)
                out["timewarp_mode"] = getattr(mode, "name", None) or str(mode)
                raw_mode = out.get("timewarp_mode")
                tw_mode_name = (str(raw_mode).lower().strip() if raw_mode else None)
            except Exception:
                pass

        # Prefer Warp.rate when available; fall back to legacy warp_rate.
        rate_effective = tw_rate
        rate_source = "warp.rate"
        if rate_effective is None:
            legacy_rate = _safe_float(getattr(sc, "warp_rate", None))
            if legacy_rate is not None:
                rate_effective = legacy_rate
                rate_source = "space_center.warp_rate"
        if rate_effective is None or rate_effective <= 0:
            rate_effective = 1.0
            rate_source = "default(1.0)"

        normalized_preferred = None
        try:
            normalized_preferred = str(preferred_mode).lower().strip() if preferred_mode else None
        except Exception:
            normalized_preferred = None

        legacy_state, stable = _settle_legacy_state(
            tw_mode_name=tw_mode_name,
            preferred=normalized_preferred,
            effective_rate=float(rate_effective),
        )
        out.update(legacy_state)
        out["telemetry_stable"] = stable

        mode_effective = _infer_mode(tw_mode_name=tw_mode_name, legacy_state=legacy_state, preferred=normalized_preferred)
        out["warp_mode_effective"] = mode_effective
        out["warp_rate_effective"] = float(rate_effective)
        out["warp_rate_source"] = rate_source

        # Effective factor: always return a value when we can compute it from the rate.
        # At ~1x, treat as realtime factor 0 regardless of mode ambiguity.
        if float(rate_effective) <= 1.01:
            out["warp_factor_effective"] = 0
        else:
            out["warp_factor_effective"] = None
            if mode_effective == "rails":
                f, _r, _rel = _nearest_factor(rate=float(rate_effective), rails=True)
                out["warp_factor_effective"] = int(f)
            elif mode_effective == "physics":
                f, _r, _rel = _nearest_factor(rate=float(rate_effective), rails=False)
                out["warp_factor_effective"] = int(f)
            else:
                # Mode unknown: pick whichever table matches the multiplier better.
                fr, _rr, relr = _nearest_factor(rate=float(rate_effective), rails=True)
                fp, _rp, relp = _nearest_factor(rate=float(rate_effective), rails=False)
                relr_val = relr if relr is not None else float("inf")
                relp_val = relp if relp is not None else float("inf")
                out["warp_factor_effective"] = int(fr if relr_val <= relp_val else fp)

        # Compute ETA (real seconds) from remaining game seconds and current warp multiplier.
        if target_ut is not None:
            try:
                now_ut = float(out.get("universal_time_s") or getattr(sc, "ut", 0.0))
            except Exception:
                now_ut = None
            if now_ut is not None:
                remaining_game_s = float(target_ut) - now_ut
                out["target_ut"] = float(target_ut)
                out["remaining_game_time_s"] = remaining_game_s

                out["estimated_remaining_real_s"] = (
                    max(0.0, remaining_game_s) / float(rate_effective) if remaining_game_s > 0 else 0.0
                )
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_vessel_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Basic vessel info for the active craft.

    When to use:
      - High-level status summaries and sanity checks prior to planning.

    Args:
      address: LAN IP/hostname of the KSP PC
      rpc_port: kRPC RPC port (default 50000)
      stream_port: kRPC stream port (default 50001)
      name: Optional connection name shown in kRPC UI
      timeout: Connection timeout in seconds

    Returns:
      JSON string: { name, mass_kg, throttle, situation }
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.vessel_info(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_time_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Time context for the current save.

    When to use:
      - Scheduling burns, warp decisions, or synchronizing UT across tools.

    Returns:
      JSON: { universal_time_s, mission_time_s }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.time_status(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def set_timewarp_rate(address: str = DEFAULT_KRPC_ADDRESS, rate: float = 1.0, mode: str | None = None, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Adjust the current timewarp rate (and optionally the warp mode).

    When to use:
      - Change how fast the simulation advances when waiting on long events.
      - Reset the warp speed after a fire-and-forget warp_to call.

    Args:
      rate: Desired timewarp rate; 1.0 is realtime, >1 is warp, 0 stops time.
      mode: Optional warp mode name ('physics', 'rails', 'none').

    Returns:
      Human-readable status string describing the result."""
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        sc = conn.space_center
        # Newer kRPC builds expose a Warp object; older builds only expose warp_factor properties.
        tw = getattr(sc, "warp", None)

        def _set_via_warp_object() -> str:
            if tw is None:
                return ""

            if mode is not None:
                warp_mode_enum = getattr(sc, "WarpMode", None)
                if warp_mode_enum is None:
                    return "Warp mode selection is unavailable on this client."
                normalized = mode.lower()
                selection = getattr(warp_mode_enum, normalized, None)
                valid_modes = [
                    name
                    for name in ("physics", "rails", "none")
                    if hasattr(warp_mode_enum, name)
                ]
                if selection is None:
                    candidate_list = ", ".join(valid_modes) if valid_modes else "physics, rails, none"
                    return f"Unsupported warp mode '{mode}'. Valid options: {candidate_list}."
                try:
                    tw.mode = selection
                except Exception as exc:
                    return f"Failed to set warp mode '{mode}': {exc}"

            try:
                tw.rate = float(rate)
            except Exception as exc:
                return f"Failed to set warp rate to {rate}: {exc}"

            try:
                actual_rate = float(getattr(tw, "rate", float(rate)))
            except Exception:
                actual_rate = float(rate)
            requested_mode = mode.lower().strip() if isinstance(mode, str) else None
            try:
                actual_mode = getattr(getattr(tw, "mode", None), "name", None) or str(getattr(tw, "mode", ""))
            except Exception:
                actual_mode = ""
            actual_mode = actual_mode.lower().strip() if actual_mode else None
            if requested_mode:
                return f"Timewarp set (warp object). Requested mode={requested_mode}, rate={float(rate):g}. Actual mode={actual_mode}, rate={actual_rate:g}."
            return f"Timewarp set (warp object). Requested rate={float(rate):g}. Actual mode={actual_mode}, rate={actual_rate:g}."

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

        def _read_legacy_warp_state() -> dict:
            state: dict = {}
            state["warp_rate"] = _safe_float(getattr(sc, "warp_rate", None))
            if hasattr(sc, "rails_warp_factor"):
                state["rails_warp_factor"] = _safe_int(getattr(sc, "rails_warp_factor", None))
            if hasattr(sc, "physics_warp_factor"):
                state["physics_warp_factor"] = _safe_int(getattr(sc, "physics_warp_factor", None))
            return state

        def _wait_for_legacy_state(
            *,
            wait_s: float = 0.35,
            poll_s: float = 0.02,
            factor_attr: str | None = None,
            desired_factor: int | None = None,
            expected_rate: float | None = None,
        ) -> tuple[dict, bool]:
            """
            kRPC/KSP timewarp changes are not always reflected immediately after writing
            warp_factor. Poll briefly to avoid returning internally contradictory
            factor/rate readouts.
            """
            deadline = time.monotonic() + max(0.0, float(wait_s))
            prev = None
            stable_count = 0
            last = _read_legacy_warp_state()
            while time.monotonic() < deadline:
                time.sleep(max(0.0, float(poll_s)))
                cur = _read_legacy_warp_state()
                rate_now = cur.get("warp_rate")
                factor_ok = True
                if factor_attr is not None and desired_factor is not None:
                    factor_ok = cur.get(factor_attr) == desired_factor
                rate_ok = True
                if expected_rate is not None and rate_now is not None:
                    try:
                        rate_ok = abs(float(rate_now) - float(expected_rate)) <= max(1e-6, 1e-3 * float(expected_rate))
                    except Exception:
                        rate_ok = False

                if cur == prev and rate_now is not None and factor_ok and rate_ok:
                    stable_count += 1
                    if stable_count >= 1:
                        return cur, True
                else:
                    stable_count = 0
                prev = cur
                last = cur
            return last, False

        def _get_rate_table(*, rails: bool, max_factor: int) -> list[float]:
            """
            Prefer rate tables from the kRPC client when available; otherwise fall back
            to stock-like defaults.
            """
            attr = "rails_warp_factors" if rails else "physics_warp_factors"
            rates = None
            if hasattr(sc, attr):
                try:
                    raw = list(getattr(sc, attr))
                    parsed = []
                    for x in raw:
                        xf = _safe_float(x)
                        if xf is not None and xf > 0:
                            parsed.append(xf)
                    if parsed:
                        rates = parsed
                except Exception:
                    rates = None
            if rates is None:
                rates = [1.0, 5.0, 10.0, 50.0, 100.0, 1000.0, 10000.0, 100000.0] if rails else [1.0, 2.0, 3.0, 4.0]
            return rates[: max_factor + 1] if max_factor is not None else rates

        def _choose_factor(*, target_rate: float, rates: list[float]) -> int:
            if not rates:
                return 0
            # Choose the highest factor whose rate does not exceed target_rate.
            chosen = 0
            for i, r in enumerate(rates):
                try:
                    if float(r) <= float(target_rate) + 1e-9:
                        chosen = i
                except Exception:
                    continue
            return chosen

        def _set_factor(
            *,
            target_rate: float,
            rails: bool,
        ) -> tuple[bool, str]:
            factor_attr = "rails_warp_factor" if rails else "physics_warp_factor"
            max_attr = "maximum_rails_warp_factor" if rails else None

            if not hasattr(sc, factor_attr):
                return False, f"{'Rails' if rails else 'Physics'} warp is not supported on this client."

            max_factor = 3 if not rails else None
            if rails and hasattr(sc, max_attr):
                try:
                    max_factor = int(getattr(sc, max_attr))
                except Exception:
                    max_factor = None

            if max_factor is None:
                # Best-effort default rails max when client does not report it
                max_factor = 7

            rates = _get_rate_table(rails=rails, max_factor=max_factor)
            desired_factor = _choose_factor(target_rate=float(target_rate), rates=rates)
            expected_rate = _safe_float(rates[desired_factor]) if 0 <= desired_factor < len(rates) else None

            try:
                setattr(sc, factor_attr, int(desired_factor))
            except Exception as exc:
                return False, f"Failed to set {'rails' if rails else 'physics'} warp factor to {desired_factor}: {exc}"

            state, stable = _wait_for_legacy_state(
                factor_attr=factor_attr,
                desired_factor=int(desired_factor),
                expected_rate=expected_rate,
            )
            observed_rate = state.get("warp_rate")
            observed_factor = state.get(factor_attr)
            if observed_factor is None:
                observed_factor = desired_factor

            bits = [
                f"{'Rails' if rails else 'Physics'} timewarp set.",
                f"Requested rate={float(target_rate):g}.",
                f"Applied factor={int(desired_factor)}" + (f" (expected rate={expected_rate:g})." if expected_rate is not None else "."),
            ]
            if observed_rate is not None:
                bits.append(f"Observed factor={int(observed_factor)}, warp_rate={observed_rate:g}.")
            else:
                bits.append(f"Observed factor={int(observed_factor)} (warp_rate unavailable).")
            if not stable:
                bits.append("Warp state may still be updating; re-check with get_time_status.")
            return True, " ".join(bits)

        via_warp = _set_via_warp_object()
        if via_warp:
            return via_warp

        normalized_mode = mode.lower() if isinstance(mode, str) else None
        prefer_rails = normalized_mode in (None, "rails")
        prefer_physics = normalized_mode == "physics"

        # Try preferred path first, then fallback to the other if available.
        if prefer_rails:
            ok, msg = _set_factor(target_rate=float(rate), rails=True)
            if ok:
                return msg
            if not prefer_physics:
                return msg

        if prefer_physics or not prefer_rails:
            ok, msg = _set_factor(target_rate=float(rate), rails=False)
            if ok:
                return msg
            if prefer_physics:
                return msg

        # Last fallback: try whichever path works.
        for rails_flag in (True, False):
            ok, msg = _set_factor(target_rate=float(rate), rails=rails_flag)
            if ok:
                return msg

        return "Timewarp controls are not available on this kRPC client."
    except Exception as exc:  # pragma: no cover - best-effort helper
        return f"Failed to adjust timewarp: {exc}"
    finally:
        try:
            conn.close()
        except Exception:
            pass
