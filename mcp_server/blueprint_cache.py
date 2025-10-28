from __future__ import annotations

import json
import base64
from typing import Any, Dict

from .server import mcp

_LATEST_BLUEPRINT_JSON: str | None = None
_LAST_SVG: str | None = None
_LAST_PNG: bytes | None = None


def set_latest_blueprint(bp: Dict[str, Any] | str) -> None:
    global _LATEST_BLUEPRINT_JSON
    if isinstance(bp, str):
        _LATEST_BLUEPRINT_JSON = bp
    else:
        try:
            _LATEST_BLUEPRINT_JSON = json.dumps(bp)
        except Exception:
            _LATEST_BLUEPRINT_JSON = json.dumps({"error": "Failed to serialize blueprint"})


def set_last_diagram(*, svg: str | None, png_bytes: bytes | None) -> None:
    global _LAST_SVG, _LAST_PNG
    _LAST_SVG = svg
    _LAST_PNG = png_bytes


@mcp.resource("resource://blueprints/latest")
def get_latest_blueprint() -> str:
    """Return the most recently generated vessel blueprint as JSON, if available.

    Call the get_vessel_blueprint tool first to refresh this cache.
    """
    return _LATEST_BLUEPRINT_JSON or json.dumps({"error": "No cached blueprint. Call get_vessel_blueprint first."})


@mcp.resource("resource://blueprints/last-diagram.svg")
def get_last_svg() -> str:
    return _LAST_SVG or "(no SVG diagram cached; call export_blueprint_diagram)"


@mcp.resource("resource://blueprints/last-diagram.png")
def get_last_png() -> str:
    if _LAST_PNG is None:
        return "(no PNG diagram cached; call export_blueprint_diagram with format='png' or 'both')"
    # Base64-encode PNG so clients without byte support can still render
    b64 = json.dumps({
        "mime": "image/png",
        "data_base64": base64.b64encode(_LAST_PNG).decode('ascii'),
    })
    return b64
