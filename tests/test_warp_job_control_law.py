from __future__ import annotations

import pytest

from mcp_server.executor_impl import job_tools


def test_compute_desired_rate_uses_wall_budget_not_static_target():
    # If we're behind schedule, desired rate should increase rather than collapsing to ~1x.
    desired = job_tools._compute_desired_rate(
        remaining_game_s=16.5,
        settle_at_s=2.0,
        target_real_time_s=10.0,
        elapsed_wall_s=15.0,
    )
    assert desired > 5.0


def test_compute_desired_rate_settles_to_realtime_near_target():
    desired = job_tools._compute_desired_rate(
        remaining_game_s=1.9,
        settle_at_s=2.0,
        target_real_time_s=10.0,
        elapsed_wall_s=0.0,
    )
    assert desired == pytest.approx(1.0)


def test_compute_sleep_shrinks_near_target_at_high_rates():
    # Close to target, high rates should force small polling intervals to prevent overshoot.
    sleep_s = job_tools._compute_sleep_s(
        remaining_game_s=10.0,
        settle_at_s=2.0,
        expected_rate=50.0,
    )
    assert sleep_s <= 0.05


def test_compute_sleep_uses_base_sleep_far_from_target():
    sleep_s = job_tools._compute_sleep_s(
        remaining_game_s=500.0,
        settle_at_s=2.0,
        expected_rate=100.0,
    )
    assert sleep_s == pytest.approx(0.25)

