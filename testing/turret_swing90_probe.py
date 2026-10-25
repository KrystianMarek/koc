#!/usr/bin/env python3
"""
90-degree turret swing reliability probe (repeat run) - ON the robot.

Same mission as the 2026-10-25 first run (LEFT 90 -> RIGHT 180 -> LEFT 90,
encoder-driven legs, stall abort) with three upgrades for verification:

1. **Blob-driven recenter**: small right steps until the obstacle blob
   crosses the image center (x<=320) - finer than the previous 150-tick
   band that left the turret slightly off center.
2. **Per-frame blob logging** during the whole run: the blob-x vs encoder
   slope gives an independent cross-check of the 125 ticks/deg ratio
   (parallax-aware: the slope depends on the target depth, reported
   alongside the blob's own raw distance).
3. **Side-by-side comparison** against the previous run's measured values
   (return 6 ticks, color 768/768, blob x=335, sonar 75).

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
# Stream at the wrapper's consumption rate (~1 cmd per 0.3 s cycle): faster
# streaming backs up the 100-deep command queue and the backlog keeps
# executing after the reset (the 1641-tick overshoot of run 1).
STREAM_PERIOD = 0.3
SETTLE_S = 1.5
TICKS_PER_S = 5.12 * SPEED              # nominal; observed non-linear
OUT_DIR = "/tmp/koc_calib"

# previous run (2026-10-25, first clean run) for the side-by-side
PREV = {"return_ticks": 6, "color_center0": 768, "color_final": 768,
        "blob_x_final": 335, "blob_raw_final": 665, "sonar": 75,
        "recenter_right_approach": 271}

push = None
blob_log = []   # (t, encoder_at_frame, blob_x, blob_raw)


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


def blob(depth):
    """Nearest-valid cluster: (centroid_x, raw_median) or None."""
    valid = (depth >= 300) & (depth <= 1008)
    if not valid.any():
        return None
    vals = depth[valid]
    thresh = np.percentile(vals, 10)
    mask = valid & (depth <= thresh + 5)
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return None
    return float(xs.mean()), float(np.median(depth[mask]))


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
            depth = np.asarray(packet.get_depth())
            frames.append((time.time(), depth))
            b = blob(depth)
            if b is not None:
                blob_log.append((time.time(), latest_enc(log), b[0], b[1]))


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


def enc_around(log, t0, t1):
    arr = np.array([(l[0], l[1]) for l in log], dtype=float)
    return (float(arr[np.argmin(np.abs(arr[:, 0] - t0)), 1]),
            float(arr[np.argmin(np.abs(arr[:, 0] - t1)), 1]))


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

    print("baseline 3 s...")
    pump(sub, 3.0, log, frames)
    e_start = latest_enc(log)

    # --- blob-driven recenter: right steps until the blob crosses x=320 ---
    # (approaching center from the left side, matching the run-2 geometry)
    print("\nblob-driven recenter (right steps, stop at blob x<=320)...")
    for i in range(24):
        depth = latest_depth(frames, time.time() - 2.0)
        st = depth_stats(depth) if depth is not None else None
        b = blob(depth) if depth is not None else None
        if b is not None and b[0] <= 320.0:
            print("  recentered: blob x={:.0f} at encoder {}".format(
                b[0], int(latest_enc(log))))
            break
        pump(sub, 0.3, log, frames, stream=TurretRight(25))
        push.send(compress(TurretReset()))
        time.sleep(0.35)
    else:
        print("  recenter: blob never crossed x=320 in 24 steps - "
              "continuing anyway")

    poses = [snapshot("center0", sub, log, frames)]
    e_start = latest_enc(log)
    print("start encoder: {}".format(int(e_start)))

    legs = [("left 90", TurretLeft(SPEED), TARGET_TICKS),
            ("right 180", TurretRight(SPEED), 2 * TARGET_TICKS),
            ("left 90 home", TurretLeft(SPEED), TARGET_TICKS)]

    aborted = False
    for name, cmd, target in legs:
        print("\nleg {} (target {} ticks)...".format(name, target))
        achieved, stalled = swing(sub, log, frames, cmd, target, name)
        if stalled or achieved < 0.85 * target:
            print("\n!!! LEG UNDERSHOOT {:.0f}% - mechanical limit or stall."
                  " ABORTING MISSION (turret stays put; motors zeroed)".format(
                      100.0 * achieved / target))
            aborted = True
            break
        poses.append(snapshot(name.replace(" ", ""), sub, log, frames))

    if not aborted:
        poses.append(snapshot("center_final", sub, log, frames))

    # --- analysis ---
    print("\n=== MISSION REPORT ===")
    e_end = latest_enc(log)
    print("encoder: start {} -> end {} (net {:+.0f} ticks = {:+.2f} deg "
          "at {:.0f} ticks/deg)".format(
              int(e_start), int(e_end), e_end - e_start,
              (e_end - e_start) / TICKS_PER_DEG, TICKS_PER_DEG))
    print("pose table (vs previous run in brackets):")
    prev_poses = {"center0": (494, 768), "left90": (11750, 763),
                  "right180": (-10857, 734), "left90home": (500, 768),
                  "center_final": (500, 768)}
    for p in poses:
        pv = prev_poses.get(p["label"], ("-", "-"))
        print("  {:>12}: enc {:>7.0f} [prev {:>7}] color {:>4.0f} "
              "[prev {:>4}] sonar {:.0f} blob_x {} "
              "[prev {}]".format(
                  p["label"], p["enc"], pv[0], p["color_med"], pv[1],
                  p["sonar_med"],
                  "{:.0f}".format(p["blob_x"]) if p["blob_x"] else "-",
                  pv[1] if p["label"] == "center_final"
                  else {"center0": 333, "left90": 139, "right180": 438,
                        "left90home": 335}.get(p["label"], "-")))
    if not aborted:
        drift = e_end - e_start
        c0, cf = poses[0], poses[-1]
        print("return accuracy: {} ticks ({:+.2f} deg) [previous run: "
              "+6 ticks]".format(int(drift), drift / TICKS_PER_DEG))
        print("center color: start {:.0f} -> final {:.0f} [prev 768 -> 768]"
              .format(c0["color_med"], cf["color_med"]))
        if cf["blob_x"] is not None:
            print("obstacle blob at final: x={:.0f} [prev 335] raw={:.0f} "
                  "[prev 665]".format(cf["blob_x"], cf["blob_raw"]))

    # --- ratio cross-check from the per-frame blob slope ---
    print("\n=== RATIO CROSS-CHECK (blob_x vs encoder slope) ===")
    if len(blob_log) > 50:
        arr = np.array(blob_log, dtype=float)
        # obstacle frames: blob raw 550..700 (~0.7-0.8 m) near center-ish
        sel = arr[(arr[:, 3] >= 550) & (arr[:, 3] <= 700) &
                  (arr[:, 2] > 60) & (arr[:, 2] < 580)]
        print("obstacle frames: {} of {}".format(len(sel), len(arr)))
        if len(sel) > 20:
            enc, cx = sel[:, 1], sel[:, 2]
            slope, intercept = np.polyfit(enc, cx, 1)
            print("slope: {:.4f} px/tick (corr px per tick)".format(slope))
            # rotation-only expectation at fx=594: 10.37 px/deg / 125 t/deg
            # = 0.0830 px/tick; near-field parallax multiplies by
            # (1 + d_cam/depth) with the blob's own depth measured:
            raw_med = float(np.median(sel[:, 3]))
            depth_m = 0.1236 * np.tan(raw_med / 2842.5 + 1.1863)
            print("blob depth: {:.2f} m (parallax factor = 1 + d_cam/"
                  "{:.2f})".format(depth_m, depth_m))
            print("implied ticks/deg if d_cam=0: {:.1f}; the difference "
                  "from 125 estimates the camera-axis offset".format(
                      abs(1.0 / slope) * 180.0 / np.pi))
        else:
            print("not enough obstacle frames for a slope fit")
    else:
        print("blob log too sparse")

    csv_path = os.path.join(OUT_DIR, "swing90_repeat.csv")
    with open(csv_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "encoder", "color", "sonar"])
        for row in log:
            wr.writerow([round(row[0], 3), int(row[1]), int(row[2]),
                         int(row[3])])
    blob_path = os.path.join(OUT_DIR, "swing90_blobs.csv")
    with open(blob_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "encoder", "blob_x", "blob_raw"])
        for row in blob_log:
            wr.writerow([round(row[0], 3), int(row[1]), round(row[2], 1),
                         round(row[3], 0)])
    print("CSV saved:", csv_path, "+", blob_path, "| aborted:", aborted)

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
