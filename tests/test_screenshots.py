from __future__ import annotations

import datetime as dt
import re

import mcp_server.general_tools_impl.screenshots as screenshots


def test_allocate_unique_screenshot_path_is_unique_with_same_timestamp(tmp_path):
    screenshots._SCREENSHOT_DIR = tmp_path
    screenshots._SEQ = 0

    fixed_now = dt.datetime(2025, 12, 14, 1, 31, 42, 123_000)
    f1, p1, t1 = screenshots._allocate_unique_screenshot_path(now=fixed_now)
    f2, p2, t2 = screenshots._allocate_unique_screenshot_path(now=fixed_now)

    assert f1 != f2
    assert p1 != p2
    assert t1 == t2
    assert p1.parent == tmp_path
    assert p2.parent == tmp_path
    assert f1.endswith(".png")
    assert f2.endswith(".png")


def test_captured_at_format_is_compact_utc_ms(tmp_path):
    screenshots._SCREENSHOT_DIR = tmp_path
    screenshots._SEQ = 0

    fixed_now = dt.datetime(2025, 12, 14, 1, 31, 42, 999_000)
    _, _, captured_at = screenshots._allocate_unique_screenshot_path(now=fixed_now)

    assert re.fullmatch(r"\d{8}T\d{6}\d{3}Z", captured_at)
