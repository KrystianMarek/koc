#!/usr/bin/env python3
"""
Drive motor ratio probe v4 - run ON the robot (server up). THE ROBOT MOVES.

Lessons learned (2026-10-25):
- The sonar (chassis PORT_4) is blind WHILE the tracks turn (EMI/vibration)
  but reads reliably AT REST -> the at-rest position oracle.
- The kinect USB stream dies after robot motion and may not recover for
  minutes -> the kinect is an OPTIONAL cross-check with a long wait, never
  the control oracle.
- The drive train is heavily geared: ~1.16 ticks/s per speed unit (vs the
  turret's 7.2) -> all leg budgets use the drive rate.

Mission: encoder-driven legs (drive a computed tick count blind, stop,
measure at rest with the sonar). Round 1 is a short rate blip that
calibrates ticks/cm; the later legs target 20 cm excursions (the user's
clearance: 30 cm each way, 70 cm total cable envelope). The round-trip
sonar delta = the drivetrain backlash/slip. The left/right deltas = curving.

Safety: the sonar < 45 cm after any leg -> back off by the estimated ticks
and abort; per-leg duration caps; deadman streaming; kill anytime.

Usage (on the robot):
    cd ~/rpi_lego_robot && ~/.virtualenvs/pi_robot3/bin/python \\
        testing/drive_ratio_probe.py [rounds] [speed]
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
    GoBackward, GoForward, HeartbeatRequest, TelemetryPacket, TurretReset)

ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 60
STREAM_PERIOD = 0.3
SETTLE_S = 3.5
BLIP_TICKS = 1500        # the rate-calibration blip (~5-17 cm, unknown yet)
TARGET_CM = 20.0         # the excursion per leg for the calibrated rounds
SONAR_ABORT = 45         # cm - too close to the obstacle: back off + abort
TICKS_PER_S_PER_UNIT = 1.16   # the measured drive rate (the broken-run data)
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


def pump(sub, seconds, log, stream=None):
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


def drive_mean(log):
    return (abs(log[-1][1]) + abs(log[-1][2])) / 2.0 if log else None


def sonar_now(log):
    return log[-1][4] if log else None


def sonar_settled(sub, log, wait_s=6.0):
    """Wait for the post-motion sonar recovery; return the settled reading."""
    time.sleep(SETTLE_S)
    vals = []
    t0 = time.time()
    while time.time() - t0 < wait_s:
        pump(sub, 0.5, log)
        s = sonar_now(log)
        if s is not None and s != 255:
            vals.append(s)
        if len(vals) >= 3:
            break
    return float(np.median(vals)) if vals else None


def drive_ticks(sub, log, cmd, target_ticks, max_s):
    """Encoder-driven leg (the mean of the two drive encoders).

    Returns (achieved_mean_delta, reason or None); the reason is set on the
    duration cap (a probable stall/limit).
    """
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
        time.sleep(0.005)


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

    log = []

    print("baseline 3 s at rest...")
    pump(sub, 3.0, log)
    s_base = sonar_settled(sub, log)
    e_start = (log[-1][1], log[-1][2])
    print("baseline: sonar={} cm | encoders l={} r={}".format(
        s_base, e_start[0], e_start[1]))
    if s_base is None:
        sys.exit("the sonar gives no reading at rest - check the sensor")

    # --- round 1: the rate blip ---
    print("\nround 1: rate blip, {} ticks forward (blind, ~{:.0f} s)".format(
        BLIP_TICKS, BLIP_TICKS / (TICKS_PER_S_PER_UNIT * SPEED)))
    d_fwd, err = drive_ticks(sub, log, GoForward(SPEED), BLIP_TICKS,
                             BLIP_TICKS / (TICKS_PER_S_PER_UNIT * SPEED) * 3)
    s_after = sonar_settled(sub, log)
    if s_after is None:
        sys.exit("the sonar did not recover after the blip")
    travel = s_base - s_after  # cm; positive = toward the obstacle
    print("  blip: {:+.0f} ticks | sonar {} -> {} cm (travel {:+.1f} cm)"
          .format(d_fwd, s_base, s_after, travel))
    if abs(travel) < 2:
        sys.exit("the robot did not measurably move - check the tracks and "
                 "the geometry")
    ticks_per_cm = abs(d_fwd) / abs(travel)
    print("  ticks/cm: {:.1f}".format(ticks_per_cm))
    if travel < 0:
        print("  NOTE: the blip moved AWAY from the obstacle - the forward/"
              "backward roles are swapped for this robot's wiring")

    toward_cmd = GoForward(SPEED) if travel > 0 else GoBackward(SPEED)
    away_cmd = GoBackward(SPEED) if travel > 0 else GoForward(SPEED)

    # --- calibrated rounds: 20 cm out, 20 cm back ---
    rounds = []
    s_ref = s_after
    ticks_cm = ticks_per_cm
    for r in range(1, ROUNDS + 1):
        target_ticks = int(min(TARGET_CM * ticks_cm, 8000))
        max_s = target_ticks / (TICKS_PER_S_PER_UNIT * SPEED) * 2.5 + 10
        print("\nround {}: {} {} ticks (~{:.0f} cm, cap {:.0f} s)".format(
            r, "OUT" if travel > 0 else "BACK", int(target_ticks),
            target_ticks / ticks_cm, max_s))
        d_out, err_out = drive_ticks(sub, log, toward_cmd if travel > 0
                                     else away_cmd, target_ticks, max_s)
        s_out = sonar_settled(sub, log)
        if s_out is None:
            sys.exit("the sonar did not recover after the out leg")
        travel_out = s_out - s_ref  # cm; + = away from the obstacle
        print("  out: {:+.0f} ticks | sonar {} cm (delta {:+.1f} cm from "
              "the reference)".format(d_out, s_out, travel_out))
        if s_out < SONAR_ABORT:
            print("  TOO CLOSE to the obstacle - backing off and aborting")
            drive_ticks(sub, log, away_cmd if travel > 0 else toward_cmd,
                        int(abs(s_out - SONAR_ABORT) * ticks_cm), max_s)
            break

        d_back, err_back = drive_ticks(sub, log, away_cmd if travel > 0
                                       else toward_cmd, target_ticks, max_s)
        s_back = sonar_settled(sub, log)
        if s_back is None:
            sys.exit("the sonar did not recover after the back leg")
        travel_back = s_back - s_ref
        print("  back: {:+.0f} ticks | sonar {} cm (round-trip error "
              "{:+.1f} cm)".format(d_back, s_back, travel_back))
        if s_back < SONAR_ABORT:
            print("  TOO CLOSE - aborting")
            break

        rounds.append({"round": r, "d_out": d_out, "d_back": d_back,
                       "son_out": s_out, "son_back": s_back,
                       "travel_out": travel_out, "err": travel_back,
                       "tpc_out": abs(d_out) / abs(travel_out)
                       if abs(travel_out) > 1 else None,
                       "tpc_back": abs(d_back) / abs(travel_back)
                       if abs(travel_back) > 1 else None})
        s_ref = s_back

    # --- report ---
    print("\n=== DRIVE RATIO REPORT ===")
    print("rate blip: {} ticks / {:.1f} cm = {:.1f} ticks/cm".format(
        int(abs(d_fwd)), abs(travel), ticks_per_cm))
    tpcs = [x for r in rounds for x in (r["tpc_out"], r["tpc_back"]) if x]
    if tpcs:
        print("ticks per cm (calibrated legs): {} | median {:.1f}".format(
            ["{:.0f}".format(x) for x in tpcs], float(np.median(tpcs))))
        tpm = float(np.median(tpcs)) * 100.0
        print("= {:.0f} ticks/m; a 360 ticks/rev motor implies "
              "{:.1f} motor revs per wheel rev at a 17 cm effective "
              "diameter".format(tpm, tpm * 0.17 / 360.0))
    else:
        print("the calibrated legs did not yield ticks/cm (the travels were "
              "within the sonar's 1 cm quantization)")
    if rounds:
        errs = [r["err"] for r in rounds]
        print("round-trip sonar errors (cm): {}".format(
            ["{:+.1f}".format(x) for x in errs]))
        pairs = [(r["d_out"], r["d_back"]) for r in rounds]
        print("out/back tick pairs: {}".format(
            ["{:.0f}/{:.0f}".format(a, b) for a, b in pairs]))
        lr = []
        print("NOTE: the left/right encoder split per leg is in the CSV "
              "(a divergence = curving)")

    csv_path = os.path.join(OUT_DIR, "drive_ratio_v4.csv")
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
