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
    sc = conn.space_center
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
    # Fallback: some clients expose target via SpaceCenter
    try:
        tv2 = getattr(sc, "target_vessel", None)
        if tv2 is not None:
            out["target_type"] = "vessel"
            out["target_name"] = tv2.name
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
    # Fallback: SpaceCenter-level target body
    try:
        tb2 = getattr(sc, "target_body", None)
        if tb2 is not None:
            out["target_type"] = "body"
            out["target_name"] = tb2.name
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


def _vector_angle_deg(a, b) -> float | None:
    try:
        ax, ay, az = a
        bx, by, bz = b
        dot = ax * bx + ay * by + az * bz
        na = sqrt(ax * ax + ay * ay + az * az)
        nb = sqrt(bx * bx + by * by + bz * bz)
        if na == 0 or nb == 0:
            return None
        c = max(-1.0, min(1.0, dot / (na * nb)))
        from math import acos
        return acos(c) * 180.0 / 3.141592653589793
    except Exception:
        return None


def _phase_angle_deg(p1, p2) -> float | None:
    """Return the polar angle difference between two position vectors in a plane.
    Uses atan2 on the x-y projection; suitable for coarse phase planning.
    """
    try:
        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])
        a1 = atan2(y1, x1)
        a2 = atan2(y2, x2)
        d = (a2 - a1) * 180.0 / 3.141592653589793
        # Normalize to [-180, 180]
        while d > 180:
            d -= 360
        while d < -180:
            d += 360
        return d
    except Exception:
        return None


def _normalize(v):
    try:
        nx = float(v[0]); ny = float(v[1]); nz = float(v[2])
        n = sqrt(nx*nx + ny*ny + nz*nz)
        if n == 0:
            return None
        return [nx/n, ny/n, nz/n]
    except Exception:
        return None


def _find_next_nodes(orbit, ref, plane_normal, ut0, period):
    """
    Find next ascending/descending node times where position crosses the plane
    with normal 'plane_normal'. Uses sampling+bisection over one period.
    Returns (an_ut, dn_ut) or None values.
    """
    n_hat = _normalize(plane_normal)
    if n_hat is None or period is None or period <= 0:
        return None, None
    N = 120
    dt = max(period / N, 0.5)
    last_s = None
    last_ut = None
    nodes = []
    t = ut0
    for _ in range(N+1):
        try:
            r = orbit.position_at(t, ref)
        except Exception:
            break
        s = r[0]*n_hat[0] + r[1]*n_hat[1] + r[2]*n_hat[2]
        ut_node = None
        if last_s is not None and s == 0:
            ut_node = t
        elif last_s is not None and last_s * s < 0:
            a = last_ut; b = t
            fa = last_s; fb = s
            for __ in range(20):
                m = 0.5*(a+b)
                try:
                    rm = orbit.position_at(m, ref)
                except Exception:
                    break
                fm = rm[0]*n_hat[0] + rm[1]*n_hat[1] + rm[2]*n_hat[2]
                if fm == 0:
                    a = b = m
                    break
                if fa * fm <= 0:
                    b = m; fb = fm
                else:
                    a = m; fa = fm
            ut_node = 0.5*(a+b)
        if ut_node is not None:
            sign = 0.0
            try:
                vel = orbit.velocity_at(ut_node, ref)
                sign = vel[0]*n_hat[0] + vel[1]*n_hat[1] + vel[2]*n_hat[2]
            except Exception:
                pass
            nodes.append((ut_node, 'AN' if sign > 0 else 'DN'))
            if len(nodes) >= 2:
                break
        last_s = s; last_ut = t
        t += dt
    an_ut = next((ut for ut, kind in nodes if kind == 'AN'), None)
    dn_ut = next((ut for ut, kind in nodes if kind == 'DN'), None)
    return an_ut, dn_ut


def navigation_info(conn) -> Dict[str, Any]:
    """
    Provide coarse navigation info to a body or vessel target.

    For target body:
      - phase_angle_deg around common parent (if available)
      - target orbital elements (sma, period, inclination, LAN)
    For target vessel:
      - distance, relative_speed
      - relative_inclination_deg (angle between orbital planes)
      - phase_angle_deg around central body (if both orbit same)
    """
    sc = conn.space_center
    v = sc.active_vessel
    out: Dict[str, Any] = {"target_type": None}

    # Try vessel target first
    try:
        tv = v.target_vessel
        if tv is not None:
            out["target_type"] = "vessel"
            out["name"] = tv.name
            cb = v.orbit.body
            ref = getattr(cb, "non_rotating_reference_frame", cb.reference_frame)
            try:
                vp = v.position(ref)
                vv = v.velocity(ref)
                tp = tv.position(ref)
                tvv = tv.velocity(ref)
                dp = [tp[i] - vp[i] for i in range(3)]
                dv = [tvv[i] - vv[i] for i in range(3)]
                out["distance_m"] = sqrt(dp[0] ** 2 + dp[1] ** 2 + dp[2] ** 2)
                out["relative_speed_m_s"] = sqrt(dv[0] ** 2 + dv[1] ** 2 + dv[2] ** 2)
            except Exception:
                pass
            # Relative inclination via orbit normals (if both orbit the same central body)
            try:
                ref_parent = getattr(cb, "non_rotating_reference_frame", cb.reference_frame)
                # Current normal
                r1 = v.position(ref_parent)
                w1 = v.velocity(ref_parent)
                h1 = [
                    r1[1] * w1[2] - r1[2] * w1[1],
                    r1[2] * w1[0] - r1[0] * w1[2],
                    r1[0] * w1[1] - r1[1] * w1[0],
                ]
                # Target normal
                r2 = tv.position(ref_parent)
                w2 = tv.velocity(ref_parent)
                h2 = [
                    r2[1] * w2[2] - r2[2] * w2[1],
                    r2[2] * w2[0] - r2[0] * w2[2],
                    r2[0] * w2[1] - r2[1] * w2[0],
                ]
                out["relative_inclination_deg"] = _vector_angle_deg(h1, h2)
                out["phase_angle_deg"] = _phase_angle_deg(r1, r2)
                # Next AN/DN estimates
                ut0 = sc.ut
                period = getattr(v.orbit, 'period', None)
                an_ut, dn_ut = _find_next_nodes(v.orbit, ref_parent, h2, ut0, period)
                if an_ut:
                    out["next_an_ut"] = an_ut
                    out["time_to_an_s"] = an_ut - ut0
                if dn_ut:
                    out["next_dn_ut"] = dn_ut
                    out["time_to_dn_s"] = dn_ut - ut0
            except Exception:
                pass
            return out
    except Exception:
        pass

    # Try body target
    # Fallback: SpaceCenter-level target vessel
    try:
        tv2 = getattr(sc, "target_vessel", None)
        if tv2 is not None:
            tv = tv2
            out["target_type"] = "vessel"
            out["name"] = tv.name
            cb = v.orbit.body
            ref = getattr(cb, "non_rotating_reference_frame", cb.reference_frame)
            try:
                vp = v.position(ref)
                vv = v.velocity(ref)
                tp = tv.position(ref)
                tvv = tv.velocity(ref)
                dp = [tp[i] - vp[i] for i in range(3)]
                dv = [tvv[i] - vv[i] for i in range(3)]
                out["distance_m"] = sqrt(dp[0] ** 2 + dp[1] ** 2 + dp[2] ** 2)
                out["relative_speed_m_s"] = sqrt(dv[0] ** 2 + dv[1] ** 2 + dv[2] ** 2)
            except Exception:
                pass
            try:
                ref_parent = getattr(cb, "non_rotating_reference_frame", cb.reference_frame)
                r1 = v.position(ref_parent); w1 = v.velocity(ref_parent)
                h1 = [r1[1]*w1[2]-r1[2]*w1[1], r1[2]*w1[0]-r1[0]*w1[2], r1[0]*w1[1]-r1[1]*w1[0]]
                r2 = tv.position(ref_parent); w2 = tv.velocity(ref_parent)
                h2 = [r2[1]*w2[2]-r2[2]*w2[1], r2[2]*w2[0]-r2[0]*w2[2], r2[0]*w2[1]-r2[1]*w2[0]]
                out["relative_inclination_deg"] = _vector_angle_deg(h1, h2)
                out["phase_angle_deg"] = _phase_angle_deg(r1, r2)
            except Exception:
                pass
            return out
    except Exception:
        pass

    try:
        tb = v.target_body
        if tb is not None:
            out["target_type"] = "body"
            out["name"] = tb.name
            vb = v.orbit.body
            parent_v = getattr(getattr(vb, "orbit", None), "reference_body", None)
            parent_t = getattr(getattr(tb, "orbit", None), "reference_body", None)

            # Case 1: target is a moon of the vessel's body (e.g., Mun while orbiting Kerbin)
            try:
                if parent_t is not None and parent_t == vb:
                    ref = getattr(vb, "non_rotating_reference_frame", vb.reference_frame)
                    p_v = v.position(ref)
                    p_t = tb.position(ref)
                    out["phase_angle_deg"] = _phase_angle_deg(p_v, p_t)
                    # h2: target body's orbit plane normal around vb
                    vt = tb.velocity(ref); rt = tb.position(ref)
                    h2 = [rt[1]*vt[2]-rt[2]*vt[1], rt[2]*vt[0]-rt[0]*vt[2], rt[0]*vt[1]-rt[1]*vt[0]]
                    ut0 = sc.ut
                    period = getattr(v.orbit, 'period', None)
                    an_ut, dn_ut = _find_next_nodes(v.orbit, ref, h2, ut0, period)
                    if an_ut:
                        out["next_an_ut"] = an_ut
                        out["time_to_an_s"] = an_ut - ut0
                    if dn_ut:
                        out["next_dn_ut"] = dn_ut
                        out["time_to_dn_s"] = dn_ut - ut0
            except Exception:
                pass

            # Case 2: both bodies share a common parent (e.g., interplanetary transfers)
            try:
                if parent_v is not None and parent_v == parent_t:
                    ref = getattr(parent_v, "non_rotating_reference_frame", parent_v.reference_frame)
                    p_vb = vb.position(ref)
                    p_tb = tb.position(ref)
                    out.setdefault("phase_angle_deg", _phase_angle_deg(p_vb, p_tb))
                    # Use target body's orbital plane around common parent
                    vt = tb.velocity(ref); rt = tb.position(ref)
                    h2 = [rt[1]*vt[2]-rt[2]*vt[1], rt[2]*vt[0]-rt[0]*vt[2], rt[0]*vt[1]-rt[1]*vt[0]]
                    ut0 = sc.ut
                    period = getattr(v.orbit, 'period', None)
                    an_ut, dn_ut = _find_next_nodes(v.orbit, ref, h2, ut0, period)
                    if an_ut:
                        out["next_an_ut"] = an_ut
                        out["time_to_an_s"] = an_ut - ut0
                    if dn_ut:
                        out["next_dn_ut"] = dn_ut
                        out["time_to_dn_s"] = dn_ut - ut0
            except Exception:
                pass

            # Basic orbital elements of target
            try:
                o = tb.orbit
                out["target_sma_m"] = getattr(o, "semi_major_axis", None)
                out["target_period_s"] = getattr(o, "period", None)
                out["target_inclination_deg"] = getattr(o, "inclination", None)
                out["target_lan_deg"] = getattr(o, "longitude_of_ascending_node", None)
            except Exception:
                pass
            return out
    except Exception:
        pass

    # Fallback: SpaceCenter-level target body
    try:
        tb2 = getattr(sc, "target_body", None)
        if tb2 is not None:
            out["target_type"] = "body"
            out["name"] = tb2.name
            vb = v.orbit.body
            parent_v = getattr(getattr(vb, "orbit", None), "reference_body", None)
            parent_t = getattr(getattr(tb2, "orbit", None), "reference_body", None)

            # Moon-of-vessel-body case
            try:
                if parent_t is not None and parent_t == vb:
                    ref = getattr(vb, "non_rotating_reference_frame", vb.reference_frame)
                    p_v = v.position(ref)
                    p_t = tb2.position(ref)
                    out["phase_angle_deg"] = _phase_angle_deg(p_v, p_t)
                    vt = tb2.velocity(ref); rt = tb2.position(ref)
                    h2 = [rt[1]*vt[2]-rt[2]*vt[1], rt[2]*vt[0]-rt[0]*vt[2], rt[0]*vt[1]-rt[1]*vt[0]]
                    ut0 = sc.ut
                    period = getattr(v.orbit, 'period', None)
                    an_ut, dn_ut = _find_next_nodes(v.orbit, ref, h2, ut0, period)
                    if an_ut:
                        out["next_an_ut"] = an_ut
                        out["time_to_an_s"] = an_ut - ut0
                    if dn_ut:
                        out["next_dn_ut"] = dn_ut
                        out["time_to_dn_s"] = dn_ut - ut0
            except Exception:
                pass

            # Common parent case
            try:
                if parent_v is not None and parent_v == parent_t:
                    ref = getattr(parent_v, "non_rotating_reference_frame", parent_v.reference_frame)
                    p_vb = vb.position(ref)
                    p_tb = tb2.position(ref)
                    out.setdefault("phase_angle_deg", _phase_angle_deg(p_vb, p_tb))
                    vt = tb2.velocity(ref); rt = tb2.position(ref)
                    h2 = [rt[1]*vt[2]-rt[2]*vt[1], rt[2]*vt[0]-rt[0]*vt[2], rt[0]*vt[1]-rt[1]*vt[0]]
                    ut0 = sc.ut
                    period = getattr(v.orbit, 'period', None)
                    an_ut, dn_ut = _find_next_nodes(v.orbit, ref, h2, ut0, period)
                    if an_ut:
                        out["next_an_ut"] = an_ut
                        out["time_to_an_s"] = an_ut - ut0
                    if dn_ut:
                        out["next_dn_ut"] = dn_ut
                        out["time_to_dn_s"] = dn_ut - ut0
            except Exception:
                pass

            try:
                o = tb2.orbit
                out["target_sma_m"] = getattr(o, "semi_major_axis", None)
                out["target_period_s"] = getattr(o, "period", None)
                out["target_inclination_deg"] = getattr(o, "inclination", None)
                out["target_lan_deg"] = getattr(o, "longitude_of_ascending_node", None)
            except Exception:
                pass
            return out
    except Exception:
        pass

    out["target_type"] = None
    return out


def list_bodies(conn) -> List[Dict[str, Any]]:
    sc = conn.space_center
    out: List[Dict[str, Any]] = []
    try:
        bodies = getattr(sc, "bodies", {}) or {}
        for name, b in bodies.items():
            item = {
                "name": name,
                "parent": getattr(getattr(getattr(b, "orbit", None), "reference_body", None), "name", None),
                "has_atmosphere": bool(getattr(b, "atmosphere", getattr(b, "has_atmosphere", False))),
                "radius_m": getattr(b, "equatorial_radius", None),
                "soi_radius_m": getattr(b, "sphere_of_influence", None),
            }
            out.append(item)
    except Exception:
        pass
    return out


def list_vessels(conn) -> List[Dict[str, Any]]:
    sc = conn.space_center
    v = sc.active_vessel
    out: List[Dict[str, Any]] = []
    cb = None
    ref = None
    vp = None
    try:
        cb = v.orbit.body
        ref = getattr(cb, "non_rotating_reference_frame", cb.reference_frame)
        vp = v.position(ref)
    except Exception:
        ref = None
        vp = None
    try:
        for ov in sc.vessels:
            item = {
                "name": ov.name,
                "type": _enum_name(getattr(ov, "type", None)),
                "situation": _enum_name(getattr(ov, "situation", None)),
            }
            if ref is not None and vp is not None:
                try:
                    tp = ov.position(ref)
                    dp = [tp[i] - vp[i] for i in range(3)]
                    item["distance_m"] = sqrt(dp[0] ** 2 + dp[1] ** 2 + dp[2] ** 2)
                except Exception:
                    pass
            if ov.id == v.id:
                item["self"] = True
                item.setdefault("distance_m", 0.0)
            out.append(item)
    except Exception:
        pass
    # Sort by distance if available
    try:
        out.sort(key=lambda x: (x.get("distance_m") is None, x.get("distance_m", 0)))
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


def _engine_isp(e, env: str) -> float | None:
    try:
        if env == "vacuum":
            for attr in ("vacuum_specific_impulse", "isp_vacuum", "vacuum_isp"):
                v = getattr(e, attr, None)
                if v:
                    return float(v)
        elif env == "sea_level":
            for attr in ("sea_level_specific_impulse", "isp_sea_level", "sea_level_isp"):
                v = getattr(e, attr, None)
                if v:
                    return float(v)
        # Fallback to current environment
        v = getattr(e, "specific_impulse", None)
        if v:
            return float(v)
    except Exception:
        return None
    return None


def stage_plan_approx(conn, environment: str = "current") -> Dict[str, Any]:
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
                if environment == "current":
                    isp = float(getattr(e, "specific_impulse", 0.0) or 0.0)
                elif environment in ("vacuum", "sea_level"):
                    isp = _engine_isp(e, environment) or float(getattr(e, "specific_impulse", 0.0) or 0.0)
                else:
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
