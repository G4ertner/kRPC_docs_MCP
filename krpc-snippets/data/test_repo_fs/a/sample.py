"""Sample module for AST parse tests.

Includes:
- Module docstring
- Const block
- Decorated function with annotation and docstring
- Class with base, decorator, and methods
"""

# ---- Constants ----
G0 = 9.80665
EARTH_RADIUS_M = 6371000


import math
from typing import Optional


# Leading comment for function
@staticmethod
def vis_viva_speed(mu: float, r: float, a: float) -> float:
    """Compute orbital speed via vis-viva equation."""
    return math.sqrt(mu * (2.0 / r - 1.0 / a))


@dataclass
class NavHelper(BaseNav):
    """Navigation helpers."""

    # Leading comment for method
    def circ_dv(self, v_now: float, v_circ: float) -> float:
        return v_circ - v_now

