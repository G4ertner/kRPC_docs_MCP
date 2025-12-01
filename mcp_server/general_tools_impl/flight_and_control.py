from __future__ import annotations

import json

from ..utils.krpc_utils import readers
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
        return json.dumps(readers.flight_snapshot(conn))
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
        return json.dumps(readers.attitude_status(conn))
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
    return json.dumps(readers.action_groups_status(conn))


def get_camera_status(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Active camera parameters when available: mode, pitch, heading, distance, and limits.

    Returns:
      JSON: { available, mode?, pitch_deg?, heading_deg?, distance_m?,
      min_pitch_deg?, max_pitch_deg?, min_distance_m?, max_distance_m? }.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    return json.dumps(readers.camera_status(conn))


def set_sas_mode(address: str = DEFAULT_KRPC_ADDRESS, mode: str | None = None, enable_sas: bool = True, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Set SAS on/off and select an SAS hold mode while keeping the simulation running just long enough to align.

    Args:
      mode: One of the SAS modes (stability_assist, prograde, retrograde, normal, anti_normal,
        radial, anti_radial, target, anti_target, maneuver). Case- and dash/underscore-insensitive.
      enable_sas: If true, toggle SAS on before setting the mode.

    Returns:
      Human-readable status string indicating the final SAS mode and whether an orientation alignment was observed.

    Notes:
      - Best-effort unpauses before changing SAS and re-pauses after the SAS vector is aligned so you can set a target even while the game starts paused.
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

        try:
            if enable_sas is not None:
                ctrl.sas = bool(enable_sas)
        except Exception:
            pass

        ctrl.sas_mode = sas_enum
        sas_enabled = getattr(ctrl, "sas", True)
        aligned = False
        if sas_enabled:
            autop = sc.active_vessel.auto_pilot
            prev_frame = None
            try:
                prev_frame = getattr(autop, "reference_frame", None)
            except Exception:
                prev_frame = None
            orbital_frame = None
            try:
                orbital_frame = sc.active_vessel.orbital_reference_frame
            except Exception:
                orbital_frame = None
            try:
                if orbital_frame is not None:
                    autop.reference_frame = orbital_frame
            except Exception:
                pass
            try:
                autop.engage()
                try:
                    autop.sas = True
                except Exception:
                    pass
                try:
                    autop.sas_mode = sas_enum
                except Exception:
                    pass
                autop.wait()
                aligned = True
            except Exception:
                pass
            finally:
                try:
                    autop.reference_frame = prev_frame
                except Exception:
                    pass
                try:
                    autop.disengage()
                except Exception:
                    pass

        status = f"SAS mode set to {getattr(sas_enum, 'name', key)} (sas={sas_enabled})."
        if sas_enabled:
            status += " Orientation aligned." if aligned else " Orientation alignment not confirmed."
        return status
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
