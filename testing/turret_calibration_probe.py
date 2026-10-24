#!/usr/bin/env python3
"""
Turret gear-ratio calibration probe - run ON the robot (server must be up).

Setup (user-provided hardware facts):
- A LEGO color sensor rides on the turret (BrickPi PORT_1, light-on mode),
  ~5 cm above the robot body.
- A cable sticks out from the back of the robot body, ~5 cm below the
  sensor's sweep circle, at the position that marks "camera forward".
- The old paper dial is gone; the cable is the single remaining index mark.
- The turret is geared down from the PORT_C motor; the ratio is unknown.

Method:
1. Baseline: color raw for 3 s at rest (noise floor).
2. Rotate the turret at low speed for DURATION s in one direction while
   logging (t, encoder, color_raw) from telemetry (~10 Hz) and keeping a
   small ring buffer of Kinect frames.
3. Repeat in the other direction.
4. Detect color-deviation clusters ("cable crossings"); consecutive
   crossings should be exactly one turret revolution apart, so
   ticks_per_rev = |delta encoder| between consecutive crossings, and
   gear_ratio = ticks_per_rev / 360 (motor revs per turret rev).
5. Kinect cross-check: the mean abs pixel difference between frames at
   consecutive crossings should be LOW (same heading after one rev) compared
   to the start-vs-end pair.

Output: printed report + CSV at /tmp/koc_calib/turret_calib.csv

Usage (on the robot):
    cd ~/rpi_lego_robot && ~/.virtualenvs/pi_robot3/bin/python \\
        testing/turret_calibration_probe.py [duration_s] [speed]
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
    HeartbeatRequest, KinectPacket, TelemetryPacket, TurretLeft, TurretReset,
    TurretRight)

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 50
OUT_DIR = "/tmp/koc_calib"
FRAME_RING = 30          # ~900 KB each; keep small (RPi has 925 MB)
STREAM_PERIOD = 0.1      # command streaming period (deadman-safe)
MIN_FEATURE = 12         # min color deviation to count as a feature
K_MAD = 4.0              # deviation threshold in robust sigmas
GAP_SAMPLES = 5          # max index gap within one feature cluster

push = None  # set in main(); used by collect()


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


def collect(sub, seconds, log, frames, stream=None):
    """Receive for `seconds`; log (t, enc, color); keep frames; stream cmds."""
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
            time.sleep(0.01)
            continue
        if isinstance(packet, TelemetryPacket):
            log.append((time.time(), packet.turret_motor.angle,
                        packet.color_sensor.raw))
        elif isinstance(packet, KinectPacket):
            frames.append((time.time(), np.asarray(packet.get_video_frame())))


def detect_crossings(log, baseline_med, mad):
    """Return (time spans where color deviates from baseline, threshold)."""
    if len(log) < 3 or mad == 0:
        return [], None
    arr = np.array(log, dtype=float)
    t, col = arr[:, 0], arr[:, 2]
    threshold = max(K_MAD * mad, MIN_FEATURE)
    mask = np.abs(col - baseline_med) > threshold
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return [], float(threshold)
    # group consecutive sample indices (a gap > GAP_SAMPLES starts a new group)
    groups = []
    start = prev = idx[0]
    for k in idx[1:]:
        if k - prev > GAP_SAMPLES:
            groups.append((start, prev))
            start = k
        prev = k
    groups.append((start, prev))
    # to time spans, then merge spans separated by < 0.3 s
    spans = [(t[a], t[b]) for a, b in groups]
    merged = []
    for s in spans:
        if merged and s[0] - merged[-1][1] < 0.3:
            merged[-1] = (merged[-1][0], s[1])
        else:
            merged.append(s)
    return merged, float(threshold)


def nearest_frame(frames, t):
    if not frames:
        return None
    return min(frames, key=lambda f: abs(f[0] - t))[1]


def analyze(name, log, baseline_med, mad, frames, expected_ticks):
    spans, threshold = detect_crossings(log, baseline_med, mad)
    arr = np.array(log, dtype=float)
    enc_start, enc_end = arr[0, 1], arr[-1, 1]
    moved = abs(enc_end - enc_start)
    print("\n--- {} ---".format(name))
    print("encoder: {} -> {} (moved {}, expected ~{})".format(
        int(enc_start), int(enc_end), int(moved), int(expected_ticks)))
    if moved < 0.5 * expected_ticks:
        print("WARNING: encoder moved far less than commanded - "
              "possible stall/mechanical limit")
    print("color: baseline median={:.0f} mad={:.1f} threshold={} "
          "min={} max={}".format(baseline_med, mad,
                                 int(threshold) if threshold else "-",
                                 int(arr[:, 2].min()), int(arr[:, 2].max())))
    print("feature spans detected: {}".format(len(spans)))
    if len(spans) < 2:
        print("not enough crossings to estimate the gear ratio")
        return None
    arr_t = arr[:, 0]
    ticks = []
    for (t0, _), (t1, _) in zip(spans, spans[1:]):
        e0 = arr[np.argmin(np.abs(arr_t - (t0 + 0.05))), 1]
        e1 = arr[np.argmin(np.abs(arr_t - (t1 + 0.05))), 1]
        ticks.append(abs(e1 - e0))
    ticks = np.array(ticks, dtype=float)
    med = float(np.median(ticks))
    good = ticks[np.abs(ticks - med) < 0.3 * med]  # drop missed-crossing doubles
    ticks_per_rev = float(np.median(good)) if len(good) else med
    print("ticks between consecutive crossings: {}".format(
        [int(x) for x in ticks]))
    print("ticks per turret revolution: {:.0f} ({} of {} diffs used)".format(
        ticks_per_rev, len(good), len(ticks)))
    print("gear ratio: {:.2f} motor revs per turret rev ({} ticks / 360)".format(
        ticks_per_rev / 360.0, int(ticks_per_rev)))
    if frames:
        cframes = [nearest_frame(frames, t0) for (t0, _) in spans]
        cframes = [f for f in cframes if f is not None]
        if len(cframes) >= 2:
            consec = [float(np.mean(np.abs(
                cframes[i + 1].astype(float) - cframes[i].astype(float))))
                for i in range(len(cframes) - 1)]
            far = float(np.mean(np.abs(
                cframes[0].astype(float) - cframes[-1].astype(float))))
            print("kinect frame diff: consecutive crossings mean={:.1f} "
                  "(low=same heading after 1 rev), first-vs-last={:.1f}".format(
                      float(np.mean(consec)), far))
    return ticks_per_rev


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

    frames = deque(maxlen=FRAME_RING)

    # --- baseline ---
    print("baseline (3 s, motors idle)...")
    base_log = []
    collect(sub, 3.0, base_log, frames)
    colors = np.array([l[2] for l in base_log], dtype=float)
    med = float(np.median(colors))
    mad = float(np.median(np.abs(colors - med))) or 1.0
    print("baseline color: median={:.0f} mad={:.1f} min={} max={}".format(
        med, mad, int(colors.min()), int(colors.max())))

    # --- two rotation phases, opposite directions ---
    results = {}
    for name, cmd in (("rotation A (TurretRight)", TurretRight(SPEED)),
                      ("rotation B (TurretLeft)", TurretLeft(SPEED))):
        log = []
        expected = 5.12 * SPEED * DURATION  # measured ~5.12 ticks/s per unit @80
        collect(sub, DURATION, log, frames, stream=cmd)
        push.send(compress(TurretReset()))
        time.sleep(0.5)
        res = analyze(name, log, med, mad, frames, expected)
        results[name] = (res, log)

    # --- save csv ---
    csv_path = os.path.join(OUT_DIR, "turret_calib.csv")
    with open(csv_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["phase", "t", "encoder", "color"])
        for name, (_, log) in results.items():
            for row in log:
                wr.writerow([name, round(row[0], 3), int(row[1]), int(row[2])])
    print("\nCSV saved:", csv_path)

    ests = [r for r, _ in results.values() if r]
    if ests:
        ests = np.array(ests)
        print("\n=== GEAR RATIO ESTIMATE ===")
        print("ticks per turret rev: per-phase {} | combined median {:.0f}".format(
            [int(e) for e in ests], float(np.median(ests))))
        print("gear ratio: {:.2f} motor revs / turret rev".format(
            float(np.median(ests)) / 360.0))
    else:
        print("\nno ratio estimate - increase duration or check sensor geometry")

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
