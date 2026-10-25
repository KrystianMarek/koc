#!/usr/bin/env python3
"""
Standalone Kinect tilt + depth diagnostic - run ON the robot with the K.O.C
server STOPPED (this process claims the camera exclusively).

Sequence: level snapshot (2 s) -> tilt -10 deg (pivot toward the ground,
3 s) -> down snapshot -> tilt back to level -> level snapshot. Compares the
center-region raw, the nearest-blob raw and the valid-pixel fraction per
pose, against the sonar ground truth (~75 cm => raw ~594). Also prints the
accelerometer readout at each pose (cracks the mks axis-mapping bug).

Safety: single gentle tilt moves only (the motor is for repositioning, not
continuous motion); the runloop body raises Kill when done.

Usage (on the robot, server stopped):
    ~/.virtualenvs/pi_robot3/bin/python kinect_tilt_depth_probe.py
"""
import time

import numpy as np
import freenect

VALID_MIN, VALID_MAX = 300, 1008
frames = []                      # (label, depth copy)
label = ["level_before"]
phase = [0]
t_mark = [time.time()]
accels = []                      # (label, tilt_degs, x, y, z)


def depth_cb(dev, data, ts):
    frames.append((label[0], data.copy()))


def read_tilt(dev, tag):
    freenect.update_tilt_state(dev)
    st = freenect.get_tilt_state(dev)
    deg = freenect.get_tilt_degs(st)
    ax, ay, az = freenect.get_mks_accel(st)
    accels.append((label[0], deg, ax, ay, az))
    print("{:>14}: tilt {:+.2f} deg | accel mks x={:.0f} y={:.0f} z={:.0f}"
          .format(tag, deg, ax, ay, az))


def body(dev, ctx):
    now = time.time()
    if phase[0] == 0 and now - t_mark[0] > 2.0:
        read_tilt(dev, "level_before")
        label[0] = "down"
        freenect.set_tilt_degs(dev, -10.0)
        t_mark[0] = now
        phase[0] = 1
    elif phase[0] == 1 and now - t_mark[0] > 3.0:
        read_tilt(dev, "down")
        label[0] = "level_after"
        freenect.set_tilt_degs(dev, 0.0)
        t_mark[0] = now
        phase[0] = 2
    elif phase[0] == 2 and now - t_mark[0] > 2.0:
        read_tilt(dev, "level_after")
        phase[0] = 3
        raise freenect.Kill


def stats(depth):
    valid = (depth >= VALID_MIN) & (depth <= VALID_MAX)
    frac = float(valid.mean())
    m = depth[200:280, 280:360]
    m = m[(m >= VALID_MIN) & (m <= VALID_MAX)]
    ctr = float(np.median(m)) if m.size else None
    vals = depth[valid]
    if vals.size == 0:
        return frac, ctr, None, 0
    thresh = np.percentile(vals, 10)
    mask = valid & (depth <= thresh + 5)
    ys, xs = np.nonzero(mask)
    braw = float(np.median(depth[mask])) if len(xs) else None
    bx = float(xs.mean()) if len(xs) else None
    return frac, ctr, braw, int(len(xs))


def main():
    print("starting runloop (level 2 s -> down 3 s -> level 2 s)...")
    freenect.runloop(depth=depth_cb, body=body)

    print("\n=== DEPTH COMPARISON (sonar ground truth: 75 cm = raw ~594) ===")
    for lbl in ("level_before", "down", "level_after"):
        sel = [f for (l, f) in frames if l == lbl]
        if not sel:
            print("{:>14}: no frames".format(lbl))
            continue
        arr = np.mean(sel, axis=0)
        frac, ctr, braw, n = stats(arr.astype(np.uint16))
        bx_line = "-"
        print("{:>14}: frames={} valid={:.2f} ctr_raw={} blob_raw={} "
              "blob_n={}".format(
                  lbl, len(sel), frac,
                  "{:.0f}".format(ctr) if ctr else "-",
                  "{:.0f}".format(braw) if braw else "-", n))


if __name__ == "__main__":
    main()
