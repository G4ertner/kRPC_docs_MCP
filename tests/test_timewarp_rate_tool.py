from __future__ import annotations

import types

import pytest

from mcp_server.general_tools_impl import status_and_time


class _FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += float(seconds)


class _FakeSpaceCenterLegacy:
    def __init__(self, *, lag_reads: int = 2, max_rails_factor: int = 7) -> None:
        self.maximum_rails_warp_factor = max_rails_factor
        self._lag_reads = lag_reads

        self._rails_warp_factor = 0
        self._physics_warp_factor = 0
        self._warp_rate = 1.0
        self._pending_warp_rate: float | None = None
        self._pending_reads_remaining = 0

    @property
    def rails_warp_factor(self) -> int:
        return int(self._rails_warp_factor)

    @rails_warp_factor.setter
    def rails_warp_factor(self, value: int) -> None:
        self._rails_warp_factor = int(value)
        rates = [1.0, 5.0, 10.0, 50.0, 100.0, 1000.0, 10000.0, 100000.0]
        self._pending_warp_rate = rates[max(0, min(int(value), len(rates) - 1))]
        self._pending_reads_remaining = int(self._lag_reads)

    @property
    def physics_warp_factor(self) -> int:
        return int(self._physics_warp_factor)

    @physics_warp_factor.setter
    def physics_warp_factor(self, value: int) -> None:
        self._physics_warp_factor = int(value)
        rates = [1.0, 2.0, 3.0, 4.0]
        self._pending_warp_rate = rates[max(0, min(int(value), len(rates) - 1))]
        self._pending_reads_remaining = int(self._lag_reads)

    @property
    def warp_rate(self) -> float:
        # Simulate a short delay between writing the factor and warp_rate updating.
        if self._pending_warp_rate is not None and self._pending_reads_remaining > 0:
            self._pending_reads_remaining -= 1
            return float(self._warp_rate)
        if self._pending_warp_rate is not None:
            self._warp_rate = float(self._pending_warp_rate)
            self._pending_warp_rate = None
        return float(self._warp_rate)


class _FakeConn:
    def __init__(self, sc) -> None:
        self.space_center = sc

    def close(self) -> None:  # pragma: no cover
        return None


def test_set_timewarp_rate_legacy_waits_for_rate_to_settle(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(status_and_time.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(status_and_time.time, "sleep", clock.sleep)

    sc = _FakeSpaceCenterLegacy(lag_reads=3)
    monkeypatch.setattr(status_and_time, "open_connection", lambda *args, **kwargs: _FakeConn(sc))

    msg = status_and_time.set_timewarp_rate(rate=50.0, mode="rails")
    assert "Applied factor=3" in msg
    assert "Observed factor=3, warp_rate=50" in msg
    assert "Warp state may still be updating" not in msg


def test_set_timewarp_rate_legacy_warns_if_rate_never_matches(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(status_and_time.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(status_and_time.time, "sleep", clock.sleep)

    sc = _FakeSpaceCenterLegacy(lag_reads=0)
    # Make warp_rate refuse to update (e.g., rails warp blocked)
    sc.rails_warp_factor = 3
    sc._pending_warp_rate = None
    sc._warp_rate = 1.0
    monkeypatch.setattr(_FakeSpaceCenterLegacy, "warp_rate", property(lambda self: 1.0))

    monkeypatch.setattr(status_and_time, "open_connection", lambda *args, **kwargs: _FakeConn(sc))
    msg = status_and_time.set_timewarp_rate(rate=50.0, mode="rails")
    assert "Applied factor=3" in msg
    assert "Observed factor=3, warp_rate=1" in msg
    assert "Warp state may still be updating" in msg


def test_set_timewarp_rate_uses_warp_object_when_available(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(status_and_time.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(status_and_time.time, "sleep", clock.sleep)

    warp = types.SimpleNamespace(rate=1.0, mode=types.SimpleNamespace(name="rails"))
    sc = types.SimpleNamespace(warp=warp)
    monkeypatch.setattr(status_and_time, "open_connection", lambda *args, **kwargs: _FakeConn(sc))

    msg = status_and_time.set_timewarp_rate(rate=1.0, mode=None)
    assert "Timewarp set (warp object)." in msg
    assert "Actual" in msg

