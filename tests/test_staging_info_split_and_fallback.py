from __future__ import annotations

from mcp_server.utils.krpc_utils import readers


class _FakeBody:
    surface_gravity = 9.81


class _FakeOrbit:
    body = _FakeBody()


class _FakeControl:
    def __init__(self, current_stage: int) -> None:
        self.current_stage = current_stage


class _FakePart:
    def __init__(self, *, stage: int | None = None, decouple_stage: int | None = None, dry_mass: float = 0.0) -> None:
        self.stage = stage
        self.decouple_stage = decouple_stage
        self.dry_mass = dry_mass


class _FakePropellant:
    def __init__(self, name: str, total_resource_available: float) -> None:
        self.name = name
        self.total_resource_available = total_resource_available


class _FakeEngine:
    def __init__(
        self,
        *,
        stage: int,
        max_thrust: float = 1000.0,
        specific_impulse: float = 300.0,
        propellant_names: list[str] | None = None,
        propellants: list[_FakePropellant] | None = None,
    ) -> None:
        self.part = _FakePart(stage=stage)
        self.max_thrust = max_thrust
        self.specific_impulse = specific_impulse
        self.propellant_names = propellant_names or []
        self.propellants = propellants or []


class _FakeResources:
    def __init__(self, amounts: dict[str, float]) -> None:
        self._amounts = amounts

    @property
    def names(self) -> list[str]:
        return list(self._amounts.keys())

    def amount(self, name: str) -> float:
        return float(self._amounts.get(name, 0.0))


class _FakeParts:
    def __init__(self, engines: list[_FakeEngine], all_parts: list[_FakePart]) -> None:
        self.engines = engines
        self.all = all_parts

    def __getattr__(self, _name: str):
        return []


class _FakeVessel:
    def __init__(
        self,
        *,
        mass: float,
        current_stage: int,
        engines: list[_FakeEngine],
        all_parts: list[_FakePart] | None = None,
        resources_by_decouple_stage: dict[int, _FakeResources] | None = None,
    ) -> None:
        self.mass = mass
        self.control = _FakeControl(current_stage)
        self.orbit = _FakeOrbit()
        self.parts = _FakeParts(engines, all_parts or [])
        self._resources_by_decouple_stage = resources_by_decouple_stage or {}

    def resources_in_decouple_stage(self, stage: int, _cumulative: bool):
        return self._resources_by_decouple_stage.get(stage, _FakeResources({}))


class _FakeGlobalResources:
    @staticmethod
    def density(name: str) -> float:
        return {
            "LiquidFuel": 5.0,
            "Oxidizer": 5.0,
            "MonoPropellant": 4.0,
            "SolidFuel": 7.5,
            "XenonGas": 0.1,
            "Ore": 10.0,
            "ElectricCharge": 0.0,
        }.get(name, 0.0)


class _FakeSpaceCenter:
    def __init__(self, vessel: _FakeVessel) -> None:
        self.active_vessel = vessel
        self.resources = _FakeGlobalResources()


class _FakeConn:
    def __init__(self, vessel: _FakeVessel) -> None:
        self.space_center = _FakeSpaceCenter(vessel)


def _stages_by_number(result: dict) -> dict[int, dict]:
    return {seg["stage"]: seg for seg in result["stages"]}


def test_new_staging_info_shifts_propellant_to_engine_stage():
    # Stage 6 has engines, but its propellant is in decouple stage 5 (classic staging layout).
    engines = [
        _FakeEngine(stage=6, propellant_names=["LiquidFuel", "Oxidizer"]),
        _FakeEngine(stage=6, propellant_names=["LiquidFuel", "Oxidizer"]),
        _FakeEngine(stage=6, propellant_names=["LiquidFuel", "Oxidizer"]),
    ]
    resources = {
        5: _FakeResources({"LiquidFuel": 3200.0}),  # 3200 * 5 kg = 16000 kg
        6: _FakeResources({}),
    }
    conn = _FakeConn(_FakeVessel(mass=20_000.0, current_stage=6, engines=engines, resources_by_decouple_stage=resources))

    legacy = readers.staging_info_legacy(conn)
    legacy_by_stage = _stages_by_number(legacy)
    assert legacy_by_stage[6]["engines"] == 3
    assert legacy_by_stage[6]["prop_mass_kg"] == 0.0
    assert legacy_by_stage[5]["engines"] == 0
    assert legacy_by_stage[5]["prop_mass_kg"] == 16000.0

    new = readers.staging_info(conn)
    new_by_stage = _stages_by_number(new)
    assert new_by_stage[6]["engines"] == 3
    assert new_by_stage[6]["prop_mass_kg"] == 16000.0
    assert new_by_stage[5]["engines"] == 0
    assert new_by_stage[5]["prop_mass_kg"] == 0.0


def test_new_staging_info_falls_back_to_engine_propellant_availability_for_final_stage():
    engines = [
        _FakeEngine(
            stage=0,
            propellant_names=["LiquidFuel"],
            propellants=[_FakePropellant("LiquidFuel", total_resource_available=50.0)],
        )
    ]
    conn = _FakeConn(_FakeVessel(mass=1000.0, current_stage=0, engines=engines, resources_by_decouple_stage={}))

    data = readers.staging_info(conn)
    by_stage = _stages_by_number(data)
    assert by_stage[0]["prop_mass_kg"] == 250.0
    assert by_stage[0]["m0_kg"] == 1000.0
    assert by_stage[0]["m1_kg"] == 750.0

