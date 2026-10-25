#!/usr/bin/env python3
"""
Drive motor ratio probe v5 - run ON the robot (server up). THE ROBOT MOVES.

Oracle: the KINECT depth camera only. The sonar is dead (bd
koc-hw-sonar-dead - the 20 y/o LEGO US sensor reads 255 constantly), and it
was blind during motion anyway. The kinect blob distance is +-1-3 mm
accurate at 0.5-1 m (per the FrameProcessor docstring) and reads during
motion; the catch: the robot's vibration kills the kinect's USB stream for
~13-16 s after each leg (the self-healing child's exit-respawn cycle), so
every measurement waits out the recovery with retries.

Mission: a rate-calibration blip (1500 ticks - auto-detects the drive
direction), then N rounds of "20 cm away from the obstacle, 20 cm back"
(encoder-driven legs from the calibrated ticks/cm). Per leg: the mean
drive-encoder delta vs the kinect-measured displacement => ticks/cm; the
round-trip distance error => the drivetrain backlash/slip; the left/right
encoder split => curving.

Safety: the kinect distance bound 0.45..1.30 m (outside = back off/abort),
per-leg duration caps from the measured rate, deadman streaming, kill
anytime. The obstacle sits ~0.8 m dead-ahead (user's geometry).

Usage (on the robot):
    cd ~/rpi_lego_robot && ~/.virtualenvs/pi_robot3/bin/python \\
        testing/drive_ratio_probe.py [rounds] [speed]
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
    GoBackward, GoForward, HeartbeatRequest, KinectPacket, TelemetryPacket,
    TurretReset)

ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 60
STREAM_PERIOD = 0.3
BLIP_TICKS = 1500
TARGET_CM = 20.0         # the excursion per calibrated leg
DIST_MIN, DIST_MAX = 0.45, 1.30
RECOVERY_S = 16.0        # the kinect USB respawn cycle after motion
RETRY_S = 40.0           # the max wait for the first valid measurement
TAN_SCALE, TAN_OFFSET, MULT = 2842.5, 1.1863, 0.1236
VALID_MIN, VALID_MAX = 300, 1008
OUT_DIR = "/tmp/koc_calib"

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
            log.append((time.time(), packet.left_motor.angle,
                        packet.right_motor.angle, packet.color_sensor.raw,
                        packet.ultrasound_sensor.raw))
        elif isinstance(packet, KinectPacket):
            frames.append((time.time(), np.asarray(packet.get_depth())))


def drive_mean(log):
    return (abs(log[-1][1]) + abs(log[-1][2])) / 2.0 if log else None


def latest_depth(frames, after_t):
    for t, f in reversed(frames):
        if t >= after_t:
            return f
    return None


def blob_distance(depth):
    """(distance_m, blob_x) of the nearest-valid cluster, or (None, None)."""
    valid = (depth >= VALID_MIN) & (depth <= VALID_MAX)
    if not valid.any():
        return None, None
    vals = depth[valid]
    thresh = np.percentile(vals, 10)
    mask = valid & (depth <= thresh + 5)
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return None, None
    raw = float(np.median(depth[mask]))
    return 0.1236 * np.tan(raw / TAN_SCALE + TAN_OFFSET), float(xs.mean())


def wait_kinect_distance(sub, log, frames, max_wait=RETRY_S):
    """Wait (pumping) until a valid blob distance is measurable.

    Handles the post-motion USB respawn cycle (~16 s). Returns
    (distance_m or None, measure_t).
    """
    t0 = time.time()
    while time.time() - t0 < max_wait:
        mark = time.time()
        pump(sub, 1.2, log, frames)
        depth = latest_depth(frames, mark - 0.5)
        if depth is not None:
            dist, _ = blob_distance(depth)
            if dist is not None:
                return dist, time.time()
    return None, time.time()


def drive_ticks(sub, log, cmd, target_ticks, max_s):
    """Encoder-driven leg (the mean of the two drive encoders)."""
    start = drive_mean(log)
    t_leg0 = time.time()
    next_send = 0.0
    while True:
        now = time.time()
        if now >= next_send:
            push.send(compress(cmd))
            next_send = now + STREAM_PERIOD
        try:
            packet = decompress(sub.recv(zmq.NOBLOCK))
        except zmq.Again:
            time.sleep(0.005)
            continue
        if isinstance(packet, TelemetryPacket):
            log.append((time.time(), packet.left_motor.angle,
                        packet.right_motor.angle, packet.color_sensor.raw,
                        packet.ultrasound_sensor.raw))
        mean = drive_mean(log)
        if abs(mean - start) >= target_ticks:
            push.send(compress(TurretReset()))
            return drive_mean(log) - start, None
        if time.time() - t_leg0 > max_s:
            push.send(compress(TurretReset()))
            achieved = drive_mean(log) - start
            return achieved, "duration cap (achieved {:.0f} of {:.0f})".format(
                int(achieved), int(target_ticks))


def main():
    global push
    t_mission = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    ctx = zmq.Context()
    handshake(ctx)

    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://127.0.0.1:5559")
    sub.setsockopt(zmq.SUBSCRIBE, b"")
    sub.setsockopt(zmq.RCVTIMEO, 1000)

    push = ctx.socket(zmq.PUSH)
    push.connect("tcp://127.0.0.1:5560")

    frames = deque(maxlen=40)
    log = []

    print("waiting for the first valid kinect distance (baseline)...")
    d0, t_meas = wait_kinect_distance(sub, log, frames, RETRY_S + 20)
    if d0 is None:
        sys.exit("no valid kinect distance in {} s - is the camera healthy?"
                 .format(RETRY_S + 20))
    e_start = (log[-1][1], log[-1][2])
    print("baseline: kinect dist {:.3f} m | encoders l={} r={}".format(
        d0, e_start[0], e_start[1]))

    # --- round 0: the rate-calibration blip ---
    print("\nround 0: rate blip, {} ticks (auto-detects the direction; "
          "the kinect recovers ~{} s after)".format(
              BLIP_TICKS, int(RECOVERY_S)))
    d_fwd, err = drive_ticks(sub, log, GoForward(SPEED), BLIP_TICKS,
                             BLIP_TICKS / 50.0 + 30)
    print("  blip done: {:+.0f} ticks{}".format(
        d_fwd, " ({})".format(err) if err else ""))
    d1, t1 = wait_kinect_distance(sub, log, frames, RETRY_S + 20)
    if d1 is None:
        sys.exit("no kinect distance after the blip - the USB link never "
                 "recovered")
    travel = d0 - d1  # m; positive = toward the obstacle
    print("  kinect dist {:.3f} -> {:.3f} m (travel {:+.2f} cm = {})".format(
        d0, d1, travel * 100, "TOWARD" if travel > 0 else "AWAY"))
    if abs(travel) < 0.02:
        sys.exit("the robot did not measurably move ({:+.3f} m) - check "
                 "the tracks and the geometry".format(travel))
    ticks_per_cm = abs(d_fwd) / (abs(travel) * 100.0)
    print("  ticks/cm: {:.1f}".format(ticks_per_cm))

    toward_cmd = GoForward(SPEED) if travel > 0 else GoBackward(SPEED)
    away_cmd = GoBackward(SPEED) if travel > 0 else GoForward(SPEED)

    # --- calibrated rounds: 20 cm out, 20 cm back ---
    rounds = []
    d_ref = d1
    for r in range(1, ROUNDS + 1):
        target_ticks = int(min(TARGET_CM * ticks_per_cm, 12000))
        max_s = target_ticks / (60.0) * 2.5 + 20  # ~60 ticks/s at speed 60
        print("\nround {}: AWAY {} ticks (cap {:.0f} s), then BACK".format(
            r, int(target_ticks), max_s))

        d_away, err_a = drive_ticks(sub, log, away_cmd, target_ticks, max_s)
        d_a, t_a = wait_kinect_distance(sub, log, frames, RETRY_S + 20)
        if d_a is None:
            print("  ABORT: no kinect distance after the away leg")
            break
        print("  away: {:+.0f} ticks | dist {:.3f} m (travel {:+.1f} cm)"
              .format(d_away, d_a, (d_a - d_ref) * 100))

        d_back, err_b = drive_ticks(sub, log, toward_cmd, target_ticks,
                                    max_s)
        d_b, t_b = wait_kinect_distance(sub, log, frames, RETRY_S + 20)
        if d_b is None:
            print("  ABORT: no kinect distance after the back leg")
            break
        print("  back: {:+.0f} ticks | dist {:.3f} m (round-trip error "
              "{:+.1f} cm)".format(d_back, d_b, (d_b - d_ref) * 100))

        if d_b < DIST_MIN or d_b > DIST_MAX:
            print("  ABORT: the final distance {:.2f} m is outside the "
                  "safe band".format(d_b))
            break

        travel_a = abs(d_a - d_ref)
        travel_b = abs(d_b - d_ref)
        tpc_a = d_away / (travel_a * 100.0) if travel_a > 0.02 else None
        tpc_b = d_back / (travel_b * 100.0) if travel_b > 0.02 else None
        rounds.append({"round": r, "d_ref": d_ref, "d_a": d_a, "d_b": d_b,
                       "d_away": d_away, "d_back": d_back,
                       "tpc_away": tpc_a, "tpc_back": tpc_b,
                       "err_cm": (d_b - d_ref) * 100})
        d_ref = d_b

    # --- report ---
    print("\n=== DRIVE RATIO REPORT ===")
    print("rate blip: {} ticks / {:.1f} cm = {:.1f} ticks/cm".format(
        int(abs(d_fwd)), abs(travel) * 100, ticks_per_cm))
    tpcs = [x for r in rounds for x in (r["tpc_away"], r["tpc_back"]) if x]
    if tpcs:
        print("ticks per cm (calibrated legs): {} | median {:.1f}".format(
            ["{:.0f}".format(x) for x in tpcs], float(np.median(tpcs))))
        tpm = float(np.median(tpcs)) * 100.0
        print("= {:.0f} ticks/m; a 360 ticks/rev motor implies "
              "{:.1f} motor revs per wheel rev at a 17 cm effective "
              "diameter".format(tpm, tpm * 0.17 / 360.0))
    else:
        print("the calibrated legs did not yield ticks/cm (the kinect "
              "displacement was under the 2 cm threshold)")
    if rounds:
        print("round-trip errors (cm): {}".format(
            ["{:+.1f}".format(r["err_cm"]) for r in rounds]))
        print("away/back tick pairs: {}".format(
            ["{:.0f}/{:.0f}".format(r["d_away"], r["d_back"])
             for r in rounds]))
        print("final kinect distance: {:.3f} m (start {:.3f})".format(
            rounds[-1]["d_b"], d0))

    csv_path = os.path.join(OUT_DIR, "drive_ratio_v5.csv")
    with open(csv_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "enc_left", "enc_right", "color", "sonar"])
        for row in log:
            wr.writerow([round(row[0], 3), int(row[1]), int(row[2]),
                         int(row[3]), int(row[4])])
    print("CSV saved:", csv_path)

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
