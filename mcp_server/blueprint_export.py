from __future__ import annotations

import base64
import datetime as _dt
import os
from pathlib import Path
import json
from typing import Any, Dict, List

from .krpc.client import connect_to_game
from .krpc import readers
from .blueprint_cache import set_latest_blueprint
from .server import mcp


def _make_svg(bp: Dict[str, Any]) -> str:
    meta = bp.get("meta", {})
    stages = bp.get("stages") or []

    # Layout constants
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
    # Header
    title = f"Vessel: {meta.get('vessel_name')} — Body: {meta.get('body')} — Situation: {meta.get('situation')} — Mass: {meta.get('mass_kg')} kg"
    svg.append(f"<text x='{pad}' y='{pad+24}' fill='#eaeef2' font-family='monospace' font-size='18'>{esc(title)}</text>")
    svg.append(f"<text x='{pad}' y='{pad+46}' fill='#9fb3c8' font-family='monospace' font-size='12'>Stage | Engines | Δv (m/s) | TWR | Eng/Tank/Dec/Par/Dock</text>")

    y = header_h
    # Build per-stage part counts from parts[]
    from collections import defaultdict
    parts = bp.get("parts") or []
    by_stage = defaultdict(list)
    for p in parts:
        s = p.get('stage')
        if s is None or s < 0:
            s = p.get('decouple_stage')
        by_stage[s].append(p)

    def has_resource_tank(p):
        res = p.get('resources') or {}
        return any(r in res and (res[r] or {}).get('max', 0) > 0 for r in ('LiquidFuel','Oxidizer','MonoPropellant','SolidFuel'))

    def is_decoupler(p):
        mods = p.get('modules') or []
        if 'Decoupler' in mods or 'Separator' in mods:
            return True
        t = (p.get('title') or '') + ' ' + (p.get('name') or '')
        return ('Decoupler' in t) or ('Separator' in t) or ('radialDecoupler' in t)

    def is_parachute(p):
        mods = p.get('modules') or []
        if 'Parachute' in mods:
            return True
        t = (p.get('title') or '') + ' ' + (p.get('name') or '')
        return ('Parachute' in t)

    def is_docking_port(p):
        mods = p.get('modules') or []
        if 'DockingPort' in mods:
            return True
        t = (p.get('title') or '') + ' ' + (p.get('name') or '')
        return ('Dock' in t) or ('docking' in t.lower())

    row_idx = 0
    for seg in sorted(stages, key=lambda x: x.get('stage', 0), reverse=True) or [{"stage": "-", "engines": 0}]:
        s = seg.get('stage')
        sparts = by_stage.get(s, [])
        eng = int(seg.get('engines') or 0)
        tank = sum(1 for p in sparts if has_resource_tank(p))
        dec = sum(1 for p in sparts if is_decoupler(p))
        par = sum(1 for p in sparts if is_parachute(p))
        dock = sum(1 for p in sparts if is_docking_port(p))
        dv = seg.get('delta_v_m_s')
        twr = seg.get('twr_surface')

        row_y = y + row_idx * (row_h + pad)
        svg.append(f"<rect x='{pad}' y='{row_y}' width='{width-2*pad}' height='{row_h}' rx='6' ry='6' fill='#16212b' stroke='#233140' />")
        text = f"{s:>5} | {eng:>2} | {('-' if dv is None else int(dv)) :>6} | {('-' if twr is None else f'{twr:.2f}') :>4} | {eng}/{tank}/{dec}/{par}/{dock}"
        svg.append(f"<text x='{pad+12}' y='{row_y+32}' fill='#dce3ea' font-family='monospace' font-size='16'>{esc(text)}</text>")
        row_idx += 1

    svg.append("</svg>")
    return "".join(svg)


def _try_png(bp: Dict[str, Any], out_path: Path) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    meta = bp.get("meta", {})
    stages = bp.get("stages") or []
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
    # Header
    title = f"Vessel: {meta.get('vessel_name')} — Body: {meta.get('body')} — Situation: {meta.get('situation')} — Mass: {meta.get('mass_kg')} kg"
    d.text((pad, pad), title, fill=(234,238,242), font=font_b)
    d.text((pad, pad+24), "Stage | Engines | Δv (m/s) | TWR | Eng/Tank/Dec/Par/Dock", fill=(159,179,200), font=font)

    # Part counts
    from collections import defaultdict
    parts = bp.get("parts") or []
    by_stage = defaultdict(list)
    for p in parts:
        s = p.get('stage')
        if s is None or s < 0:
            s = p.get('decouple_stage')
        by_stage[s].append(p)

    def count_mod(stage_parts, label):
        c = 0
        for p in stage_parts:
            mods = p.get("modules") or []
            if label in mods:
                c += 1
        return c

    y = header_h
    for idx, seg in enumerate(sorted(stages, key=lambda x: x.get('stage', 0), reverse=True) or [{"stage": "-", "engines": 0}]):
        s = seg.get('stage')
        sparts = by_stage.get(s, [])
        eng = int(seg.get('engines') or 0)
        tank = sum(1 for p in sparts if has_resource_tank(p))
        dec = sum(1 for p in sparts if is_decoupler(p))
        par = sum(1 for p in sparts if is_parachute(p))
        dock = sum(1 for p in sparts if is_docking_port(p))
        dv = seg.get('delta_v_m_s')
        twr = seg.get('twr_surface')

        row_y = y + idx * (row_h + pad)
        d.rounded_rectangle((pad, row_y, width-pad, row_y+row_h), radius=6, fill=(22,33,43), outline=(35,49,64))
        text = f"{s:>5} | {eng:>2} | {('-' if dv is None else int(dv)) :>6} | {('-' if twr is None else f'{twr:.2f}') :>4} | {eng}/{tank}/{dec}/{par}/{dock}"
        d.text((pad+12, row_y+16), text, fill=(220,227,234), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return True


@mcp.tool()
def export_blueprint_diagram(
    address: str,
    rpc_port: int = 50000,
    stream_port: int = 50001,
    name: str | None = None,
    *,
    format: str = "svg",  # 'svg' | 'png' | 'both'
    out_dir: str | None = None,
) -> str:
    """
    Export a simple 2D vessel blueprint diagram and expose as resources.

    When to use:
      - Visualize the craft by stage to verify staging/structure and share with the agent.

    Args:
      address/rpc_port/stream_port/name: kRPC connection settings
      format: 'svg' | 'png' | 'both' (png requires Pillow)
      out_dir: Optional output directory for saved files (default: ./artifacts/blueprints)

    Returns:
      JSON: { uri_svg?, uri_png?, saved_path_svg?, saved_path_png?, note? }
    """
    conn = connect_to_game(address, rpc_port=rpc_port, stream_port=stream_port, name=name)
    bp = readers.vessel_blueprint(conn)
    set_latest_blueprint(bp)

    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    base = Path(out_dir or (Path.cwd() / "artifacts" / "blueprints"))
    base.mkdir(parents=True, exist_ok=True)
    stem = f"blueprint_{ts}"

    # SVG always
    svg_text = _make_svg(bp)
    svg_path = base / f"{stem}.svg"
    svg_path.write_text(svg_text, encoding="utf-8")

    # Update resources cache for last diagram
    from .blueprint_cache import set_last_diagram
    set_last_diagram(svg=svg_text, png_bytes=None)

    result: Dict[str, Any] = {
        "uri_svg": "resource://blueprints/last-diagram.svg",
        "saved_path_svg": str(svg_path),
    }

    fmt = (format or "svg").lower()
    if fmt in ("png", "both"):
        png_path = base / f"{stem}.png"
        ok = _try_png(bp, png_path)
        if ok:
            # Store minimal pointer; resource will serve if available
            with png_path.open("rb") as f:
                png_bytes = f.read()
            set_last_diagram(svg=svg_text, png_bytes=png_bytes)
            result.update({
                "uri_png": "resource://blueprints/last-diagram.png",
                "saved_path_png": str(png_path),
            })
        else:
            result["note"] = "PNG export requires Pillow. Install with 'uv pip install pillow' or add extras."

    return json.dumps(result)
