from __future__ import annotations

import pytest

from mcp_server.general_tools_impl import status_and_time


class _FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += float(seconds)


class _FakeSpaceCenterLegacyLag:
    def __init__(self, *, factor_lag_reads: int = 1) -> None:
        self.ut = 123.0
        self._reads_remaining = int(factor_lag_reads)

    @property
    def warp_rate(self) -> float:
        # Warp is already at 5x.
        return 5.0

    @property
    def rails_warp_factor(self) -> int:
        # Simulate kRPC/KSP lag: factor reads as 0 briefly even though warp_rate is > 1.
        if self._reads_remaining > 0:
            self._reads_remaining -= 1
            return 0
        return 1


class _FakeConn:
    def __init__(self, sc) -> None:
        self.space_center = sc

    def close(self) -> None:  # pragma: no cover
        return None


def test_warp_monitor_settles_legacy_factor_rate_race(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(status_and_time.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(status_and_time.time, "sleep", clock.sleep)

    sc = _FakeSpaceCenterLegacyLag(factor_lag_reads=2)
    monkeypatch.setattr(status_and_time, "open_connection", lambda *args, **kwargs: _FakeConn(sc))

    snap = status_and_time._warp_monitor(timeout=0.01)
    assert snap["warp_rate"] == pytest.approx(5.0)
    assert snap["rails_warp_factor"] == 1
    assert snap["telemetry_stable"] is True
    assert snap["warp_rate_effective"] == pytest.approx(5.0)
    assert snap["warp_mode_effective"] == "rails"
    assert snap["warp_factor_effective"] == 1


def test_warp_monitor_reports_realtime_factor_zero_with_preferred_mode(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(status_and_time.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(status_and_time.time, "sleep", clock.sleep)

    sc = _FakeSpaceCenterLegacyLag(factor_lag_reads=0)
    # Force realtime and no factor info.
    monkeypatch.setattr(_FakeSpaceCenterLegacyLag, "warp_rate", property(lambda self: 1.0))
    monkeypatch.setattr(_FakeSpaceCenterLegacyLag, "rails_warp_factor", property(lambda self: 0))

    monkeypatch.setattr(status_and_time, "open_connection", lambda *args, **kwargs: _FakeConn(sc))

    snap = status_and_time._warp_monitor(timeout=0.01, preferred_mode="rails")
    assert snap["warp_rate_effective"] == pytest.approx(1.0)
    assert snap["warp_factor_effective"] == 0
    assert snap["warp_mode_effective"] == "rails"
