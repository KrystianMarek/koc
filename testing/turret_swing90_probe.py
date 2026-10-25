#!/usr/bin/env python3
"""
90-degree turret swing reliability probe - run ON the robot (server up).

Mission (bd koc-swing90): swing the turret LEFT 90 deg off center, then
RIGHT 180 deg, then LEFT 90 deg back - and check reliability + return
accuracy. The robot is static; measurements come from the encoder (PORT_C),
the color sensor (PORT_1), the ultrasonic sensor (PORT_4, obstacle at ~75 cm
dead-ahead = ground truth) and the Kinect depth stream.

Legs are ENCODER-DRIVEN: stream commands until |encoder - leg start| reaches
the target ticks, so the ratio's +-10% uncertainty does not affect the
travel. Safety:
- stall abort: a leg that undershoots 85% of its target (motor blocked,
  likely the in-turret cables) aborts the whole mission
- hard duration cap per leg (1.6x the expected time)
- deadman streaming at 10 Hz; kill anytime - motors stop in ~0.3 s

Per-pose snapshots (after a settle): encoder, color stats, sonar, kinect
depth stats (center-region raw, nearest-blob centroid/raw, valid fraction).
The final pose checks the return: encoder vs start, color vs the start
value, and whether the 75 cm obstacle blob re-centers on the image
(x ~ 320).

Usage (on the robot):
    cd ~/rpi_lego_robot && ~/.virtualenvs/pi_robot3/bin/python \\
        testing/turret_swing90_probe.py [speed]
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

SPEED = int(sys.argv[1]) if len(sys.argv) > 1 else 50
TICKS_PER_DEG = 125.0                   # measured 2026-10-25 (+-10%)
TARGET_TICKS = int(90 * TICKS_PER_DEG)  # 11250
# Stream at the wrapper's consumption rate (~1 cmd per 0.3 s cycle): a 0.1 s
# period backs up the 100-deep command queue during long legs and the backlog
# keeps executing after the reset (~1641-tick overshoot measured 2026-10-25).
STREAM_PERIOD = 0.3
SETTLE_S = 1.5
TICKS_PER_S = 5.12 * SPEED              # measured ticks/s per speed unit
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
            log.append((time.time(), packet.turret_motor.angle,
                        packet.color_sensor.raw,
                        packet.ultrasound_sensor.raw))
        elif isinstance(packet, KinectPacket):
            frames.append((time.time(), np.asarray(packet.get_depth())))


def latest_enc(log):
    return log[-1][1] if log else None


def latest_depth(frames, after_t):
    for t, f in reversed(frames):
        if t >= after_t:
            return f
    return None


def depth_stats(depth):
    valid = (depth >= 300) & (depth <= 1008)
    frac = float(valid.mean())
    m = depth[200:280, 280:360]
    m = m[(m >= 300) & (m <= 1008)]
    ctr = float(np.median(m)) if m.size else None
    vals = depth[valid]
    if vals.size == 0:
        return frac, ctr, None, None, 0
    thresh = np.percentile(vals, 10)
    mask = valid & (depth <= thresh + 5)
    ys, xs = np.nonzero(mask)
    braw = float(np.median(depth[mask])) if len(xs) else None
    bx = float(xs.mean()) if len(xs) else None
    return frac, ctr, braw, bx, int(len(xs))


def snapshot(label, sub, log, frames):
    time.sleep(SETTLE_S)
    mark = time.time()
    pump(sub, 1.2, log, frames)
    enc = latest_enc(log)
    win = [l for l in log if l[0] >= mark]
    col = np.array([l[2] for l in win], dtype=float)
    son = np.array([l[3] for l in win], dtype=float)
    depth = latest_depth(frames, mark)
    st = depth_stats(depth) if depth is not None else None
    print("{:>10}: enc {:>7.0f} | color {:>4.0f}..{:.0f} (med {:.0f}) | "
          "sonar {:>3.0f}..{:.0f} (med {:.0f})".format(
              label, enc, col.min(), col.max(), np.median(col),
              son.min(), son.max(), np.median(son)))
    if st:
        frac, ctr, braw, bx, n = st
        print("{:>10}   kinect: valid {:.2f} ctr_raw {} blob x {} raw {} "
              "n={}".format("", frac,
                            "{:.0f}".format(ctr) if ctr else "-",
                            "{:.0f}".format(bx) if bx else "-",
                            "{:.0f}".format(braw) if braw else "-", n))
    else:
        print("{:>10}   kinect: no frames".format(""))
    return {"label": label, "enc": enc,
            "color_med": float(np.median(col)) if col.size else -1,
            "sonar_med": float(np.median(son)) if son.size else -1,
            "ctr_raw": st[1] if st else None,
            "blob_x": st[3] if st else None,
            "blob_raw": st[2] if st else None}


def swing(sub, log, frames, cmd, target_ticks, name):
    """Encoder-driven leg; returns (achieved_ticks, stalled)."""
    start = latest_enc(log)
    expected_dur = target_ticks / float(TICKS_PER_S)
    deadline = time.time() + expected_dur * 1.6 + 2.0
    t_leg0 = time.time()
    next_send = 0.0
    stalled = False
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
            log.append((time.time(), packet.turret_motor.angle,
                        packet.color_sensor.raw,
                        packet.ultrasound_sensor.raw))
        enc = latest_enc(log)
        done = abs(enc - start) >= target_ticks
        timed_out = now > deadline
        if done or timed_out:
            push.send(compress(TurretReset()))
            if timed_out and not done:
                stalled = True
            achieved = abs(latest_enc(log) - start)
            print("  leg {}: target {} ticks, achieved {} ({:.0f}%) "
                  "in {:.1f}s{}".format(
                      name, target_ticks, int(achieved),
                      100.0 * achieved / target_ticks,
                      time.time() - t_leg0,
                      " STALLED" if stalled else ""))
            return achieved, stalled
        time.sleep(0.005)


def main():
    global push
    t0 = time.time()
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

    print("baseline 3 s at center...")
    pump(sub, 3.0, log, frames)
    e_start = latest_enc(log)

    # --- recenter toward the backlash midpoint (~+401) before the legs ---
    # The previous mission ended ~13 deg left of center (command-queue
    # backlog); the mechanical center sits in the 275..527 backlash band.
    PREDICTED_CENTER = 401
    t_rc = time.time()
    while abs(latest_enc(log) - PREDICTED_CENTER) > 150 and \
            time.time() - t_rc < 60:
        d = TurretRight(SPEED) if latest_enc(log) > PREDICTED_CENTER \
            else TurretLeft(SPEED)
        pump(sub, 0.5, log, frames, stream=d)
        push.send(compress(TurretReset()))
        time.sleep(0.4)
    e_start = latest_enc(log)

    poses = [snapshot("center0", sub, log, frames)]
    print("start encoder after recenter: {}".format(int(e_start)))

    legs = [("left 90", TurretLeft(SPEED), TARGET_TICKS),
            ("right 180", TurretRight(SPEED), 2 * TARGET_TICKS),
            ("left 90 home", TurretLeft(SPEED), TARGET_TICKS)]

    aborted = False
    for name, cmd, target in legs:
        print("\nleg {} (target {} ticks, ~{:.0f} s at {} ticks/s)...".format(
            name, target, target / float(TICKS_PER_S), TICKS_PER_S))
        achieved, stalled = swing(sub, log, frames, cmd, target, name)
        if stalled or achieved < 0.85 * target:
            print("\n!!! LEG UNDERSHOOT {:.0f}% - mechanical limit or stall."
                  " ABORTING MISSION (turret stays put; motors zeroed)".format(
                      100.0 * achieved / target))
            aborted = True
            break
        label = name.replace(" ", "")
        poses.append(snapshot(label, sub, log, frames))

    if not aborted:
        poses.append(snapshot("center_final", sub, log, frames))

    # --- analysis ---
    print("\n=== MISSION REPORT ===")
    e_end = latest_enc(log)
    print("encoder: start {} -> end {} (net {:+.0f} ticks = {:+.2f} deg "
          "at {:.0f} ticks/deg)".format(
              int(e_start), int(e_end), e_end - e_start,
              (e_end - e_start) / TICKS_PER_DEG, TICKS_PER_DEG))
    print("pose table:")
    for p in poses:
        print("  {:>12}: enc {:>7.0f} color {:>4.0f} sonar {:>3.0f} "
              "blob_x {} blob_raw {}".format(
                  p["label"], p["enc"], p["color_med"], p["sonar_med"],
                  "{:.0f}".format(p["blob_x"]) if p["blob_x"] else "-",
                  "{:.0f}".format(p["blob_raw"]) if p["blob_raw"] else "-"))
    if not aborted:
        drift = e_end - e_start
        print("return accuracy: {} ticks ({:+.2f} deg) off the start "
              "position".format(int(drift), drift / TICKS_PER_DEG))
        c0, cf = poses[0], poses[-1]
        print("center color: start {:.0f} -> final {:.0f}; sonar start "
              "{:.0f} -> final {:.0f}".format(
                  c0["color_med"], cf["color_med"],
                  c0["sonar_med"], cf["sonar_med"]))
        if cf["blob_x"] is not None:
            print("obstacle blob at final: x={:.0f} (320=centered) raw={:.0f}"
                  .format(cf["blob_x"], cf["blob_raw"]))
        else:
            print("obstacle blob NOT seen at the final pose - obstacle "
                  "moved/removed or kinect degraded")

    csv_path = os.path.join(OUT_DIR, "swing90_full.csv")
    with open(csv_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "encoder", "color", "sonar"])
        for row in log:
            wr.writerow([round(row[0], 3), int(row[1]), int(row[2]),
                         int(row[3])])
    print("CSV saved:", csv_path, "| aborted:", aborted)

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
