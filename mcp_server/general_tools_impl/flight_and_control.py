from __future__ import annotations

import time

from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import (
    best_effort_pause,
    best_effort_paused_state,
    best_effort_unpause,
    open_connection,
)
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_flight_snapshot(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Flight snapshot for the active vessel.

    When to use:
      - Real-time monitoring, ascent/descent guidance, atmosphere checks.

    Returns:
      JSON: { altitude_sea_level_m, altitude_terrain_m, vertical_speed_m_s,
      speed_surface_m_s, speed_horizontal_m_s, dynamic_pressure_pa, mach,
      g_force, angle_of_attack_deg, pitch_deg, roll_deg, heading_deg }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.flight_snapshot(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_attitude_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Attitude/control state for the active vessel.

    When to use:
      - Verify SAS/RCS/throttle state and autopilot targets before burns.
      - Pair with set_sas_mode to adjust navball hold behaviors.

    Returns:
      JSON: { sas, sas_mode, rcs, throttle, autopilot_state, autopilot_target_pitch,
      autopilot_target_heading, autopilot_target_roll, speed_mode? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.attitude_status(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_action_groups_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Action group toggles.

    When to use:
      - Verify control safety and configuration pre‑burn or pre‑entry.

    Returns:
      JSON: { sas, rcs, lights, gear, brakes, abort, custom_1..custom_10 }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json_dumps(readers.action_groups_status(conn))


def get_camera_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Active camera parameters when available: mode, pitch, heading, distance, and limits.

    Returns:
      JSON: { available, mode?, pitch_deg?, heading_deg?, distance_m?,
      min_pitch_deg?, max_pitch_deg?, min_distance_m?, max_distance_m? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json_dumps(readers.camera_status(conn))


def set_sas_mode(address: str = DEFAULT_KRPC_ADDRESS, mode: str | None = None, enable_sas: bool = True, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Set SAS on/off and select an SAS hold mode.

    Args:
      mode: One of the SAS modes (stability_assist, prograde, retrograde, normal, anti_normal,
        radial, anti_radial, target, anti_target, maneuver). Case- and dash/underscore-insensitive.
      enable_sas: If true, toggle SAS on before setting the mode.

    Returns:
      Human-readable status string indicating the final SAS state and SAS mode.

    Notes:
      - Best-effort unpauses before changing SAS and re-pauses afterward so you can set a target even while the game starts paused.
      - When enabling SAS from an off state, KSP can ignore direct transitions into some hold modes. This function latches SAS on first.
    """
    if mode is None:
        raise ValueError("mode is required")
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    paused_before = best_effort_paused_state(conn)
    try:
        best_effort_unpause(conn)
    except Exception:
        pass
    try:
        sc = conn.space_center
        ctrl = sc.active_vessel.control

        try:
            sas_before = bool(getattr(ctrl, "sas"))
        except Exception:
            sas_before = False

        key = mode.strip().lower().replace("-", "_")
        aliases = {
            "antinormal": "anti_normal",
            "anti_normal": "anti_normal",
            "antiradial": "anti_radial",
            "anti_radial": "anti_radial",
            "antitarget": "anti_target",
            "anti_target": "anti_target",
            "stability": "stability_assist",
            "stabilityassist": "stability_assist",
            "maneuver": "maneuver",
        }
        key = aliases.get(key, key)

        options = {attr.lower(): getattr(sc.SASMode, attr) for attr in dir(sc.SASMode) if not attr.startswith("_")}
        sas_enum = options.get(key)
        if sas_enum is None:
            available = ", ".join(sorted(options))
            return f"Unknown SAS mode '{mode}'. Available: {available}"

        desired_sas = sas_before if enable_sas is None else bool(enable_sas)

        def _read_sas() -> bool:
            try:
                return bool(getattr(ctrl, "sas"))
            except Exception:
                return False

        def _read_sas_mode():
            try:
                return getattr(ctrl, "sas_mode")
            except Exception:
                return None

        def _wait_for(predicate, timeout_s: float, step_s: float = 0.05) -> bool:
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                if predicate():
                    return True
                time.sleep(step_s)
            return bool(predicate())

        def _apply_sas_mode(target_mode, timeout_s: float = 1.0, step_s: float = 0.05) -> bool:
            deadline = time.time() + timeout_s
            last_ok = False
            while time.time() < deadline:
                try:
                    ctrl.sas_mode = target_mode
                except Exception:
                    pass
                last_ok = _read_sas_mode() == target_mode
                if last_ok:
                    return True
                time.sleep(step_s)
            return last_ok

        used_stability_latch = False
        stability_enum = options.get("stability_assist")

        if not desired_sas:
            try:
                ctrl.sas = False
            except Exception:
                pass
            return f"SAS set to off (sas={_read_sas()})."

        try:
            ctrl.sas = True
        except Exception:
            pass

        sas_enabled = _wait_for(_read_sas, timeout_s=1.0)
        if not sas_enabled and stability_enum is not None:
            # One more attempt: force stability assist, then enable SAS again.
            try:
                ctrl.sas_mode = stability_enum
                used_stability_latch = True
            except Exception:
                pass
            try:
                ctrl.sas = True
            except Exception:
                pass
            sas_enabled = _wait_for(_read_sas, timeout_s=1.0)

        if not sas_enabled:
            return f"Failed to enable SAS; requested mode {getattr(sas_enum, 'name', key)} (sas={_read_sas()})."

        # When coming from SAS-off, KSP often needs SAS to be enabled (and usually in stability assist)
        # for at least one tick before switching into other hold modes.
        if not sas_before and stability_enum is not None and sas_enum != stability_enum:
            if _apply_sas_mode(stability_enum, timeout_s=1.0):
                used_stability_latch = True
                time.sleep(0.15)

        mode_applied = _apply_sas_mode(sas_enum, timeout_s=1.0)
        time.sleep(0.15)
        # Confirm it persists after a couple of physics frames.
        mode_applied = mode_applied and (_read_sas_mode() == sas_enum)

        sas_enabled = _read_sas()
        suffix = ""
        if used_stability_latch:
            suffix = " (latched via stability_assist)"
        if mode_applied:
            return f"SAS mode set to {getattr(sas_enum, 'name', key)} (sas={sas_enabled}){suffix}."
        return f"SAS enabled but mode not confirmed as {getattr(sas_enum, 'name', key)} (sas={sas_enabled}, sas_mode={getattr(_read_sas_mode(), 'name', _read_sas_mode())}){suffix}."
    except Exception as e:
        return f"Failed to set SAS mode: {e}"
    finally:
        try:
            best_effort_pause(conn)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
