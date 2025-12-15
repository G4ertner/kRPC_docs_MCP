from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.general_tools_impl import orbit_and_navigation
from mcp_server.general_tools_impl import flight_and_control
from mcp_server.utils.json_utils import dumps as json_dumps


def test_json_dumps_converts_non_finite_numbers_to_null():
    out = json_dumps(
        {
            "finite": 1.25,
            "pos_inf": float("inf"),
            "neg_inf": float("-inf"),
            "nan": float("nan"),
            "nested": [float("inf"), {"x": float("nan")}],
        }
    )
    parsed = json.loads(out)

    assert parsed["finite"] == 1.25
    assert parsed["pos_inf"] is None
    assert parsed["neg_inf"] is None
    assert parsed["nan"] is None
    assert parsed["nested"][0] is None
    assert parsed["nested"][1]["x"] is None


def test_get_orbit_info_does_not_emit_bare_infinity(monkeypatch):
    class _DummyConn:
        def close(self) -> None:
            return

    def _fake_open_connection(*_args, **_kwargs):
        return _DummyConn()

    def _fake_orbit_info(_conn):
        return {
            "body": "Mun",
            "apoapsis_altitude_m": -1106360.3271848965,
            "time_to_apoapsis_s": float("inf"),
            "periapsis_altitude_m": 19599.75923881223,
            "time_to_periapsis_s": 4438.706167025549,
            "eccentricity": 1.6395234947620128,
            "inclination_deg": 3.0739103549301907,
            "lan_deg": 1.8640874913624068,
            "argument_of_periapsis_deg": 2.229539320943627,
            "semi_major_axis_m": -343380.2839730421,
            "period_s": float("inf"),
        }

    monkeypatch.setattr(orbit_and_navigation, "open_connection", _fake_open_connection)
    monkeypatch.setattr(orbit_and_navigation.readers, "orbit_info", _fake_orbit_info)

    raw = orbit_and_navigation.get_orbit_info()
    assert "Infinity" not in raw
    parsed = json.loads(raw)
    assert parsed["time_to_apoapsis_s"] is None
    assert parsed["period_s"] is None


def test_get_attitude_status_does_not_emit_bare_nan(monkeypatch):
    class _DummyConn:
        def close(self) -> None:
            return

    def _fake_open_connection(*_args, **_kwargs):
        return _DummyConn()

    def _fake_attitude_status(_conn):
        return {
            "sas": True,
            "sas_mode": "stability_assist",
            "rcs": False,
            "throttle": 0.0,
            "autopilot_state": "disengaged",
            "autopilot_target_pitch": 90.0,
            "autopilot_target_heading": 90.0,
            "autopilot_target_roll": float("nan"),
        }

    monkeypatch.setattr(flight_and_control, "open_connection", _fake_open_connection)
    monkeypatch.setattr(flight_and_control.readers, "attitude_status", _fake_attitude_status)

    raw = flight_and_control.get_attitude_status()
    assert "NaN" not in raw
    parsed = json.loads(raw)
    assert parsed["autopilot_target_roll"] is None
