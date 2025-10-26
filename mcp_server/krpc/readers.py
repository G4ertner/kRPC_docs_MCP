from __future__ import annotations

from typing import Any, Dict, List


def _enum_name(x: Any) -> str:
    try:
        return getattr(x, "name", str(x))
    except Exception:
        return str(x)


def vessel_info(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    ctrl = v.control
    return {
        "name": v.name,
        "mass_kg": v.mass,  # kg
        "throttle": ctrl.throttle,
        "situation": _enum_name(v.situation),
    }


def environment_info(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    body = v.orbit.body
    flight = v.flight()
    in_atmo = False
    try:
        in_atmo = bool(flight.atmosphere)
    except Exception:
        try:
            in_atmo = float(flight.mean_altitude) < float(body.atmosphere_depth)
        except Exception:
            in_atmo = False
    # Optional values
    pressure = None
    temp = None
    try:
        pressure = flight.static_pressure
    except Exception:
        pass
    try:
        temp = flight.temperature
    except Exception:
        pass
    biome = None
    try:
        biome = flight.biome
    except Exception:
        pass
    # Atmosphere presence (robust across API variants)
    has_atmo = False
    for attr in ("has_atmosphere", "atmosphere"):
        try:
            val = getattr(body, attr)
            if isinstance(val, bool):
                has_atmo = has_atmo or val
        except Exception:
            pass
    try:
        depth = getattr(body, "atmosphere_depth", None)
        if depth is not None:
            has_atmo = has_atmo or (float(depth) > 0)
    except Exception:
        pass

    return {
        "body": body.name,
        "in_atmosphere": in_atmo,
        "surface_gravity_m_s2": body.surface_gravity,
        "biome": biome,
        "static_pressure_pa": pressure,
        "temperature_k": temp,
        "atmosphere": has_atmo,
        "atmosphere_depth_m": getattr(body, "atmosphere_depth", None),
    }


def flight_snapshot(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    f = v.flight()
    data = {
        "altitude_sea_level_m": getattr(f, "mean_altitude", None),
        "altitude_terrain_m": getattr(f, "surface_altitude", None),
        "vertical_speed_m_s": getattr(f, "vertical_speed", None),
        "speed_surface_m_s": getattr(f, "speed", None),
        "speed_horizontal_m_s": getattr(f, "horizontal_speed", None),
        "dynamic_pressure_pa": getattr(f, "dynamic_pressure", None),
        "mach": getattr(f, "mach", None),
        "g_force": getattr(f, "g_force", None),
        "angle_of_attack_deg": getattr(f, "angle_of_attack", None),
        "pitch_deg": getattr(f, "pitch", None),
        "roll_deg": getattr(f, "roll", None),
        "heading_deg": getattr(f, "heading", None),
    }
    return data


def orbit_info(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    o = v.orbit
    return {
        "body": o.body.name,
        "apoapsis_altitude_m": getattr(o, "apoapsis_altitude", None),
        "time_to_apoapsis_s": getattr(o, "time_to_apoapsis", None),
        "periapsis_altitude_m": getattr(o, "periapsis_altitude", None),
        "time_to_periapsis_s": getattr(o, "time_to_periapsis", None),
        "eccentricity": getattr(o, "eccentricity", None),
        "inclination_deg": getattr(o, "inclination", None),
        "lan_deg": getattr(o, "longitude_of_ascending_node", None),
        "argument_of_periapsis_deg": getattr(o, "argument_of_periapsis", None),
        "semi_major_axis_m": getattr(o, "semi_major_axis", None),
        "period_s": getattr(o, "period", None),
    }


def time_status(conn) -> Dict[str, Any]:
    sc = conn.space_center
    v = sc.active_vessel
    data = {
        "universal_time_s": sc.ut,
        "mission_time_s": getattr(v, "met", None),
    }
    try:
        tw = sc.warp
        data["timewarp_rate"] = getattr(tw, "rate", None)
        data["timewarp_mode"] = _enum_name(getattr(tw, "mode", None))
    except Exception:
        pass
    return data


def attitude_status(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    ctrl = v.control
    ap = v.auto_pilot
    data = {
        "sas": getattr(ctrl, "sas", None),
        "sas_mode": _enum_name(getattr(ctrl, "sas_mode", None)),
        "rcs": getattr(ctrl, "rcs", None),
        "throttle": getattr(ctrl, "throttle", None),
    }
    # Autopilot state & targets (best-effort)
    try:
        data["autopilot_state"] = _enum_name(getattr(ap, "state", None))
        data["autopilot_target_pitch"] = getattr(ap, "target_pitch", None)
        data["autopilot_target_heading"] = getattr(ap, "target_heading", None)
        data["autopilot_target_roll"] = getattr(ap, "target_roll", None)
    except Exception:
        pass
    return data


def aero_status(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    f = v.flight()
    data = {
        "dynamic_pressure_pa": getattr(f, "dynamic_pressure", None),
        "mach": getattr(f, "mach", None),
        "atmosphere_density_kg_m3": getattr(f, "atmosphere_density", None),
    }
    # Optional
    try:
        data["drag"] = getattr(f, "drag", None)
    except Exception:
        pass
    try:
        data["lift"] = getattr(f, "lift", None)
    except Exception:
        pass
    return data


def maneuver_nodes_basic(conn) -> List[Dict[str, Any]]:
    sc = conn.space_center
    v = sc.active_vessel
    ut = sc.ut
    nodes = []
    try:
        for n in v.control.nodes:
            item = {
                "ut": getattr(n, "ut", None),
                "time_to_node_s": (getattr(n, "ut", 0) - ut) if getattr(n, "ut", None) is not None else None,
                "delta_v_m_s": getattr(n, "delta_v", None),
            }
            nodes.append(item)
    except Exception:
        pass
    return nodes
