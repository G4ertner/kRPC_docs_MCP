from __future__ import annotations

import base64
import json
from pathlib import Path

import mcp_server.general_tools_impl.blueprints as blueprints


def test_resource_payload_for_svg_reads_text(tmp_path: Path):
    blueprints._BLUEPRINT_DIR = tmp_path
    blueprints._EXPORTED_FILES.clear()

    svg = tmp_path / "blueprint_test.svg"
    svg.write_text("<svg>ok</svg>", encoding="utf-8")

    payload = blueprints.resource_payload_for("blueprint_test.svg")
    assert payload == "<svg>ok</svg>"


def test_resource_payload_for_png_returns_base64_json(tmp_path: Path):
    blueprints._BLUEPRINT_DIR = tmp_path
    blueprints._EXPORTED_FILES.clear()

    png = tmp_path / "blueprint_test.png"
    data = b"\x89PNG\r\n\x1a\nnot-a-real-png"
    png.write_bytes(data)

    payload = json.loads(blueprints.resource_payload_for("blueprint_test.png"))
    assert payload["filename"] == "blueprint_test.png"
    assert payload["mime"] == "image/png"
    assert base64.b64decode(payload["data_base64"]) == data


def test_resource_payload_for_sanitizes_filename(tmp_path: Path):
    blueprints._BLUEPRINT_DIR = tmp_path / "blueprints"
    blueprints._BLUEPRINT_DIR.mkdir(parents=True, exist_ok=True)
    blueprints._EXPORTED_FILES.clear()

    other = tmp_path / "other"
    other.mkdir(parents=True, exist_ok=True)
    (other / "secret.svg").write_text("nope", encoding="utf-8")

    payload = json.loads(blueprints.resource_payload_for("../secret.svg"))
    assert "error" in payload


def test_resource_payload_for_uses_registered_export_path(tmp_path: Path):
    blueprints._BLUEPRINT_DIR = tmp_path / "blueprints"
    blueprints._BLUEPRINT_DIR.mkdir(parents=True, exist_ok=True)
    blueprints._EXPORTED_FILES.clear()

    custom_dir = tmp_path / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    svg = custom_dir / "blueprint_custom.svg"
    svg.write_text("<svg>custom</svg>", encoding="utf-8")

    blueprints._EXPORTED_FILES[svg.name] = svg
    payload = blueprints.resource_payload_for(svg.name)
    assert payload == "<svg>custom</svg>"

