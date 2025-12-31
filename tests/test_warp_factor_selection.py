from __future__ import annotations

from mcp_server.executor_impl import job_tools


def test_choose_factor_avoids_early_drop_to_realtime_for_rails():
    # Stock-ish rails rates used by the server when kRPC doesn't provide them.
    rates = [1.0, 5.0, 10.0, 50.0, 100.0, 1000.0, 10000.0, 100000.0]

    # W001 repro shape: desired_rate between 1 and 5 must pick 5x rather than 1x.
    assert job_tools._choose_factor(target_rate=2.0, rates=rates) == 1
    assert job_tools._choose_factor(target_rate=4.6, rates=rates) == 1

    # Near-1x should still pick realtime.
    assert job_tools._choose_factor(target_rate=1.2, rates=rates) == 0


def test_choose_factor_picks_reasonable_nearest_factor():
    rates = [1.0, 5.0, 10.0, 50.0]

    # If ideal is close to 10x, choose 10x.
    assert job_tools._choose_factor(target_rate=9.0, rates=rates) == 2

    # If ideal is close to 50x, choose 50x.
    assert job_tools._choose_factor(target_rate=40.0, rates=rates) == 3


def test_nearest_factor_index_matches_expected_rates():
    rates = [1.0, 5.0, 10.0, 50.0]
    assert job_tools._nearest_factor_index(rate=1.0, rates=rates) == 0
    assert job_tools._nearest_factor_index(rate=4.9, rates=rates) == 1
    assert job_tools._nearest_factor_index(rate=5.0, rates=rates) == 1
    assert job_tools._nearest_factor_index(rate=9.0, rates=rates) == 2
    assert job_tools._nearest_factor_index(rate=40.0, rates=rates) == 3
