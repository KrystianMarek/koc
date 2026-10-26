#!/usr/bin/env python3
"""
turret_envelope.py - show or re-reference the turret cable envelope.

The v1 server and motord both enforce it from ~/.koc/turret.json (rules in
app/server/turret_guard.py). Re-reference ONLY after the user has confirmed
where the turret faces, and with both daemons stopped; they re-read the file
on start.

    python3 testing/turret_envelope.py show
    python3 testing/turret_envelope.py set-center --encoder N
    python3 testing/turret_envelope.py set-center --encoder N --current-deg X

N is the current turret encoder (from `motord_parity_probe.py motord`, which
works while the turret is locked). X is how far the turret currently faces
LEFT of camera-forward in degrees (negative = right), when it is not at
center; the center is then derived with TICKS_PER_DEG.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.server import turret_guard as g

HALF_RANGE = 21000      # 180 deg at 116.7 ticks/deg, 168 deg at 125
TICKS_PER_DEG = 116.7   # lower measured ratio; see doc/architecture/robot-hardware.md


def describe(state):
    low, high = g.limits(state)
    span = state["half_range"]
    return ("center C={center}, last C={last}, half_range {hr} ticks "
            "({d1:.0f} deg at 116.7 t/deg, {d2:.0f} deg at 125); turret stops at "
            "C<={low} (right) / C>={high} (left)").format(
                center=state["center"], last=state["last"], hr=span,
                d1=span / 116.7, d2=span / 125.0, low=low, high=high)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("show")
    sc = sub.add_parser("set-center")
    sc.add_argument("--encoder", type=int, required=True)
    sc.add_argument("--current-deg", type=float, default=0.0)
    sc.add_argument("--path", default=g.STATE_PATH)
    args = parser.parse_args()
    if args.cmd == "show":
        state = g.load_state()
        print(describe(state) if state else "no valid state at {} - turret LOCKED".format(g.STATE_PATH))
        return
    if args.cmd == "set-center":
        center = int(round(args.encoder - args.current_deg * TICKS_PER_DEG))
        state = {"center": center, "half_range": HALF_RANGE, "last": args.encoder}
        if abs(args.encoder - center) >= HALF_RANGE - g.STOP_MARGIN:
            sys.exit("refused: the current position would be outside the envelope")
        g.save_state(state, args.path)
        print("written {}: {}".format(args.path, describe(state)))
        print("restart the v1 server / motord to apply")
        return
    parser.print_help()


if __name__ == "__main__":
    main()
