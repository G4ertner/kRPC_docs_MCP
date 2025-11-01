"""PID Hover Throttle Controller (kRPC)

This script provides a ready-to-use PID-based throttle controller to hover or
hold altitude using kRPC. It exposes tuneable gains, an integral clamp,
feed-forward estimation of hover throttle, and an optional dynamic pressure
limit (Q) using a PID loop.

Side effects:
- Adjusts `vessel.control.throttle` continuously while running.
- Optionally enables SAS in stability assist mode to help keep attitude steady.

Requirements:
- Python 3.10+
- kRPC Python client installed (install package extras with `-e .[krpc]`)

Usage examples:
  # Hold current altitude with conservative defaults (10 Hz)
  uv run scripts/pid_hover.py --address 192.168.1.50 --hold-here

  # Target a specific altitude (meters above terrain), stronger gains
  uv run scripts/pid_hover.py --address 192.168.1.50 \
    --target-alt 150 --kp 0.03 --ki 0.01 --kd 0.06 --rate 15

  # Use vertical-speed hold (hover: vs=0), disable feed-forward
  uv run scripts/pid_hover.py --address 192.168.1.50 \
    --mode vspeed --target-vspeed 0 --no-feedforward

  # Limit max dynamic pressure with a Q-loop (PID clamps throttle)
  uv run scripts/pid_hover.py --address 192.168.1.50 --hold-here --max-q 20000

Notes:
- A hover controller assumes the craft can maintain near-upright attitude
  (SAS stability assist recommended). This script only manages throttle.
- Gains are craft dependent. Start with small values and rise carefully.
- Always fly in a safe save; stop with Ctrl-C. On exit, throttle is set to 0.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from typing import Optional, Tuple


# --- Constants (adapted from the resolved snippet bundle)
REFRESH_FREQ = 2  # default refresh rate in Hz (overridden by --rate)
TELEM_DELAY = 5   # seconds between telemetry prints
ALL_FUELS = ("LiquidFuel", "SolidFuel")
MAX_PHYSICS_WARP = 3


@dataclass
class PID:
    """Simple PID controller with integral clamp and sample time gating.

    The controller computes: u = Kp*e + Ki*integral(e*dt) + Kd*de/dt

    Integral anti-windup: we clamp the integral term contribution to
    +/- i_limit (in output units). This keeps integral from dominating.
    """

    kp: float
    ki: float
    kd: float
    setpoint: float = 0.0
    sample_time: float = 0.1
    out_limits: Tuple[float, float] = (0.0, 1.0)
    i_limit: float = 0.3  # absolute clamp (applied to the integral term)

    _last_time: Optional[float] = None
    _last_error: float = 0.0
    _integral_state: float = 0.0  # stores the unscaled integral of error

    def reset(self) -> None:
        self._last_time = None
        self._last_error = 0.0
        self._integral_state = 0.0

    def update(self, measurement: float, now: Optional[float] = None) -> float:
        now = time.monotonic() if now is None else now
        error = self.setpoint - measurement

        if self._last_time is None:
            self._last_time = now
            self._last_error = error
            # On first call return a proportional-only response (no dt yet)
            u = self.kp * error
            return _clamp(u, *self.out_limits)

        dt = now - self._last_time
        if dt <= 0.0 or dt < self.sample_time:
            # Not enough time elapsed; return previous proportional estimate
            u = self.kp * error + self.ki * self._integral_term() + self.kd * 0.0
            return _clamp(u, *self.out_limits)

        # Integral update with clamp applied to the TERM contribution
        self._integral_state += error * dt
        i_term = self.ki * self._integral_state
        if i_term > self.i_limit:
            # Back-calculate the underlying integral state
            self._integral_state = self.i_limit / self.ki if self.ki != 0 else 0.0
            i_term = self.i_limit
        elif i_term < -self.i_limit:
            self._integral_state = -self.i_limit / self.ki if self.ki != 0 else 0.0
            i_term = -self.i_limit

        # Derivative on error
        d_err = (error - self._last_error) / dt

        u = self.kp * error + i_term + self.kd * d_err
        u = _clamp(u, *self.out_limits)

        self._last_error = error
        self._last_time = now
        return u

    def _integral_term(self) -> float:
        # current integral term contribution (clamped)
        term = self.ki * self._integral_state
        return max(-self.i_limit, min(self.i_limit, term))


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _estimate_hover_throttle(vessel) -> float:
    """Estimate a hover throttle from T/W (recompute each tick).

    Uses current mass and max_thrust at current conditions.
    Adds a small margin to ensure lift > weight.
    """
    try:
        mass = vessel.mass  # kg
        g = vessel.orbit.body.surface_gravity  # m/s^2
        max_thrust = vessel.max_thrust  # N at full throttle under current Isp
        if max_thrust <= 1e-6:
            return 0.0
        throttle = (mass * g) / max_thrust
        return _clamp(throttle * 1.05, 0.0, 1.0)  # +5% margin
    except Exception:
        return 0.5


def limitq(conn, controller: PID) -> None:  # from resolved snippet
    """Limits vessel's throttle to stay under MAX_Q using PID controller.

    Note: This variant sets throttle directly (side effect), matching the
    snippet intent. In the main loop we instead prefer to compute the Q-limit
    as `controller.update(dynamic_pressure)` and take `min()` with the hover
    throttle to avoid fighting controllers.
    """
    vessel = conn.space_center.active_vessel
    flight = vessel.flight(vessel.orbit.body.non_rotating_reference_frame)
    vessel.control.throttle = controller.update(flight.dynamic_pressure)


def run(args: argparse.Namespace) -> int:
    try:
        import krpc  # type: ignore
    except Exception as exc:  # pragma: no cover - import-time guidance
        print("Error: kRPC Python package not found. Install extras with '-e .[krpc]'.", file=sys.stderr)
        print(f"Detail: {exc}", file=sys.stderr)
        return 2

    # Connect to kRPC
    conn = krpc.connect(
        name="PID Hover Controller",
        address=args.address,
        rpc_port=args.rpc_port,
        stream_port=args.stream_port,
    )
    vessel = conn.space_center.active_vessel

    # Recommended: turn on SAS stability assist to help attitude
    try:
        vessel.control.sas = True
        # Some kRPC versions expose SASMode via the connection namespace
        sas_mode = getattr(conn.space_center, "SASMode", None)
        if sas_mode is not None and hasattr(sas_mode, "stability_assist"):
            vessel.control.sas_mode = sas_mode.stability_assist
    except Exception:
        pass

    # Choose telemetry frames
    f_surface = vessel.flight(vessel.surface_reference_frame)
    f_q = vessel.flight(vessel.orbit.body.non_rotating_reference_frame)

    # Determine setpoint based on mode
    if args.mode == "altitude":
        setpoint = f_surface.surface_altitude if args.hold_here else args.target_alt
        if setpoint is None:
            print("Error: --target-alt is required for altitude mode (or use --hold-here)", file=sys.stderr)
            return 2
        meas_fn = lambda: f_surface.surface_altitude
        tol = args.tol_alt
    else:  # vspeed
        setpoint = args.target_vspeed
        meas_fn = lambda: f_surface.vertical_speed
        tol = args.tol_vspeed

    # Controller output is a delta around a base (feed-forward) throttle
    # Clamp deltas to +/- 0.5 (so base +/- 50%) by default
    pid = PID(
        kp=args.kp,
        ki=args.ki,
        kd=args.kd,
        setpoint=setpoint,
        sample_time=1.0 / float(args.rate),
        out_limits=(-0.5, 0.5),
        i_limit=args.i_limit,
    )

    # Optional dynamic pressure limiter
    q_pid: Optional[PID] = None
    if args.max_q is not None and args.max_q > 0:
        q_pid = PID(
            kp=args.q_kp,
            ki=args.q_ki,
            kd=args.q_kd,
            setpoint=args.max_q,
            sample_time=1.0 / float(args.rate),
            out_limits=(0.0, 1.0),  # direct throttle recommendation
            i_limit=args.q_i_limit,
        )

    last_print = 0.0
    dt = 1.0 / float(args.rate)

    print("Controller armed. Ctrl-C to stop.\n")
    try:
        while True:
            now = time.monotonic()

            base = _estimate_hover_throttle(vessel) if args.feedforward else args.base
            measurement = meas_fn()

            delta = pid.update(measurement, now=now)
            throttle = _clamp(base + delta, args.out_min, args.out_max)

            # Apply Q limit as the min of hover throttle and Q-PID recommendation
            if q_pid is not None:
                q_throttle = q_pid.update(f_q.dynamic_pressure, now=now)
                throttle = min(throttle, q_throttle)

            vessel.control.throttle = throttle

            # Telemetry
            if (now - last_print) >= args.telemetry:
                last_print = now
                if args.mode == "altitude":
                    err = setpoint - measurement
                    print(
                        f"alt={measurement:7.2f}m err={err:+7.2f}m vs={f_surface.vertical_speed:+6.2f}m/s "
                        f"tw={_estimate_hover_throttle(vessel):.3f} thr={throttle:.3f} q={f_q.dynamic_pressure:7.0f}Pa"
                    )
                else:
                    err = setpoint - measurement
                    print(
                        f"vs={measurement:+6.2f}m/s err={err:+6.2f} tw={_estimate_hover_throttle(vessel):.3f} "
                        f"thr={throttle:.3f} alt={f_surface.surface_altitude:7.2f}m q={f_q.dynamic_pressure:7.0f}Pa"
                    )

            # Completion check: within tolerance (alt) or vspeed steady
            if args.duration is not None and args.duration > 0:
                # Time-limited run
                if (now - last_print) >= args.duration:
                    break
            else:
                if abs((setpoint - measurement)) <= tol:
                    # Stay within tol for a short dwell (2 cycles)
                    time.sleep(2 * dt)
                    measurement = meas_fn()
                    if abs((setpoint - measurement)) <= tol:
                        print("Target reached within tolerance; stopping.")
                        break

            time.sleep(dt)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        try:
            vessel.control.throttle = 0.0
        except Exception:
            pass

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PID hover/altitude throttle controller (kRPC)")
    # kRPC connection
    p.add_argument("--address", required=True, help="kRPC server address (game PC IP)")
    p.add_argument("--rpc-port", type=int, default=50000, help="kRPC RPC port (default: 50000)")
    p.add_argument("--stream-port", type=int, default=50001, help="kRPC stream port (default: 50001)")

    # Mode and targets
    p.add_argument("--mode", choices=["altitude", "vspeed"], default="altitude", help="Control mode")
    p.add_argument("--target-alt", type=float, help="Target altitude above terrain (m)")
    p.add_argument("--hold-here", action="store_true", help="Use current altitude as setpoint")
    p.add_argument("--target-vspeed", type=float, default=0.0, help="Target vertical speed (m/s)")

    # Controller gains and limits
    p.add_argument("--kp", type=float, default=0.02, help="Proportional gain")
    p.add_argument("--ki", type=float, default=0.006, help="Integral gain")
    p.add_argument("--kd", type=float, default=0.04, help="Derivative gain")
    p.add_argument("--i-limit", type=float, default=0.3, help="Clamp for integral term contribution (throttle units)")
    p.add_argument("--out-min", type=float, default=0.0, help="Minimum throttle")
    p.add_argument("--out-max", type=float, default=1.0, help="Maximum throttle")

    # Feed-forward/base throttle
    p.add_argument("--feedforward", dest="feedforward", action="store_true", help="Enable hover throttle feed-forward (default)")
    p.add_argument("--no-feedforward", dest="feedforward", action="store_false", help="Disable feed-forward")
    p.set_defaults(feedforward=True)
    p.add_argument("--base", type=float, default=0.5, help="Base throttle if feed-forward disabled")

    # Dynamic pressure limiting (Q-limit)
    p.add_argument("--max-q", type=float, help="Max dynamic pressure (Pa). If set, limits throttle with a Q PID loop.")
    p.add_argument("--q-kp", type=float, default=0.00005, help="Q PID Kp (maps Pa to throttle)")
    p.add_argument("--q-ki", type=float, default=0.0, help="Q PID Ki")
    p.add_argument("--q-kd", type=float, default=0.0, help="Q PID Kd")
    p.add_argument("--q-i-limit", type=float, default=0.2, help="Q PID integral clamp (throttle units)")

    # Timing and telemetry
    p.add_argument("--rate", type=float, default=10.0, help="Control loop rate (Hz)")
    p.add_argument("--telemetry", type=float, default=1.0, help="Seconds between telemetry prints")
    p.add_argument("--duration", type=float, help="Optional max runtime (seconds)")

    # Tolerances for completion
    p.add_argument("--tol-alt", type=float, default=0.5, help="Altitude tolerance to stop (m)")
    p.add_argument("--tol-vspeed", type=float, default=0.1, help="VSpeed tolerance to stop (m/s)")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

