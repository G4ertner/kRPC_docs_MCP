# --- const: a.sample (CONST_BLOCK)
G0 = 9.80665
EARTH_RADIUS_M = 6371000

# --- class: a.sample (NavHelper)
class NavHelper(BaseNav):
    """Navigation helpers."""

    # Leading comment for method
    def circ_dv(self, v_now: float, v_circ: float) -> float:
        return v_circ - v_now

