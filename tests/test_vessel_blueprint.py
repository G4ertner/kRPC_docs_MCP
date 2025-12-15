from __future__ import annotations

from mcp_server.utils.krpc_utils import readers


class _FakeBody:
    name = "Kerbin"


class _FakeOrbit:
    body = _FakeBody()


class _FakeControl:
    current_stage = 0


class _FakePart:
    def __init__(self, title: str) -> None:
        self.title = title


class _FakeEngine:
    def __init__(self) -> None:
        self.part = _FakePart('LV-909 "Terrier" Liquid Fuel Engine')
        self.max_thrust = 60000.0
        self.throttle = 0.0
        self.vacuum_specific_impulse = 345.0
        self.sea_level_specific_impulse = 85.0
        self.specific_impulse = 86.8


class _FakeParts:
    def __init__(self, engines: list[_FakeEngine]) -> None:
        self.engines = engines
        self.all = [e.part for e in engines]

    def __getattr__(self, _name: str):
        return []


class _FakeVessel:
    def __init__(self, engines: list[_FakeEngine]) -> None:
        self.name = "TestVessel"
        self.mass = 123.0
        self.control = _FakeControl()
        self.orbit = _FakeOrbit()
        self.situation = "pre_launch"
        self.parts = _FakeParts(engines)
        self.reference_frame = None


class _FakeSpaceCenter:
    def __init__(self, vessel: _FakeVessel) -> None:
        self.active_vessel = vessel


class _FakeConn:
    def __init__(self, vessel: _FakeVessel) -> None:
        self.space_center = _FakeSpaceCenter(vessel)


def test_vessel_blueprint_includes_sea_level_and_vacuum_isp(monkeypatch):
    monkeypatch.setattr(readers, "part_tree", lambda _conn: {"parts": []})
    monkeypatch.setattr(readers, "stage_plan_approx", lambda _conn, environment="current": {"stages": []})

    engine = _FakeEngine()
    conn = _FakeConn(_FakeVessel([engine]))

    bp = readers.vessel_blueprint(conn)
    assert bp["engines"][0]["isp_vacuum_s"] == 345.0
    assert bp["engines"][0]["isp_sea_level_s"] == 85.0
    assert "specific_impulse_s" not in bp["engines"][0]

