#!/usr/bin/env python3
"""
Kinect tilt (pitch) motor probe - run ON the robot.

The Kinect 360 has a motorized tilt in its base (USB interface 'NUI Motor',
02b0) with roughly +/-27 degrees of travel and an accelerometer for feedback.
libfreenect exposes it via set_tilt_degs / get_tilt_state; K.O.C v1 stubbed
it out (kinect_process.py returns 0) - this probe verifies the hardware works.

NOTE (libfreenect guidance): do not spam set_tilt_degs - the tilt motor is a
small DC gearmotor meant for occasional repositioning, not continuous motion.
This probe moves gently with settle pauses and always returns to level.

Usage (on the robot):
    ~/.virtualenvs/pi_robot3/bin/python kinect_tilt_probe.py

The motor interface can be claimed while the camera interface is held by
another process (e.g. a running K.O.C server) - they are independent.
"""
import time

import freenect

POSITIONS = [0.0, 12.0, -12.0, 0.0]
SETTLE_SECONDS = 3.0


def read_tilt(dev):
    """Refresh tilt state and return the accelerometer-derived angle."""
    freenect.update_tilt_state(dev)
    state = freenect.get_tilt_state(dev)
    return freenect.get_tilt_degs(state)


def main():
    ctx = freenect.init()
    dev = freenect.open_device(ctx, 0)
    print("initial tilt: {:+.2f} deg".format(read_tilt(dev)))
    for pos in POSITIONS:
        freenect.set_tilt_degs(dev, pos)
        time.sleep(SETTLE_SECONDS)
        actual = read_tilt(dev)
        print("commanded {:+6.1f} -> actual {:+.2f} deg".format(pos, actual))
    # Accelerometer sanity at the final (level) position.
    freenect.update_tilt_state(dev)
    state = freenect.get_tilt_state(dev)
    ax, ay, az = freenect.get_mks_accel(state)
    print("accel at level (milli-g): x={:.0f} y={:.0f} z={:.0f}".format(ax, ay, az))
    freenect.close_device(dev)
    freenect.shutdown(ctx)


if __name__ == "__main__":
    main()
