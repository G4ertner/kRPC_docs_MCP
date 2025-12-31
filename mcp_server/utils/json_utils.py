from __future__ import annotations

import json
import math
import os
from typing import Any


_ROUNDING_ENABLED = os.getenv("GEEPT_JSON_ROUNDING", "").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

_DEFAULT_FLOAT_DECIMALS = 4
_EXACT_KEY_DECIMALS = {
    "latitude_deg": 4,
    "longitude_deg": 4,
    "eccentricity": 4,
    "mach": 2,
    "twr_surface": 2,
    "g_force": 2,
    "throttle": 2,
    "sun_exposure_avg": 2,
    "est_output": 2,
    "amount": 2,
    "max": 2,
    "current": 2,
    "ut": 1,
    "timewarp_rate": 2,
}
_SUFFIX_KEY_DECIMALS = [
    ("_m_s2", 2),
    ("_kg_m3", 4),
    ("_m_s", 1),
    ("_deg", 1),
    ("_pa", 0),
    ("_kg", 1),
    ("_n", 0),
    ("_k", 1),
    ("_ut", 1),
    ("_s", 1),
    ("_m", 0),
]


def _precision_for_key(key: str | None) -> int:
    if not key:
        return _DEFAULT_FLOAT_DECIMALS
    if key in _EXACT_KEY_DECIMALS:
        return _EXACT_KEY_DECIMALS[key]
    for suffix, digits in _SUFFIX_KEY_DECIMALS:
        if key.endswith(suffix):
            return digits
    return _DEFAULT_FLOAT_DECIMALS


def _round_float(value: float, key: str | None) -> float | None:
    if not math.isfinite(value):
        return None
    if not _ROUNDING_ENABLED:
        return value
    digits = _precision_for_key(key)
    rounded = round(value, digits)
    if rounded == 0.0:
        return 0.0
    return rounded


def sanitize(value: Any, *, key: str | None = None) -> Any:
    """
    Prepare data for strict JSON encoding.

    - Converts non-finite floats (NaN/Inf) to None so the result can be encoded
      with allow_nan=False (RFC 8259 compliant JSON).
    - Rounds finite floats based on their key/unit unless disabled via
      GEEPT_JSON_ROUNDING=0.
    - Recurses through common containers.
    """
    if value is None:
        return None

    if isinstance(value, float):
        return _round_float(value, key)

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for k, v in value.items():
            key_str = str(k) if k is not None else None
            sanitized[k] = sanitize(v, key=key_str)
        return sanitized

    if isinstance(value, (list, tuple, set)):
        return [sanitize(v, key=key) for v in value]

    return value


def dumps(payload: Any, **kwargs: Any) -> str:
    """
    json.dumps wrapper that always produces RFC 8259-compliant JSON.

    Any non-finite floats in the payload are encoded as null, and finite floats
    may be rounded for readability.
    """
    kwargs.pop("allow_nan", None)
    return json.dumps(sanitize(payload), allow_nan=False, **kwargs)
