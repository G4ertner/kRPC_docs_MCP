from __future__ import annotations

from .blueprints import set_latest_vessel_blueprint
from ..utils.krpc_utils import readers
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import open_connection
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def get_part_tree(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Hierarchical part tree with staging and module/resource summaries.

    Note:
      This synchronous call can exceed the CLI's 60 s limit on large vessels.
      Prefer start_part_tree_job -> get_job_status(job_id) -> read_resource(result_resource)
      when you need a full tree safely; fall back to this direct call only for quick checks.

    Returns:
      JSON: { parts: [ { id, title, name, tag?, stage, decouple_stage?, parent_id?, children_ids[],
              modules: [...], resources: {R:{amount,max}}, crossfeed? } ] }
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.part_tree(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_vessel_blueprint(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Idealized vessel blueprint combining meta, stage plan, engines, control capabilities, and part tree.

    When to use:
      - Give the agent a structural understanding of the craft before writing scripts.

    Returns:
      JSON with sections: meta, stages, engines, control_capabilities, parts, geometry, notes.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        bp = readers.vessel_blueprint(conn)
        try:
            # Cache for blueprint resource
            set_latest_vessel_blueprint(bp)
        except Exception:
            pass
        return json_dumps(bp)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_blueprint_ascii(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Compact ASCII schematic/summary of the current vessel by stage.

    Includes a header and a per-stage table with engine counts, Δv, TWR,
    and key part category counts (Eng/Tank/Dec/Par/Dock).
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        s = readers.blueprint_ascii(conn)
        return s
    except Exception as e:
        return f"Failed to build ASCII blueprint: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_stage_plan(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, environment: str = "current") -> str:
    """
    Approximate stock‑like staging plan by grouping decouple‑only stages under the
    preceding engine stage.

    Note:
      For big rockets this direct call can exceed the 60 s CLI limit.

    When to use:
      - Match KSP’s staging view for Δv/TWR per engine stage.

    Args:
      environment: 'current' | 'sea_level' | 'vacuum' — controls Isp used

    Returns:
      JSON array of stage rows, sorted ascending by stage number:
        [ { stage, engines, delta_v_m_s (int|null), combined_isp_s, max_thrust_n, twr_surface,
            relevant_parts: [part_title, ...] }, ... ]
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    env = (environment or "current").lower()
    if env not in ("current", "sea_level", "vacuum"):
        env = "current"
    try:
        v = conn.space_center.active_vessel
        raw = readers.stage_plan_approx(conn, environment=env) or {}
        segs = raw.get("stages", []) if isinstance(raw, dict) else []

        seg_by_stage: dict[int, dict] = {}
        for seg in segs:
            try:
                seg_by_stage[int(seg.get("stage"))] = seg
            except Exception:
                continue

        def _safe_stage(x):
            try:
                if x is None:
                    return None
                s = int(x)
                return s if s >= 0 else None
            except Exception:
                return None

        def _module_names(part) -> list[str]:
            try:
                mods = getattr(part, "modules", None)
                if mods is None:
                    return []
                names = []
                for m in list(mods) or []:
                    try:
                        n = getattr(m, "name", None)
                        if n:
                            names.append(str(n))
                    except Exception:
                        continue
                return names
            except Exception:
                return []

        def _has_attr(obj, attr: str) -> bool:
            try:
                return getattr(obj, attr, None) is not None
            except Exception:
                return False

        def _stage_category(part) -> str | None:
            # Prefer kRPC typed accessors when present (fast, reliable).
            if _has_attr(part, "engine"):
                return "engine"
            if _has_attr(part, "decoupler") or _has_attr(part, "separator"):
                return "decouple"
            if _has_attr(part, "parachute"):
                return "parachute"
            if _has_attr(part, "launch_clamp"):
                return "clamp"
            if _has_attr(part, "solar_panel"):
                return "solar"
            if _has_attr(part, "antenna"):
                return "antenna"

            # Module-name heuristics (covers fairings and many modded parts).
            mods = _module_names(part)
            if not mods:
                return None

            for n in mods:
                if n == "ModuleLaunchClamp" or "LaunchClamp" in n:
                    return "clamp"
                if n == "ModuleProceduralFairing" or "ProceduralFairing" in n or "Fairing" in n:
                    return "fairing"
                if n == "ModuleJettison" or "Jettison" in n:
                    return "fairing"
                if "Decouple" in n or "AnchoredDecoupler" in n or "Separator" in n:
                    return "decouple"
                if "Parachute" in n or "RealChute" in n:
                    return "parachute"
                if "Engines" in n or n in ("ModuleEngines", "ModuleEnginesFX"):
                    return "engine"
                if "SolarPanel" in n:
                    return "solar"
                if "Antenna" in n or "DataTransmitter" in n:
                    return "antenna"
                if "ScienceExperiment" in n:
                    return "science"

            return None

        category_order = ("engine", "decouple", "clamp", "fairing", "parachute", "solar", "antenna", "science")
        stage_parts: dict[int, dict[str, list[str]]] = {}
        try:
            for p in list(getattr(v.parts, "all", []) or []):
                s = _safe_stage(getattr(p, "stage", None))
                if s is None:
                    continue
                cat = _stage_category(p)
                if cat is None:
                    continue
                try:
                    title = getattr(p, "title", None) or getattr(p, "name", None) or "Unknown Part"
                except Exception:
                    title = "Unknown Part"
                stage_parts.setdefault(int(s), {}).setdefault(cat, []).append(str(title))
        except Exception:
            stage_parts = {}

        relevant_parts_by_stage: dict[int, list[str]] = {}
        for s, cats in stage_parts.items():
            combined: list[str] = []
            for cat in category_order:
                combined.extend(cats.get(cat, []))
            for cat, items in cats.items():
                if cat not in category_order:
                    combined.extend(items)
            relevant_parts_by_stage[int(s)] = combined

        stage_nums = set(seg_by_stage.keys()) | set(relevant_parts_by_stage.keys())
        out = []
        for s in sorted(stage_nums):
            seg = seg_by_stage.get(int(s), {}) or {}
            dv = seg.get("delta_v_m_s")
            dv_int = None
            try:
                if dv is not None:
                    dv_int = int(round(float(dv)))
            except Exception:
                dv_int = None

            relevant = relevant_parts_by_stage.get(int(s), [])
            if dv_int is None and not relevant:
                continue

            out.append({
                "stage": int(s),
                "engines": int(seg.get("engines") or 0),
                "delta_v_m_s": dv_int,
                "combined_isp_s": seg.get("combined_isp_s"),
                "max_thrust_n": float(seg.get("max_thrust_n") or 0.0),
                "twr_surface": seg.get("twr_surface"),
                "relevant_parts": relevant,
            })

        return json_dumps(out)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_stage_plan_legacy(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, environment: str = "current") -> str:
    """
    Legacy approximate stock-like staging plan.

    Kept for side-by-side comparisons with get_stage_plan.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    env = (environment or "current").lower()
    if env not in ("current", "sea_level", "vacuum"):
        env = "current"
    try:
        return json_dumps(readers.stage_plan_approx_legacy(conn, environment=env))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_staging_plan(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, environment: str = "current") -> str:
    """Alias for get_stage_plan (stock-like staging plan)."""
    return get_stage_plan(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout, environment=environment)


def get_staging_plan_legacy(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0, environment: str = "current") -> str:
    """Alias for get_stage_plan_legacy."""
    return get_stage_plan_legacy(address=address, rpc_port=rpc_port, stream_port=stream_port, name=name, timeout=timeout, environment=environment)


def get_staging_info(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Approximate per-stage delta‑v and TWR plan using current engine Isp and resource masses.

    When to use:
      - Quick staging analysis for mission planning and sanity checks.

    Returns:
      JSON: { current_stage, stages: [ { stage, engines, max_thrust_n,
      combined_isp_s?, delta_v_m_s?, twr_surface?, prop_mass_kg, m0_kg, m1_kg } ] }.

    Note: Uses standard KSP resource densities and current environment Isp; results are estimates.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.staging_info(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_staging_info_legacy(address: str = DEFAULT_KRPC_ADDRESS, rpc_port: int = 50000, stream_port: int = 50001, name: str | None = None, timeout: float = 5.0) -> str:
    """
    Legacy approximate per-stage delta-v/TWR plan.

    Note:
      This legacy implementation is kept for side-by-side comparisons with
      the current get_staging_info behavior.
    """
    conn = open_connection(address, rpc_port, stream_port, name, timeout)
    try:
        return json_dumps(readers.staging_info_legacy(conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass
