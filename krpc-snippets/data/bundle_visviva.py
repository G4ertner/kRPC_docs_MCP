# --- const: a.sample (CONST_BLOCK)
G0 = 9.80665
EARTH_RADIUS_M = 6371000

# --- function: a.sample (vis_viva_speed)
def vis_viva_speed(mu: float, r: float, a: float) -> float:
    """Compute orbital speed via vis-viva equation."""
    return math.sqrt(mu * (2.0 / r - 1.0 / a))

