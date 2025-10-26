from __future__ import annotations

from typing import Any, Dict, List
from math import atan, atan2, cos, sqrt, radians, sin


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


def engine_status(conn) -> List[Dict[str, Any]]:
    v = conn.space_center.active_vessel
    engines = []
    eng_objs = []
    try:
        eng_objs = list(v.parts.engines)
    except Exception:
        try:
            for p in v.parts.all:
                try:
                    e = p.engine
                    if e is not None:
                        eng_objs.append(e)
                except Exception:
                    continue
        except Exception:
            eng_objs = []

    for e in eng_objs:
        part_title = None
        try:
            part_title = getattr(e, "part").title
        except Exception:
            try:
                part_title = getattr(getattr(e, "part", None), "name", None)
            except Exception:
                part_title = None
        item = {
            "part": part_title,
            "active": getattr(e, "active", None),
            "has_fuel": getattr(e, "has_fuel", None),
            "flameout": getattr(e, "flameout", None),
            "thrust_n": getattr(e, "thrust", None),
            "max_thrust_n": getattr(e, "max_thrust", None),
            "specific_impulse_s": getattr(e, "specific_impulse", None),
            "throttle": getattr(e, "throttle", None),
        }
        engines.append(item)
    return engines


def resource_breakdown(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    out: Dict[str, Any] = {"vessel_totals": {}, "stage_totals": {}, "current_stage": None}
    try:
        res = v.resources
        for name in list(getattr(res, "names", []) or []):
            try:
                out["vessel_totals"][name] = {
                    "amount": res.amount(name),
                    "max": res.max(name),
                }
            except Exception:
                continue
    except Exception:
        pass

    # Current stage resource totals (non-cumulative)
    try:
        stage = v.control.current_stage
        out["current_stage"] = stage
        sres = v.resources_in_decouple_stage(stage, False)
        for name in list(getattr(sres, "names", []) or []):
            try:
                out["stage_totals"][name] = {
                    "amount": sres.amount(name),
                    "max": sres.max(name),
                }
            except Exception:
                continue
    except Exception:
        pass
    return out


def surface_info(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    body = v.orbit.body
    f = v.flight()
    lat = getattr(f, "latitude", None)
    lon = getattr(f, "longitude", None)
    surf_alt = getattr(f, "surface_altitude", None)
    ground_speed = getattr(f, "horizontal_speed", None)
    slope_deg = None
    try:
        if lat is not None and lon is not None:
            # Sample terrain heights around location to estimate slope
            step_deg = 0.001
            lat_rad = radians(lat)
            R = getattr(body, "equatorial_radius", 600000.0)
            dlat_m = radians(step_deg) * R
            dlon_m = radians(step_deg) * R * max(1e-6, cos(lat_rad))
            h0 = body.surface_height(lat, lon)
            h_latp = body.surface_height(lat + step_deg, lon)
            h_latm = body.surface_height(lat - step_deg, lon)
            h_lonp = body.surface_height(lat, lon + step_deg)
            h_lonm = body.surface_height(lat, lon - step_deg)
            if None not in (h0, h_latp, h_latm, h_lonp, h_lonm) and dlat_m and dlon_m:
                grad_lat = (h_latp - h_latm) / (2 * dlat_m)
                grad_lon = (h_lonp - h_lonm) / (2 * dlon_m)
                slope_rad = atan((grad_lat ** 2 + grad_lon ** 2) ** 0.5)
                slope_deg = slope_rad * 180.0 / 3.141592653589793
    except Exception:
        slope_deg = None

    terrain_height = None
    try:
        terrain_height = body.surface_height(lat, lon) if (lat is not None and lon is not None) else None
    except Exception:
        pass

    return {
        "latitude_deg": lat,
        "longitude_deg": lon,
        "surface_altitude_m": surf_alt,
        "ground_speed_m_s": ground_speed,
        "terrain_height_m": terrain_height,
        "slope_deg": slope_deg,
        "body": body.name,
    }


def targeting_info(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    out: Dict[str, Any] = {"target_type": None, "target_name": None}
    body = v.orbit.body
    ref = getattr(body, "non_rotating_reference_frame", body.reference_frame)
    try:
        tv = v.target_vessel
        if tv is not None:
            out["target_type"] = "vessel"
            out["target_name"] = tv.name
            try:
                vp = v.position(ref)
                vv = v.velocity(ref)
                tp = tv.position(ref)
                tvv = tv.velocity(ref)
                dp = [tp[i] - vp[i] for i in range(3)]
                dv = [tvv[i] - vv[i] for i in range(3)]
                out["distance_m"] = (dp[0] ** 2 + dp[1] ** 2 + dp[2] ** 2) ** 0.5
                out["relative_speed_m_s"] = (dv[0] ** 2 + dv[1] ** 2 + dv[2] ** 2) ** 0.5
            except Exception:
                pass
            return out
    except Exception:
        pass
    try:
        tb = v.target_body
        if tb is not None:
            out["target_type"] = "body"
            out["target_name"] = tb.name
            try:
                vp = v.position(ref)
                tp = tb.position(ref)
                dp = [tp[i] - vp[i] for i in range(3)]
                out["distance_m"] = (dp[0] ** 2 + dp[1] ** 2 + dp[2] ** 2) ** 0.5
            except Exception:
                pass
            return out
    except Exception:
        pass
    try:
        tdp = v.target_docking_port
        if tdp is not None:
            out["target_type"] = "docking_port"
            out["target_name"] = getattr(getattr(tdp, "part", None), "title", None)
            tv = getattr(getattr(tdp, "part", None), "vessel", None)
            if tv is not None:
                out["target_vessel"] = tv.name
                try:
                    vp = v.position(ref)
                    tp = tv.position(ref)
                    dp = [tp[i] - vp[i] for i in range(3)]
                    out["distance_m"] = (dp[0] ** 2 + dp[1] ** 2 + dp[2] ** 2) ** 0.5
                except Exception:
                    pass
            return out
    except Exception:
        pass
    out["target_type"] = None
    return out


def maneuver_nodes_detailed(conn) -> List[Dict[str, Any]]:
    sc = conn.space_center
    v = sc.active_vessel
    ut = sc.ut
    nodes = []
    # For burn time estimate
    mass = None
    thrust = None
    try:
        mass = v.mass
    except Exception:
        pass
    try:
        thrust = v.available_thrust
        if not thrust or thrust <= 0:
            # Fallback to sum of max_thrust across engines
            thrust = 0.0
            try:
                for e in v.parts.engines:
                    mt = getattr(e, "max_thrust", 0.0) or 0.0
                    thrust += float(mt)
            except Exception:
                thrust = None
    except Exception:
        thrust = None

    for n in v.control.nodes:
        dv_vec = getattr(n, "delta_v", None)
        dv = None
        if isinstance(dv_vec, (list, tuple)) and len(dv_vec) == 3:
            dv = float((dv_vec[0] ** 2 + dv_vec[1] ** 2 + dv_vec[2] ** 2) ** 0.5)
        item = {
            "ut": getattr(n, "ut", None),
            "time_to_node_s": (getattr(n, "ut", 0) - ut) if getattr(n, "ut", None) is not None else None,
            "delta_v_vector_m_s": dv_vec,
            "delta_v_total_m_s": dv,
        }
        # Simple burn time: dv / (thrust/mass)
        try:
            if dv is not None and thrust and mass and thrust > 0 and mass > 0:
                item["burn_time_simple_s"] = dv * mass / thrust
        except Exception:
            pass
        nodes.append(item)
    return nodes


def docking_ports(conn) -> List[Dict[str, Any]]:
    v = conn.space_center.active_vessel
    ports = []
    try:
        for p in v.parts.docking_ports:
            entry = {
                "part": getattr(getattr(p, "part", None), "title", None),
                "state": _enum_name(getattr(p, "state", None)),
                "ready": getattr(p, "ready", None),
                "dockee": getattr(getattr(p, "docked_part", None), "title", None),
            }
            ports.append(entry)
    except Exception:
        pass
    return ports


def camera_status(conn) -> Dict[str, Any]:
    sc = conn.space_center
    out: Dict[str, Any] = {}
    try:
        cam = sc.camera
    except Exception:
        return {"available": False}
    out["available"] = True
    try:
        out["mode"] = _enum_name(getattr(cam, "mode", None))
        out["pitch_deg"] = getattr(cam, "pitch", None)
        out["heading_deg"] = getattr(cam, "heading", None)
        out["distance_m"] = getattr(cam, "distance", None)
        out["min_pitch_deg"] = getattr(cam, "min_pitch", None)
        out["max_pitch_deg"] = getattr(cam, "max_pitch", None)
        out["min_distance_m"] = getattr(cam, "min_distance", None)
        out["max_distance_m"] = getattr(cam, "max_distance", None)
    except Exception:
        pass
    return out


def _gc_distance_and_bearing(body, lat1, lon1, lat2, lon2):
    try:
        R = getattr(body, "equatorial_radius", 600000.0)
        # Convert to radians
        phi1, phi2 = radians(lat1), radians(lat2)
        dphi = radians(lat2 - lat1)
        dlambda = radians(lon2 - lon1)
        a = (sin(dphi / 2) ** 2) + cos(phi1) * cos(phi2) * (sin(dlambda / 2) ** 2)
        c = 2 * atan2(sqrt(a), sqrt(max(0.0, 1 - a)))
        distance = R * c
        y = sin(dlambda) * cos(phi2)
        x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlambda)
        bearing = (atan2(y, x) * 180.0 / 3.141592653589793 + 360.0) % 360.0
        return distance, bearing
    except Exception:
        return None, None


def list_waypoints(conn) -> List[Dict[str, Any]]:
    sc = conn.space_center
    v = sc.active_vessel
    body = v.orbit.body
    out: List[Dict[str, Any]] = []
    try:
        wpm = sc.waypoint_manager
        wps = list(getattr(wpm, "waypoints", []) or [])
    except Exception:
        return out
    # Vessel position
    vlat = getattr(v.flight(), "latitude", None)
    vlon = getattr(v.flight(), "longitude", None)
    for w in wps:
        try:
            item = {
                "name": getattr(w, "name", None),
                "body": getattr(getattr(w, "body", None), "name", None),
                "latitude_deg": getattr(w, "latitude", None),
                "longitude_deg": getattr(w, "longitude", None),
                "altitude_m": getattr(w, "altitude", None),
            }
            if vlat is not None and vlon is not None and item["latitude_deg"] is not None and item["longitude_deg"] is not None:
                d, b = _gc_distance_and_bearing(body, vlat, vlon, item["latitude_deg"], item["longitude_deg"])
                item["distance_m"] = d
                item["bearing_deg"] = b
            out.append(item)
        except Exception:
            continue
    return out


def action_groups_status(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    ctrl = v.control
    out = {
        "sas": getattr(ctrl, "sas", None),
        "rcs": getattr(ctrl, "rcs", None),
        "lights": getattr(ctrl, "lights", None),
        "gear": getattr(ctrl, "gear", None),
        "brakes": getattr(ctrl, "brakes", None),
        "abort": getattr(ctrl, "abort", None),
    }
    # Custom groups 1..10
    try:
        try:
            import krpc  # type: ignore
            AG = krpc.spacecenter.ActionGroup
            for i in range(1, 11):
                name = f"custom{i:02d}"
                enum_val = getattr(AG, name, None)
                if enum_val is None:
                    out[f"custom_{i}"] = None
                else:
                    out[f"custom_{i}"] = bool(ctrl.get_action_group(enum_val))
        except Exception:
            # Fallback: try integer indexing where supported
            for i in range(1, 11):
                try:
                    out[f"custom_{i}"] = bool(ctrl.get_action_group(i))
                except Exception:
                    out[f"custom_{i}"] = None
    except Exception:
        pass
    return out


# --- Hard: Staging with per-stage Δv (approximate) ---
G0 = 9.80665  # m/s^2
RESOURCE_DENSITY_KG_PER_UNIT = {
    "LiquidFuel": 5.0,
    "Oxidizer": 5.0,
    "MonoPropellant": 4.0,
    "SolidFuel": 7.5,
    "XenonGas": 0.1,
    "Ore": 10.0,
    "ElectricCharge": 0.0,
}


def _stage_prop_mass_kg(conn, stage: int) -> float:
    v = conn.space_center.active_vessel
    mass = 0.0
    try:
        res = v.resources_in_decouple_stage(stage, False)
        names = list(getattr(res, "names", []) or [])
        for n in names:
            amt = 0.0
            try:
                amt = float(res.amount(n))
            except Exception:
                continue
            dens = RESOURCE_DENSITY_KG_PER_UNIT.get(n, 0.0)
            mass += amt * dens
    except Exception:
        pass
    return mass


def _stage_dry_drop_mass_kg(conn, stage: int) -> float:
    v = conn.space_center.active_vessel
    total = 0.0
    try:
        for p in v.parts.all:
            try:
                if getattr(p, "decouple_stage", None) == stage:
                    dm = getattr(p, "dry_mass", None)
                    if dm is None:
                        dm = getattr(p, "mass", 0.0)
                    total += float(dm)
            except Exception:
                continue
    except Exception:
        pass
    return total


def _combined_isp_and_thrust_for_stage(conn, stage: int):
    v = conn.space_center.active_vessel
    engines = []
    try:
        engines = [e for e in v.parts.engines if getattr(e.part, "stage", None) == stage]
    except Exception:
        pass
    total_thrust = 0.0
    denom = 0.0
    count = 0
    for e in engines:
        try:
            th = float(getattr(e, "max_thrust", 0.0) or 0.0)
            isp = float(getattr(e, "specific_impulse", 0.0) or 0.0)
            if th > 0 and isp > 0:
                total_thrust += th
                denom += th / isp
                count += 1
        except Exception:
            continue
    combined_isp = (total_thrust / denom) if denom > 0 else None
    return combined_isp, total_thrust, count


def staging_info(conn) -> Dict[str, Any]:
    v = conn.space_center.active_vessel
    body = v.orbit.body
    current_stage = getattr(v.control, "current_stage", 0)
    stages = []
    mass_current = float(getattr(v, "mass", 0.0) or 0.0)
    # Iterate stages from current down to 0
    for s in range(current_stage, -1, -1):
        prop_mass = _stage_prop_mass_kg(conn, s)
        m0 = mass_current
        m1 = max(0.1, m0 - prop_mass)  # avoid zero
        isp, thrust, eng_count = _combined_isp_and_thrust_for_stage(conn, s)
        dv = None
        if isp and isp > 0 and m0 > m1:
            from math import log
            dv = G0 * isp * log(m0 / m1)
        twr = None
        try:
            g = float(getattr(body, "surface_gravity", 9.81) or 9.81)
            if thrust and g > 0 and m0 > 0:
                twr = thrust / (m0 * g)
        except Exception:
            pass
        stages.append({
            "stage": s,
            "engines": eng_count,
            "max_thrust_n": thrust,
            "combined_isp_s": isp,
            "delta_v_m_s": dv,
            "twr_surface": twr,
            "prop_mass_kg": prop_mass,
            "m0_kg": m0,
            "m1_kg": m1,
        })
        # Update mass for next stage iteration: drop stage dry mass
        drop = _stage_dry_drop_mass_kg(conn, s)
        mass_current = max(0.1, m1 - drop)
    return {"current_stage": current_stage, "stages": stages}


def stage_plan_approx(conn) -> Dict[str, Any]:
    """
    Approximate KSP's stage DV display:
    - Split burn into subsegments labeled by stage boundaries.
    - For each engine ignition stage, iterate down through subsequent decouple stages.
      For subsegment labeled Y, use only propellant in stage Y-1, then decouple dry mass at Y.
    - Update engine set when engines are decoupled at Y.
    This yields small DV portions at early strap-on drops and a large DV portion for the
    core stage, matching stock staging intuition.
    """
    v = conn.space_center.active_vessel
    body = v.orbit.body
    g = float(getattr(body, "surface_gravity", 9.81) or 9.81)

    # Precompute per-stage propellant and dry mass drop
    current_stage = getattr(v.control, "current_stage", 0)
    # Determine min/max stage indices to consider
    min_stage = 0
    max_stage = 0
    try:
        max_stage = max([current_stage] + [getattr(getattr(e, "part", None), "stage", 0) for e in v.parts.engines])
    except Exception:
        max_stage = current_stage
    prop_by_stage = {s: _stage_prop_mass_kg(conn, s) for s in range(max_stage, min_stage - 1, -1)}
    drop_by_stage = {s: _stage_dry_drop_mass_kg(conn, s) for s in range(max_stage, min_stage - 1, -1)}

    # Build ignition stages and engine membership
    engines_all = []
    try:
        engines_all = list(v.parts.engines)
    except Exception:
        engines_all = []
    def engine_ignition_stage(e):
        try:
            return int(getattr(getattr(e, "part", None), "stage", 0))
        except Exception:
            return 0
    def engine_decouple_stage(e):
        try:
            return int(getattr(getattr(e, "part", None), "decouple_stage", -1))
        except Exception:
            return -1

    ignition_stages = sorted({engine_ignition_stage(e) for e in engines_all}, reverse=True)
    if not ignition_stages:
        return {"stages": []}

    # Helper: combined Isp/thrust for a set of engines
    def combined_isp_thrust(active_eng):
        total_thrust = 0.0
        denom = 0.0
        count = 0
        for e in active_eng:
            try:
                th = float(getattr(e, "max_thrust", 0.0) or 0.0)
                isp = float(getattr(e, "specific_impulse", 0.0) or 0.0)
                if th > 0 and isp > 0:
                    total_thrust += th
                    denom += th / isp
                    count += 1
            except Exception:
                continue
        isp = (total_thrust / denom) if denom > 0 else None
        return isp, total_thrust, count

    mass_current = float(getattr(v, "mass", 0.0) or 0.0)
    plan = []

    for idx, s in enumerate(ignition_stages):
        # Active engines: those ignited at stage s and not yet decoupled
        active_eng = [e for e in engines_all if engine_ignition_stage(e) == s]

        # Subsegments run from label y = s down to just above next ignition stage
        s_next = ignition_stages[idx + 1] if idx + 1 < len(ignition_stages) else -1
        y = s
        while y > s_next:
            # DV labeled at stage y comes from prop in stage y-1 (fuel burned before staging y)
            prop = prop_by_stage.get(y - 1, 0.0)
            isp, thrust, count = combined_isp_thrust(active_eng)
            dv = None
            twr = None
            if thrust and g > 0 and mass_current > 0:
                twr = thrust / (mass_current * g)
            if isp and isp > 0 and prop > 0 and mass_current > prop:
                from math import log
                dv = G0 * isp * log(mass_current / (mass_current - prop))

            plan.append({
                "stage": y,
                "engines": int(count or 0),
                "max_thrust_n": thrust,
                "combined_isp_s": isp,
                "prop_mass_kg": prop,
                "m0_kg": mass_current,
                "m1_kg": max(0.1, mass_current - prop),
                "delta_v_m_s": dv,
                "twr_surface": twr,
            })

            # Burn prop
            mass_current = max(0.1, mass_current - prop)
            # Stage y: decouple any engines/parts
            # Remove engines whose decouple_stage == y
            try:
                active_eng = [e for e in active_eng if engine_decouple_stage(e) != y]
            except Exception:
                pass
            # Drop dry mass
            mass_current = max(0.1, mass_current - drop_by_stage.get(y, 0.0))
            y -= 1

    return {"stages": plan}
