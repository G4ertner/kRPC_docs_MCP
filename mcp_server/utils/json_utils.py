from __future__ import annotations

import json
import math
from typing import Any


def sanitize(value: Any) -> Any:
    """
    Prepare data for strict JSON encoding.

    - Converts non-finite floats (NaN/±Inf) to None so the result can be encoded
      with allow_nan=False (RFC 8259 compliant JSON).
    - Recurses through common containers.
    """
    if value is None:
        return None

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [sanitize(v) for v in value]

    return value


def dumps(payload: Any, **kwargs: Any) -> str:
    """
    json.dumps wrapper that always produces RFC 8259-compliant JSON.

    Any non-finite floats in the payload are encoded as null.
    """
    kwargs.pop("allow_nan", None)
    return json.dumps(sanitize(payload), allow_nan=False, **kwargs)

