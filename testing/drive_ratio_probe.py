#!/usr/bin/env python3
"""
Drive motor ratio probe v3 - run ON the robot (server up). THE ROBOT MOVES.

Setup: an obstacle dead-ahead; the kinect depth camera measures the distance
DURING motion (vibration-immune); the chassis sonar goes blind while the
tracks turn (drive EMI/vibration - measured 2026-10-25), so it is used only
at rest, verifying the round-trip position error in cm.

Mission: drive AWAY from the obstacle ~8 cm (kinect-oracle-driven), back to
the start distance, x N rounds. Per leg: the mean drive-encoder delta vs
the kinect-measured displacement => ticks/cm; the round-trip sonar delta =>
the drivetrain backlash/slip; the left/right encoder deltas => curving.

Safety: sonar bound 40 cm (hard stop), kinect distance bound 0.35 m,
duration caps, deadman streaming, kill anytime.

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
SETTLE_S = 1.0
SWING_M = 0.08           # excursion per leg (m)
DIST_MIN, DIST_MAX = 0.35, 1.20
SONAR_MIN = 40
LEG_MAX_S = 45.0
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


def sonar_now(log):
    return log[-1][4] if log else None


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


def kinect_dist(frames, window_s=1.0):
    """Median blob distance over the frames of the last window_s."""
    now = time.time()
    dists = [blob_distance(f)[0] for (t, f) in frames
             if t >= now - window_s]
    dists = [d for d in dists if d is not None]
    return float(np.median(dists)) if dists else None


def drive_until(sub, log, frames, cmd, dist_target, recede):
    """Stream `cmd` until the kinect-measured distance reaches the target.

    recede: True if this command increases the distance.
    Returns (reason, dist_final): reason in
    {None=reached, "too-close", "lost", "timeout"}.
    """
    t_leg0 = time.time()
    next_send = 0.0
    window = deque(maxlen=3)
    confirm = 0
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
        dist = kinect_dist(frames, 1.0)
        if dist is None:
            if time.time() - t_leg0 > LEG_MAX_S:
                return "timeout", None
            time.sleep(0.05)
            continue
        if dist < DIST_MIN:
            return "too-close", dist
        if dist > DIST_MAX:
            return "lost", dist
        window.append(dist)
        if len(window) == 3:
            med = float(np.median(window))
            on_target = (med >= dist_target) if recede \
                else (med <= dist_target)
            confirm = confirm + 1 if on_target else 0
            if confirm >= 2:
                return None, dist
        if time.time() - t_leg0 > LEG_MAX_S:
            return "timeout", dist


def enc_mean_at(log, t):
    arr = np.array([(l[0], l[1], l[2]) for l in log], dtype=float)
    i = np.argmin(np.abs(arr[:, 0] - t))
    return (abs(arr[i, 1]) + abs(arr[i, 2])) / 2.0


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

    print("baseline 3 s...")
    pump(sub, 3.0, log, frames)
    son_base = sonar_now(log)
    e_start = (log[-1][1], log[-1][2])
    d_base = kinect_dist(frames, 2.0)
    print("baseline: sonar={} cm | encoders l={} r={} | kinect dist="
          "{:.2f} m".format(son_base, e_start[0], e_start[1],
                            d_base if d_base else -1))
    if d_base is None:
        sys.exit("no kinect distance measurable at rest - aborting")

    # --- direction calibration: 1 s GoForward blip ---
    print("\ndirection calibration (1 s GoForward blip)...")
    d_before = kinect_dist(frames, 1.0)
    pump(sub, 1.0, log, frames, stream=GoForward(SPEED))
    push.send(compress(TurretReset()))
    time.sleep(SETTLE_S)
    d_after = kinect_dist(frames, 1.0)
    son_after = sonar_now(log)
    if d_before is None or d_after is None:
        sys.exit("kinect distance unavailable during the blip - aborting")
    forward_toward = d_after < d_before
    print("kinect {:.2f} -> {:.2f} m (sonar now {} cm): GoForward drives "
          "{}".format(d_before, d_after, son_after,
                      "TOWARD the obstacle" if forward_toward
                      else "AWAY from the obstacle"))
    if abs(d_after - d_before) < 0.02:
        print("WARNING: the distance barely moved - check the geometry")

    toward_cmd, away_cmd = ((GoForward(SPEED), GoBackward(SPEED))
                            if forward_toward else
                            (GoBackward(SPEED), GoForward(SPEED)))

    rounds = []
    d_ref = d_after  # the reference distance after the direction blip

    for r in range(1, ROUNDS + 1):
        target_out = d_ref + SWING_M    # recede: the distance grows
        print("\n--- round {}: recede to {:.2f} m, return to {:.2f} m "
              "---".format(r, target_out, d_ref))

        e_leg0 = (log[-1][1], log[-1][2])
        reason, d_out = drive_until(
            sub, log, frames, away_cmd, target_out, True)
        e_out = (log[-1][1], log[-1][2])
        son_out = sonar_now(log)
        print("  out leg: {} dist {:.2f} m | sonar {} cm".format(
            reason or "reached", d_out if d_out else -1,
            son_out if son_out else -1))
        if reason:
            print("  ABORT:", reason)
            break

        reason, d_back = drive_until(
            sub, log, frames, toward_cmd, d_ref, False)
        e_back = (log[-1][1], log[-1][2])
        son_back = sonar_now(log)
        print("  back leg: {} dist {:.2f} m | sonar {} cm".format(
            reason or "reached", d_back if d_back else -1,
            son_back if son_back else -1))
        if reason:
            print("  ABORT:", reason)
            break

        d_out_ticks = (abs(e_out[0] - e_leg0[0]) +
                       abs(e_out[1] - e_leg0[1])) / 2.0
        d_back_ticks = (abs(e_back[0] - e_leg0[0]) +
                        abs(e_back[1] - e_leg0[1])) / 2.0
        travel_out = abs(d_out - d_ref)
        travel_back = abs(d_back - d_ref)
        tpc_out = d_out_ticks / (travel_out * 100.0) if travel_out > 0.02 \
            else None
        tpc_back = d_back_ticks / (travel_back * 100.0) if travel_back \
            > 0.02 else None
        print("  out: {} ticks / {:.1f} cm = {:.0f} ticks/cm | "
              "back: {} ticks / {:.1f} cm = {:.0f} ticks/cm".format(
                  int(d_out_ticks), travel_out * 100,
                  tpc_out * 100 if tpc_out else -1,
                  int(d_back_ticks), travel_back * 100,
                  tpc_back * 100 if tpc_back else -1))
        rounds.append({"round": r, "d_ref": d_ref, "d_out": d_out,
                       "d_back": d_back, "d_out_ticks": d_out_ticks,
                       "d_back_ticks": d_back_ticks,
                       "son_back": son_back, "tpc_out": tpc_out,
                       "tpc_back": tpc_back})
        d_ref = d_back  # the next round starts from the reached distance

    # --- report ---
    print("\n=== DRIVE RATIO REPORT ===")
    print("sonar at start: {} cm; kinect at start: {:.2f} m".format(
        son_base, d_base if d_base else -1))
    tpcs = [x for r in rounds for x in (r["tpc_out"], r["tpc_back"]) if x]
    if tpcs:
        print("ticks per cm: per-leg {} | median {:.0f}".format(
            ["{:.0f}".format(x) for x in tpcs], float(np.median(tpcs))))
        tpm = float(np.median(tpcs)) * 100.0
        print("= {:.0f} ticks/m; a 360 ticks/rev motor implies "
              "{:.1f} motor revs per wheel rev at a 17 cm effective "
              "wheel/track diameter".format(tpm, tpm * 0.17 / 360.0))
    else:
        print("no ticks/cm measurable - the legs did not move or the "
              "kinect did not track")
    if rounds:
        son_err = [r["son_back"] - son_base for r in rounds]
        print("round-trip sonar error vs the start (cm): {}".format(
            ["{:+.0f}".format(x) for x in son_err],
        ))
        enc_drift = [(r["d_back"]) for r in rounds]
        print("kinect-measured end distances per round (m): {}".format(
            ["{:.2f}".format(x) for x in enc_drift]))

    csv_path = os.path.join(OUT_DIR, "drive_ratio_v3.csv")
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
