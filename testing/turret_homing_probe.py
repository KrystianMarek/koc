#!/usr/bin/env python3
"""
Turret homing probe - find the encoder position that centers the Kinect on
an obstacle the ultrasonic sensor ranges. Run ON the robot (server up).

Setup (user-provided):
- Obstacle directly in front of the base chassis, ~70 cm from the ultrasonic
  sensor (BrickPi PORT_4, chassis-fixed, facing forward).
- Turret currently ~30 deg RIGHT of center; turning LEFT centers the Kinect
  on the obstacle.
- Color sensor (PORT_1) rides on the turret - its reading at center is the
  landmark for the homing system.

Method: small bounded swings left; per swing log encoder + color + sonar from
telemetry and grab the latest Kinect depth frame. The obstacle is the nearest
valid-depth cluster (lowest raw, per raw_depth_to_meters: raw ~594 = 0.70 m);
when its centroid crosses the image center (x~320) or the central-region raw
passes ~594, the camera is centered on the obstacle. Probe stops there
(or at the tick budget) and reports the encoder + color landmark.

Safety: deadman-streamed small swings, hard tick budget (cables inside the
turret), kill anytime - motors stop within ~0.3 s.

Usage (on the robot):
    cd ~/rpi_lego_robot && ~/.virtualenvs/pi_robot3/bin/python \\
        testing/turret_homing_probe.py [max_swing_count] [speed]
"""
import csv
import os
import sys
import time
from collections import deque

import numpy as np
import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.common.serialization import compress, decompress
from app.networking import (
    HeartbeatRequest, KinectPacket, TelemetryPacket, TurretLeft, TurretReset)

MAX_SWINGS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 25
SWING_S = 1.0
SETTLE_S = 0.4
STREAM_PERIOD = 0.1
OUT_DIR = "/tmp/koc_calib"

# raw_depth_to_meters constants (app/client/frame_processor.py)
TAN_SCALE, TAN_OFFSET, MULT = 2842.5, 1.1863, 0.1236
VALID_MIN, VALID_MAX = 300, 1008          # 0.42 m .. 4.0 m
OBSTACLE_RAW = 594                        # ~0.70 m (the sonar's distance)
CX_IMAGE = 320.0

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


def blob(depth):
    """Nearest-valid cluster: (centroid_x, raw_median, npix) or None."""
    valid = (depth >= VALID_MIN) & (depth <= VALID_MAX)
    if not valid.any():
        return None
    vals = depth[valid]
    thresh = np.percentile(vals, 10)
    mask = valid & (depth <= thresh + 5)
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return None
    return float(xs.mean()), float(np.median(depth[mask])), int(len(xs))


def center_raw(depth):
    m = depth[200:280, 280:360]
    m = m[(m >= VALID_MIN) & (m <= VALID_MAX)]
    return float(np.median(m)) if m.size else None


def enc_around(log, t0, t1):
    arr = np.array([(l[0], l[1]) for l in log], dtype=float)
    return (float(arr[np.argmin(np.abs(arr[:, 0] - t0)), 1]),
            float(arr[np.argmin(np.abs(arr[:, 0] - t1)), 1]))


def main():
    global push
    os.makedirs(OUT_DIR, exist_ok=True)
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

    print("baseline 3 s (motors idle)...")
    pump(sub, 3.0, log, frames)
    arr = np.array([(l[0], l[2], l[3]) for l in log if l[0] < time.time()],
                   dtype=float)
    colors = arr[:, 1]
    sonars = arr[:, 2]
    print("baseline: color med={:.0f} ({}..{}) sonar med={:.0f} ({}..{}) "
          "encoder={}".format(
              np.median(colors), int(colors.min()), int(colors.max()),
              np.median(sonars), int(sonars.min()), int(sonars.max()),
              int(log[-1][1])))

    e_start = log[-1][1]
    results = []
    homed = None
    centered_streak = 0

    print("\nsweep: up to {} swings of {} s @ speed {} "
          "(~1 deg each at 125 ticks/deg)".format(MAX_SWINGS, SWING_S, SPEED))
    print("stop when the obstacle blob centers (x~320) or the tick budget "
          "laps; expect sonar ~70 throughout")
    for i in range(MAX_SWINGS):
        t0 = time.time()
        pump(sub, SWING_S, log, frames, stream=TurretLeft(SPEED))
        push.send(compress(TurretReset()))
        t1 = time.time()
        pump(sub, SETTLE_S, log, frames)
        e0, e1 = enc_around(log, t0 - 0.2, t1 + 0.2)

        win = [l for l in log if t0 <= l[0] <= t1]
        col = np.array([l[2] for l in win], dtype=float)
        son = np.array([l[3] for l in win], dtype=float)

        depth = None
        for t, f in reversed(frames):
            if t >= t0:
                depth = f
                break
        b = blob(depth) if depth is not None else None
        cr = center_raw(depth) if depth is not None else None

        line = "s{:02d} enc {:>7.0f} ({:+4.0f}) color {:>4.0f}..{:.0f} " \
               "sonar {:>3.0f}..{:.0f}".format(
                   i + 1, e1, e1 - e0, col.min(), col.max(),
                   son.min(), son.max())
        if b:
            line += " | blob x={:5.0f} raw={:.0f} n={}".format(b[0], b[1], b[2])
        else:
            line += " | blob none"
        if cr is not None:
            line += " | ctr_raw={:.0f}".format(cr)
        print(line)

        results.append((i + 1, e1, float(col.mean()), float(np.median(son)),
                        b[0] if b else None, b[1] if b else None,
                        cr if cr is not None else -1))

        # centered? blob centroid near image center twice in a row
        if b and abs(b[0] - CX_IMAGE) <= 30:
            centered_streak += 1
            if centered_streak >= 2:
                homed = e1
                print("\n>>> obstacle centered: encoder {} (blob x={:.0f}, "
                      "color {:.0f}, sonar {:.0f})".format(
                          int(e1), b[0], float(col.mean()),
                          float(np.median(son))))
                break
        else:
            centered_streak = 0
        if abs(e1 - e_start) > 4200:
            print("\ntick budget reached without centering - stopping "
                  "(cable safety)")
            break

    # --- report ---
    print("\n=== HOMING REPORT ===")
    print("encoder start {} -> end {} (net {:+.0f} ticks = {:+.1f} deg "
          "at 125 ticks/deg)".format(
              int(e_start), int(log[-1][1]),
              log[-1][1] - e_start, (log[-1][1] - e_start) / 125.0))
    if homed is not None:
        i = next(r for r in results if r[1] == homed)
        print("CENTER: encoder {} | color {:.0f} | sonar {:.0f} | "
              "blob raw {}".format(int(homed), i[2], i[3], int(i[5])))
    else:
        # interpolate the encoder where the blob centroid crossed x=320
        pts = [(r[1], r[4]) for r in results if r[4] is not None]
        if len(pts) >= 2:
            xs = np.array([p[1] for p in pts])
            es = np.array([p[0] for p in pts])
            order = np.argsort(xs)
            est = np.interp(CX_IMAGE, xs[order], es[order])
            print("blob crossed image center between swings - interpolated "
                  "center encoder: {:.0f}".format(est))
        else:
            print("obstacle blob never seen - check kinect/geometry")
    son_all = np.array([r[3] for r in results])
    print("sonar across sweep: median {:.0f}, range {}..{} "
          "(expect ~70; changes = occlusion landmark)".format(
              float(np.median(son_all)), int(son_all.min()),
              int(son_all.max())))

    csv_path = os.path.join(OUT_DIR, "turret_homing.csv")
    with open(csv_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["swing", "encoder", "color_mean", "sonar_med",
                     "blob_x", "blob_raw", "center_raw"])
        for r in results:
            wr.writerow([int(r[0]), int(r[1]), round(r[2], 1), round(r[3], 0),
                         round(r[4], 1) if r[4] else "", round(r[5], 0),
                         round(r[6], 0)])
    full_path = os.path.join(OUT_DIR, "turret_homing_full.csv")
    with open(full_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "encoder", "color", "sonar"])
        for row in log:
            wr.writerow([round(row[0], 3), int(row[1]), int(row[2]),
                         int(row[3])])
    print("CSV saved:", csv_path, "+", full_path)

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
