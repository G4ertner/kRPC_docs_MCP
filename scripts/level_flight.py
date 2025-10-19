#!/usr/bin/env python3
"""
Level Flight (KSP + kRPC)

Engages the kRPC AutoPilot to hold:
- Pitch = 0° (level to the horizon)
- Roll  = 0° (wings level)
- Heading = current heading at the moment you run it

The script keeps the connection open so the autopilot remains engaged.
Press Ctrl+C to disengage and exit.

Requires:
- Kerbal Space Program running
- kRPC mod installed and its server running
- Python package `krpc` installed (pip install krpc)
"""

import math
import signal
import sys
import time

import krpc


def main() -> None:
    conn = krpc.connect(name="Level Flight (kRPC)")
    sc = conn.space_center
    vessel = sc.active_vessel

    ap = vessel.auto_pilot

    # Use surface reference frame so pitch/heading are relative to horizon/north
    ap.reference_frame = vessel.surface_reference_frame

    # Get the current heading (relative to surface)
    flight = vessel.flight(vessel.surface_reference_frame)
    current_heading = flight.heading

    # Tighter roll matching so wings truly level
    try:
        ap.roll_threshold = 1.0  # degrees
    except Exception:
        pass  # property may not exist on older kRPC versions

    # Configure targets and engage
    ap.target_pitch_and_heading(0.0, current_heading)
    ap.target_roll = 0.0
    ap.engage()

    print(
        f"Autopilot engaged: pitch=0°, roll=0°, heading={current_heading:.1f}°."
    )
    print("Press Ctrl+C to disengage and exit.")

    def shutdown(*_: object) -> None:
        try:
            print("\nDisengaging autopilot...")
            ap.disengage()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep the connection open and provide a lightweight status readout
    last_print = 0.0
    while True:
        now = time.time()
        if now - last_print > 1.5:
            last_print = now
            try:
                # Errors are degrees difference to targets
                err = ap.error
                pe = getattr(ap, "pitch_error", float("nan"))
                he = getattr(ap, "heading_error", float("nan"))
                re = getattr(ap, "roll_error", float("nan"))
                print(
                    f"Errors — total:{err:5.2f}°, pitch:{pe:5.2f}°, heading:{he:6.2f}°, roll:{re:5.2f}°"
                )
            except Exception:
                # Fallback status using current flight attitude
                f = vessel.flight(vessel.surface_reference_frame)
                print(
                    f"Attitude — pitch:{f.pitch:5.1f}°, heading:{f.heading:6.1f}°, roll:{f.roll:5.1f}°"
                )
        time.sleep(0.1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

