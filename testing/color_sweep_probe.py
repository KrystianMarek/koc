#!/usr/bin/env python3
"""
Color sensor landmark sweep - run ON the robot (server must be up).

Turns the turret left 3 s, then right 3 s (small, cable-safe swings) while
logging the color sensor (PORT_1, light-on mode) and turret encoder at full
telemetry rate (~10 Hz). Purpose: the user expects the sensor to see the
BACK LEFT CORNER of the robot body during this sweep; a sustained color
deviation pinned to an encoder value names that landmark (anchor for turret
homing geometry).

Prints the full color trace per phase + deviation events; saves CSV to
/tmp/koc_calib/color_sweep.csv.

Usage (on the robot):
    cd ~/rpi_lego_robot && ~/.virtualenvs/pi_robot3/bin/python \\
        testing/color_sweep_probe.py [swing_seconds] [speed]
"""
import csv
import os
import sys
import time

import numpy as np
import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.common.serialization import compress, decompress
from app.networking import (
    HeartbeatRequest, TelemetryPacket, TurretLeft, TurretReset, TurretRight)

SWING_S = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 25
STREAM_PERIOD = 0.1

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


def pump(sub, seconds, log, stream=None):
    """Receive for `seconds`; log (t, phase, enc, color); stream cmds."""
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
                        packet.color_sensor.raw))


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

    log = []
    print("baseline 2 s at rest...")
    pump(sub, 2.0, log)

    phases = []
    for name, cmd in (("LEFT", TurretLeft(SPEED)), ("RIGHT", TurretRight(SPEED))):
        t0 = time.time()
        pump(sub, SWING_S, log, stream=cmd)
        push.send(compress(TurretReset()))
        t1 = time.time()
        time.sleep(1.0)
        phases.append((name, t0, t1, log[-1][1]))
        print("{} swing done: encoder now {}".format(name, int(log[-1][1])))

    # --- analyze ---
    arr = np.array([(l[0], l[1], l[2]) for l in log], dtype=float)
    rest_mask = np.ones(len(arr), dtype=bool)
    for _, t0, t1, _ in phases:
        rest_mask &= ~((arr[:, 0] >= t0 - 0.2) & (arr[:, 0] <= t1 + 0.2))
    rest_colors = arr[rest_mask, 2]
    med = float(np.median(rest_colors))
    mad = float(np.median(np.abs(rest_colors - med))) or 1.0
    threshold = max(4.0 * mad, 12)

    print("\n=== COLOR TRACE (baseline median={:.0f}, mad={:.1f}, "
          "threshold={:.0f}; dev=*>*) ===".format(med, mad, threshold))
    for t, enc, col in log:
        phase = "."
        for name, t0, t1, _ in phases:
            if t0 - 0.2 <= t <= t1 + 0.2:
                phase = name[0]
        mark = " *dev*".format() if abs(col - med) > threshold else ""
        print("{:>11.3f} {} enc={:>7.0f} color={:>4.0f}{}".format(
            t % 1000, phase, enc, col, mark))

    print("\n=== PER-PHASE SUMMARY ===")
    if len(rest_colors) == 0:
        print("rest: NO SAMPLES")
    else:
        print("rest: median={:.0f} min={} max={}".format(
            med, int(rest_colors.min()), int(rest_colors.max())))
    for name, t0, t1, enc_end in phases:
        m = (arr[:, 0] >= t0 - 0.2) & (arr[:, 0] <= t1 + 0.2)
        if not m.any():
            print("{}: NO TELEMETRY SAMPLES - stream died mid-probe "
                  "(known wedge bug koc-hw-kinect-wedge?)".format(name))
            continue
        cols = arr[m, 2]
        encs = arr[m, 1]
        devs = arr[m & (np.abs(arr[:, 2] - med) > threshold)]
        print("{}: enc {}..{} color min={} max={} span={} dev_samples={} "
              "{}".format(
                  name, int(encs.min()), int(encs.max()), int(cols.min()),
                  int(cols.max()), int(cols.max() - cols.min()), len(devs),
                  "dev enc {}".format([int(e) for e in devs[:, 1]])
                  if len(devs) else ""))

    csv_path = "/tmp/koc_calib/color_sweep.csv"
    with open(csv_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "encoder", "color"])
        for t, enc, col in log:
            wr.writerow([round(t, 3), int(enc), int(col)])
    print("CSV saved:", csv_path)

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
