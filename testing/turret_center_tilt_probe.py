#!/usr/bin/env python3
"""
Turret centering + Kinect tilt diagnostic - run ON the robot (server up).

Phase A - centering: small swings toward the predicted landmark while
tracking the nearest-depth blob; stops when the blob centers. If the turret
is already centered per the blob, phase A is skipped. Known effect (2026-10-25):
the blob-centered encoder depends on the approach direction (gear backlash,
measured ~252 ticks) - the homing sweep (left approach) centered at +527,
the right-approach run at +275.

Phase B - tilt: pivot the Kinect down 10 deg (internal motor, gentle single
move) and compare depth readings pre/down/level, plus the accelerometer
readout at each position (cracks the mks axis-mapping bug).

Safety: deadman-streamed small swings, hard encoder floor, kill anytime.
Usage (on the robot):
    cd ~/rpi_lego_robot && ~/.virtualenvs/pi_robot3/bin/python \\
        testing/turret_center_tilt_probe.py [predicted_center_encoder]
"""
import os
import sys
import time
from collections import deque

import numpy as np
import zmq

import freenect as fn  # robot venv; used for the tilt motor interface

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.common.serialization import compress, decompress
from app.networking import (
    HeartbeatRequest, KinectPacket, TelemetryPacket, TurretLeft, TurretReset,
    TurretRight)

PREDICTED_CENTER = int(sys.argv[1]) if len(sys.argv) > 1 else 401
SWING_S = 0.6
SPEED = 25
STREAM_PERIOD = 0.1
MAX_SWINGS = 16
HARD_FLOOR = 100          # never below this encoder (cable safety)
SETTLE_S = 0.4
TILT_DEG = -10.0          # pivot toward the ground
TILT_SETTLE_S = 3.0

push = None


def handshake(ctx):
    req = ctx.socket(zmq.REQ)
    req.setsockopt(zmq.LINGER, 0)
    req.setsockopt(zmq.RCVTIMEO, 8000)
    req.connect("tcp://127.0.0.1:5556")
    req.send(compress(HeartbeatRequest(
        sequence=0, running=True, network={}, sleep=1.0)))
    try:
        decompress(req.recv())
        print("handshake ok")
    except zmq.Again:
        sys.exit("no handshake response - is the server running?")
    req.close()


def pump(sub, seconds, log, frames, stream=None):
    end = time.time() + seconds
    next_send = 0.0
    while time.time() < end:
        now = time.time()
        if stream is not None and now >= next_send:
            push.send(compress(stream))
            next_send = now + STREAM_PERIOD
        try:
            packet = decompress(sub.recv(zmq.NOBLOCK))
        except zmq.Again:
            time.sleep(0.005)
            continue
        if isinstance(packet, TelemetryPacket):
            log.append((time.time(), packet.turret_motor.angle,
                        packet.color_sensor.raw,
                        packet.ultrasound_sensor.raw))
        elif isinstance(packet, KinectPacket):
            frames.append((time.time(), np.asarray(packet.get_depth())))


def latest_depth(frames, after_t):
    for t, f in reversed(frames):
        if t >= after_t:
            return f
    return None


def depth_stats(depth):
    """(center_region_raw, blob_x, blob_raw, valid_frac) or None."""
    valid = (depth >= 300) & (depth <= 1008)
    frac = float(valid.mean())
    if not valid.any():
        return None
    m = depth[200:280, 280:360]
    m = m[(m >= 300) & (m <= 1008)]
    ctr = float(np.median(m)) if m.size else None
    vals = depth[valid]
    thresh = np.percentile(vals, 10)
    mask = valid & (depth <= thresh + 5)
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return ctr, None, None, frac
    return ctr, float(xs.mean()), float(np.median(depth[mask])), frac


def enc_around(log, t0, t1):
    arr = np.array([(l[0], l[1]) for l in log], dtype=float)
    return (float(arr[np.argmin(np.abs(arr[:, 0] - t0)), 1]),
            float(arr[np.argmin(np.abs(arr[:, 0] - t1)), 1]))


def main():
    global push
    os.makedirs("/tmp/koc_calib", exist_ok=True)
    ctx = zmq.Context()
    handshake(ctx)

    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://127.0.0.1:5559")
    sub.setsockopt(zmq.SUBSCRIBE, b"")
    sub.setsockopt(zmq.RCVTIMEO, 1000)

    push = ctx.socket(zmq.PUSH)
    push.connect("tcp://127.0.0.1:5560")

    frames = deque(maxlen=30)
    log = []

    print("baseline 3 s...")
    pump(sub, 3.0, log, frames)
    e_start = log[-1][1]
    col = np.array([l[2] for l in log], dtype=float)
    son = np.array([l[3] for l in log], dtype=float)
    print("start: encoder {} | color med {:.0f} | sonar med {:.0f} | "
          "predicted center {}".format(
              int(e_start), np.median(col), np.median(son), PREDICTED_CENTER))

    depth0 = latest_depth(frames, time.time() - 3.0)
    st0 = depth_stats(depth0) if depth0 is not None else None
    already = st0 and st0[1] is not None and abs(st0[1] - 320.0) <= 30
    print("blob at rest: {} (centered={})".format(
        "x={:.0f} raw={:.0f}".format(st0[1], st0[2]) if st0 and st0[1]
        else "none", bool(already)))

    # --- phase A: center (skip if already centered) ---
    if already:
        print("\nphase A skipped: already centered at encoder {}".format(
            int(e_start)))
    else:
        direction = TurretRight(SPEED) if e_start > PREDICTED_CENTER \
            else TurretLeft(SPEED)
        dname = "RIGHT" if e_start > PREDICTED_CENTER else "LEFT"
        print("\nphase A: {} swings until the blob centers "
              "(predicted enc {})".format(dname, PREDICTED_CENTER))
        streak = 0
        for i in range(MAX_SWINGS):
            t0 = time.time()
            pump(sub, SWING_S, log, frames, stream=direction)
            push.send(compress(TurretReset()))
            t1 = time.time()
            pump(sub, SETTLE_S, log, frames)
            e0, e1 = enc_around(log, t0 - 0.2, t1 + 0.2)

            win = [l for l in log if t0 <= l[0] <= t1]
            col = np.array([l[2] for l in win], dtype=float)
            son = np.array([l[3] for l in win], dtype=float)

            depth = latest_depth(frames, t0)
            st = depth_stats(depth) if depth is not None else None
            line = "s{:02d} enc {:>7.0f} ({:+4.0f}) color {:>4.0f}..{:.0f} " \
                   "sonar {:>3.0f}".format(
                       i + 1, e1, e1 - e0, col.min(), col.max(),
                       son.min() if son.size else -1,
                       son.max() if son.size else -1)
            if st:
                ctr, bx, braw, frac = st
                line += " | ctr_raw {} | blob {} raw {} frac {:.2f}".format(
                    "{:.0f}".format(ctr) if ctr else "-",
                    "{:.0f}".format(bx) if bx else "-",
                    "{:.0f}".format(braw) if braw else "-", frac)
            print(line)

            if st and st[1] is not None and abs(st[1] - 320.0) <= 30:
                streak += 1
                if streak >= 2:
                    print("\n>>> blob centered: encoder {} | color {:.0f} | "
                          "sonar {:.0f}".format(
                              int(e1), float(col.mean()),
                              float(np.median(son)) if son.size else -1))
                    break
            else:
                streak = 0
            if e1 <= HARD_FLOOR:
                print("\nhard floor reached (enc {}) - stopping".format(
                    int(e1)))
                break

    # --- phase B: tilt diagnostic ---
    print("\nphase B: Kinect tilt (level -> {:+.0f} -> level)".format(TILT_DEG))
    tctx = fn.init()
    tdev = fn.open_device(tctx, 0)  # camera claim may fail-busy; motor works
    if tdev is None:
        print("open_device failed (camera busy?) - tilt diagnostic skipped; "
              "turret left at encoder {}".format(int(log[-1][1])))
        sub.close()
        push.close()
        ctx.term()
        return

    def tilt_snapshot(label):
        fn.update_tilt_state(tdev)
        st = fn.get_tilt_state(tdev)
        deg = fn.get_tilt_degs(st)
        ax, ay, az = fn.get_mks_accel(st)
        mark = time.time()
        pump(sub, 1.2, log, frames)
        depth = latest_depth(frames, mark)
        st2 = depth_stats(depth) if depth is not None else None
        ctr = st2[0] if st2 else None
        braw = st2[2] if st2 else None
        frac = st2[3] if st2 else -1
        print("{}: tilt {:+.2f} deg | accel mks x={:.0f} y={:.0f} z={:.0f} | "
              "ctr_raw {} | blob_raw {} | valid {:.2f}".format(
                  label, deg, ax, ay, az,
                  "{:.0f}".format(ctr) if ctr else "-",
                  "{:.0f}".format(braw) if braw else "-", frac))

    tilt_snapshot("level(before)")
    fn.set_tilt_degs(tdev, TILT_DEG)
    time.sleep(TILT_SETTLE_S)
    tilt_snapshot("down")
    fn.set_tilt_degs(tdev, 0.0)
    time.sleep(TILT_SETTLE_S)
    tilt_snapshot("level(after)")
    fn.close_device(tdev)
    fn.shutdown(tctx)

    print("\nsonar reference: ~75 cm; kinect raw for a given distance:")
    for d in (0.70, 0.75, 0.80):
        raw = 2842.5 * (np.arctan(d / 0.1236) - 1.1863)
        print("  kinect raw for {:.2f} m = {:.0f}".format(d, raw))

    csv_path = "/tmp/koc_calib/center_tilt.csv"
    with open(csv_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "encoder", "color", "sonar"])
        for row in log:
            wr.writerow([round(row[0], 3), int(row[1]), int(row[2]),
                         int(row[3])])
    print("CSV saved:", csv_path)

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
