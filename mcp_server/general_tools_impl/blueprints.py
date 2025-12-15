from __future__ import annotations

import base64
import datetime as _dt
import os
from pathlib import Path
from typing import Any, Dict, List

from ..utils.krpc_utils import readers
from ..utils.krpc_utils.client import connect_to_game
from ..utils.json_utils import dumps as json_dumps
from ..utils.krpc_helpers import DEFAULT_KRPC_ADDRESS

_LATEST_STAGING_JSON: str | None = None
_LATEST_VESSEL_BLUEPRINT_JSON: str | None = None
_LAST_SVG: str | None = None
_LAST_PNG: bytes | None = None
_BLUEPRINT_DIR = Path.cwd() / "artifacts" / "blueprints"
_EXPORTED_FILES: dict[str, Path] = {}


def _register_exported_file(path: Path) -> None:
    # Store by basename to avoid path traversal through the resource route.
    _EXPORTED_FILES[path.name] = path


def _set_latest_json(cache_key: str, payload: Dict[str, Any] | str) -> None:
    global _LATEST_STAGING_JSON, _LATEST_VESSEL_BLUEPRINT_JSON
    try:
        json_payload = payload if isinstance(payload, str) else json_dumps(payload)
    except Exception:
        json_payload = json_dumps({"error": f"Failed to serialize {cache_key} payload"})

    if cache_key == "staging":
        _LATEST_STAGING_JSON = json_payload
    elif cache_key == "vessel_blueprint":
        _LATEST_VESSEL_BLUEPRINT_JSON = json_payload
    else:
        raise ValueError(f"Unknown cache_key: {cache_key}")


def set_latest_staging(stage_plan: Dict[str, Any] | str) -> None:
    _set_latest_json("staging", stage_plan)


def set_latest_vessel_blueprint(bp: Dict[str, Any] | str) -> None:
    _set_latest_json("vessel_blueprint", bp)


def set_last_diagram(*, svg: str | None, png_bytes: bytes | None) -> None:
    global _LAST_SVG, _LAST_PNG
    _LAST_SVG = svg
    _LAST_PNG = png_bytes


def get_latest_staging() -> str:
    return _LATEST_STAGING_JSON or json_dumps({"error": "No cached staging JSON. Call get_stage_plan or export_blueprint_diagram first."})


def get_latest_vessel_blueprint() -> str:
    return _LATEST_VESSEL_BLUEPRINT_JSON or json_dumps({"error": "No cached vessel blueprint. Call get_vessel_blueprint first."})


def get_last_svg() -> str:
    return _LAST_SVG or "(no SVG diagram cached; call export_blueprint_diagram)"


def get_last_png() -> str:
    if _LAST_PNG is None:
        return "(no PNG diagram cached; call export_blueprint_diagram with format='png' or 'both')"
    b64 = json_dumps({
        "mime": "image/png",
        "data_base64": base64.b64encode(_LAST_PNG).decode('ascii'),
    })
    return b64


def resource_payload_for(filename: str) -> str:
    safe_name = Path(filename).name
    path = _EXPORTED_FILES.get(safe_name) or (_BLUEPRINT_DIR / safe_name)
    if not path.exists():
        return json_dumps({"error": f"Blueprint diagram '{safe_name}' not found. Call export_blueprint_diagram first."})

    suffix = path.suffix.lower()
    if suffix == ".svg":
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return path.read_text()
    if suffix == ".png":
        data = path.read_bytes()
        return json_dumps({
            "filename": safe_name,
            "mime": "image/png",
            "data_base64": base64.b64encode(data).decode("ascii"),
        })
    return json_dumps({"error": f"Unsupported blueprint diagram format '{suffix}'.", "filename": safe_name})


def export_blueprint_diagram(
    address: str = DEFAULT_KRPC_ADDRESS,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    *,
    format: str = "svg",
    out_dir: str | None = None,
) -> str:
    conn = connect_to_game(address, rpc_port=rpc_port, stream_port=stream_port, name=name)
    v = conn.space_center.active_vessel
    meta = {
        "vessel_name": getattr(v, "name", None),
        "body": getattr(getattr(v, "orbit", None), "body", None).name if getattr(getattr(v, "orbit", None), "body", None) is not None else None,
        "situation": getattr(getattr(v, "situation", None), "name", None) if hasattr(getattr(v, "situation", None), "name") else str(getattr(v, "situation", None)),
        "mass_kg": getattr(v, "mass", None),
    }
    stage_plan = readers.stage_plan_approx(conn, environment="current")
    stages = stage_plan.get("stages", []) if isinstance(stage_plan, dict) else []
    from collections import defaultdict

    counts_by_stage: Dict[Any, Dict[str, int]] = defaultdict(lambda: {"tank": 0, "dec": 0, "par": 0, "dock": 0})

    def stage_of(obj):
        p = getattr(obj, "part", None) or obj
        s = getattr(p, "stage", None)
        if s is None or (isinstance(s, int) and s < 0):
            s = getattr(p, "decouple_stage", None)
        return s

    try:
        for d in list(getattr(v.parts, "decouplers", []) or []) + list(getattr(v.parts, "separators", []) or []):
            counts_by_stage[stage_of(d)]["dec"] += 1
    except Exception:
        pass
    try:
        for c in list(getattr(v.parts, "parachutes", []) or []):
            counts_by_stage[stage_of(c)]["par"] += 1
    except Exception:
        pass
    try:
        for dp in list(getattr(v.parts, "docking_ports", []) or []):
            counts_by_stage[stage_of(dp)]["dock"] += 1
    except Exception:
        pass
    try:
        for tank in list(getattr(v.parts, "fuel_tanks", []) or []):
            counts_by_stage[stage_of(tank)]["tank"] += 1
    except Exception:
        pass

    base_dir = Path(out_dir) if out_dir else _BLUEPRINT_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    result = {"note": "Blueprint diagram generated."}
    svg_data = _make_svg_fast(meta, stages, counts_by_stage)
    svg_path = base_dir / f"blueprint_{timestamp}.svg"
    svg_path.write_text(svg_data, encoding="utf-8")
    _register_exported_file(svg_path)
    result["saved_path_svg"] = str(svg_path)
    result["uri_svg"] = f"resource://blueprints/{svg_path.name}"
    result["uri_last_svg"] = "resource://blueprints/last-diagram.svg"

    png_path = None
    if format in {"png", "both"}:
        png_path = base_dir / f"blueprint_{timestamp}.png"
        if _try_png_fast(meta, stages, counts_by_stage, png_path):
            _register_exported_file(png_path)
            result["saved_path_png"] = str(png_path)
            result["uri_png"] = f"resource://blueprints/{png_path.name}"
            result["uri_last_png"] = "resource://blueprints/last-diagram.png"
        else:
            result["note"] = result.get("note", "") + " PNG generation failed (missing Pillow)."

    set_latest_staging(stage_plan)
    set_last_diagram(svg=svg_data, png_bytes=png_path.read_bytes() if png_path and png_path.exists() else None)
    return json_dumps(result)


def _make_svg_fast(meta: Dict[str, Any], stages: List[Dict[str, Any]], counts_by_stage: Dict[Any, Dict[str, int]]) -> str:
    width = 900
    header_h = 60
    row_h = 50
    pad = 10
    rows = len(stages) if stages else 1
    height = header_h + rows * (row_h + pad) + pad

    def esc(t: Any) -> str:
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    svg: List[str] = []
    svg.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>")
    svg.append(f"<rect x='0' y='0' width='{width}' height='{height}' fill='#0b0f12' />")
    title = f"Vessel: {meta.get('vessel_name')} — Body: {meta.get('body')} — Situation: {meta.get('situation')} — Mass: {meta.get('mass_kg')} kg"
    svg.append(f"<text x='{pad}' y='{pad+24}' fill='#eaeef2' font-family='monospace' font-size='18'>{esc(title)}</text>")
    svg.append(f"<text x='{pad}' y='{pad+46}' fill='#9fb3c8' font-family='monospace' font-size='12'>Stage | Engines | Δv (m/s) | TWR | Eng/Tank/Dec/Par/Dock</text>")

    y = header_h
    row_idx = 0
    for seg in sorted(stages, key=lambda x: x.get('stage', 0), reverse=True) or [{"stage": "-", "engines": 0}]:
        s = seg.get('stage')
        c = counts_by_stage.get(s, {"tank":0,"dec":0,"par":0,"dock":0})
        eng = int(seg.get('engines') or 0)
        tank = int(c.get('tank', 0))
        dec = int(c.get('dec', 0))
        par = int(c.get('par', 0))
        dock = int(c.get('dock', 0))
        dv = seg.get('delta_v_m_s')
        twr = seg.get('twr_surface')

        row_y = y + row_idx * (row_h + pad)
        svg.append(f"<rect x='{pad}' y='{row_y}' width='{width-2*pad}' height='{row_h}' rx='6' ry='6' fill='#16212b' stroke='#233140' />")
        text = f"{s:>5} | {eng:>2} | {('-' if dv is None else int(dv)) :>6} | {('-' if twr is None else f'{twr:.2f}') :>4} | {eng}/{tank}/{dec}/{par}/{dock}"
        svg.append(f"<text x='{pad+12}' y='{row_y+32}' fill='#dce3ea' font-family='monospace' font-size='16'>{esc(text)}</text>")
        row_idx += 1

    svg.append("</svg>")
    return "".join(svg)


def _try_png_fast(meta: Dict[str, Any], stages: List[Dict[str, Any]], counts_by_stage: Dict[Any, Dict[str, int]], out_path: Path) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    width = 1000
    header_h = 80
    row_h = 52
    pad = 10
    rows = len(stages) if stages else 1
    height = header_h + rows * (row_h + pad) + pad
    img = Image.new("RGB", (width, height), (11, 15, 18))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
        font_b = ImageFont.load_default()
    except Exception:
        font = None; font_b = None
    title = f"Vessel: {meta.get('vessel_name')} — Body: {meta.get('body')} — Situation: {meta.get('situation')} — Mass: {meta.get('mass_kg')} kg"
    d.text((pad, pad), title, fill=(234,238,242), font=font_b)
    d.text((pad, pad+24), "Stage | Engines | Δv (m/s) | TWR | Eng/Tank/Dec/Par/Dock", fill=(159,179,200), font=font)

    y = header_h
    for idx, seg in enumerate(sorted(stages, key=lambda x: x.get('stage', 0), reverse=True) or [{"stage": "-", "engines": 0}]):
        s = seg.get('stage')
        c = counts_by_stage.get(s, {"tank":0,"dec":0,"par":0,"dock":0})
        eng = int(seg.get('engines') or 0)
        tank = int(c.get('tank', 0))
        dec = int(c.get('dec', 0))
        par = int(c.get('par', 0))
        dock = int(c.get('dock', 0))
        dv = seg.get('delta_v_m_s')
        twr = seg.get('twr_surface')

        row_y = y + idx * (row_h + pad)
        d.rounded_rectangle((pad, row_y, width-pad, row_y+row_h), radius=6, fill=(22,33,43), outline=(35,49,64))
        text = f"{s:>5} | {eng:>2} | {('-' if dv is None else int(dv)) :>6} | {('-' if twr is None else f'{twr:.2f}') :>4} | {eng}/{tank}/{dec}/{par}/{dock}"
        d.text((pad+12, row_y+16), text, fill=(220,227,234), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return True
