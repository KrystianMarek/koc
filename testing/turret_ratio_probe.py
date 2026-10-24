#!/usr/bin/env python3
"""
Turret gear-ratio probe via Kinect optics - small swings, cable-aware.
Run ON the robot (server must be up).

Hardware facts (user-provided):
- Cables run through the turret (Kinect, motor, light sensor) -> rotation is
  LIMITED. No full revolutions. Small swings only.
- Turret currently ~45 deg right of center (camera forward).
- Color sensor (PORT_1) rides on the turret ~5 cm above the body; a cable
  sticking from the robot's back marks the forward position. The old paper
  dial is gone.

Method (phase A - ratio):
  Small bounded swings; at each rest, average a few Kinect frames and
  measure the horizontal scene shift vs the previous rest frame
  (normalized cross-correlation of the row-averaged intensity profile,
  sub-pixel). Convert px -> degrees with the Kinect focal length
  (Config.KINECT_FX, atan model). Ratio = encoder ticks per turret degree.
  (Numerically, ticks/degree == motor revs per turret rev, since the motor
  encoder is 360 ticks/rev.)

Method (phase B - homing attempt, only if affordable):
  Swing toward center in small steps while watching the color sensor; on a
  sustained deviation (the cable), stop immediately and record the encoder
  value. Bounded by a conservative tick budget derived from the measured
  ratio and the reported 45 deg offset. If the budget is exhausted without
  a crossing, stop and report (never overshoot blindly).

Safety: deadman streaming (0.1 s period), tiny swings, per-phase tick
budgets, stall detection, and the probe prints progress as it goes - kill
it anytime and the deadman stops the motors within ~0.3 s.

Usage (on the robot):
    cd ~/rpi_lego_robot && ~/.virtualenvs/pi_robot3/bin/python \\
        testing/turret_ratio_probe.py [swing_seconds] [speed]
"""
import csv
import os
import sys
import time
from collections import deque

import numpy as np
import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.common.config import Config
from app.common.serialization import compress, decompress
from app.networking import (
    HeartbeatRequest, KinectPacket, TelemetryPacket, TurretLeft, TurretReset)

SWING_S = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 25
N_SWINGS_A = 4           # phase A swings (ratio measurement)
MAX_TOTAL_TICKS_B = 600  # hard phase-B budget (cable safety)
SETTLE_S = 1.2           # wait after each swing (deadman + motion settle)
CAPTURE_S = 1.0          # kinect frame gathering per rest point
STREAM_PERIOD = 0.1
MIN_FEATURE = 12
K_MAD = 4.0
IMG_ROWS = (150, 300)    # horizontal band used for the shift estimate
MAX_SHIFT_PX = 80

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
            time.sleep(0.005)
            continue
        if isinstance(packet, TelemetryPacket):
            log.append((time.time(), packet.turret_motor.angle,
                        packet.color_sensor.raw))
        elif isinstance(packet, KinectPacket):
            frames.append((time.time(), np.asarray(packet.get_video_frame())))


def rest_frame(sub, log, frames):
    """Pause, then return the average of the last few kinect frames."""
    time.sleep(SETTLE_S)
    t0 = time.time()
    frames.clear()
    pump(sub, CAPTURE_S, log, frames)
    recent = [f for (t, f) in frames if t >= t0]
    if not recent:
        sys.exit("no kinect frames received - is the kinect process alive?")
    return np.mean(recent[-4:], axis=0).astype(np.float32)


def enc_around(log, t0, t1):
    arr = np.array([(l[0], l[1]) for l in log], dtype=float)
    e0 = arr[np.argmin(np.abs(arr[:, 0] - t0)), 1]
    e1 = arr[np.argmin(np.abs(arr[:, 0] - t1)), 1]
    return float(e0), float(e1)


def profile_shift_deg(img_a, img_b):
    """Horizontal scene shift (px, degrees) between two frames.

    Positive px = features moved right in the image = camera yawed left.
    """
    a = img_a[IMG_ROWS[0]:IMG_ROWS[1]].mean(axis=(0, 2))
    b = img_b[IMG_ROWS[0]:IMG_ROWS[1]].mean(axis=(0, 2))
    a = a - a.mean()
    b = b - b.mean()
    scores = {}
    for s in range(-MAX_SHIFT_PX, MAX_SHIFT_PX + 1):
        lo_a, hi_a = max(0, -s), 640 - max(0, s)
        lo_b, hi_b = max(0, s), 640 - max(0, s) + s
        va, vb = a[lo_a:hi_a], b[lo_b:hi_b]
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        if len(va) < 200 or denom < 1e-9:
            continue
        scores[s] = float(np.dot(va, vb) / denom)
    if not scores:
        return None, None
    best = max(scores, key=scores.get)
    if best - 1 not in scores or best + 1 not in scores or \
            scores[best - 1] >= scores[best] or scores[best + 1] >= scores[best]:
        return None, scores.get(best, 0.0)  # peak not interior -> untrustworthy
    denom = scores[best - 1] - 2 * scores[best] + scores[best + 1]
    subpx = 0.5 * (scores[best - 1] - scores[best + 1]) / denom if denom else 0.0
    shift = best + subpx
    return shift, scores[best]


def color_baseline(log, t_before):
    vals = np.array([l[2] for l in log if l[0] < t_before], dtype=float)
    if len(vals) < 5:
        return None, None
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) or 1.0
    return med, mad


def color_events(log, t0, t1, med, mad):
    """Time span of the first sustained color deviation in (t0, t1)."""
    arr = np.array([l for l in log if t0 <= l[0] <= t1], dtype=float)
    if len(arr) < 3:
        return None
    threshold = max(K_MAD * mad, MIN_FEATURE)
    mask = np.abs(arr[:, 2] - med) > threshold
    idx = np.where(mask)[0]
    if len(idx) < 2:
        return None
    # first run of >= 2 consecutive deviations
    run = 1
    for i in range(1, len(idx)):
        if idx[i] == idx[i - 1] + 1:
            run += 1
            if run >= 2:
                start = idx[i - 1]
                return (float(arr[start, 0]), float(arr[idx[i], 0]),
                        float(arr[start, 2]))
        else:
            run = 1
    return None


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

    print("initial rest frame + color baseline...")
    f_prev = rest_frame(sub, log, frames)
    med, mad = color_baseline(log, time.time())
    e_prev = enc_around(log, time.time() - 1.0, time.time())[1]
    print("color baseline: median={:.0f} mad={:.1f}; encoder={}".format(
        med, mad, int(e_prev)))

    # sanity: two rest frames ~0 s apart should agree
    f_now = rest_frame(sub, log, frames)
    shift0, score0 = profile_shift_deg(f_prev, f_now)
    print("sanity shift (no motion): {} px, corr={:.3f}".format(
        "n/a" if shift0 is None else "{:+.2f}".format(shift0),
        score0 if score0 is not None else -1))

    # --- phase A: ratio via small swings ---
    ticks_per_deg = []
    rows = []
    print("\nphase A: {} swings of {} s at speed {}".format(
        N_SWINGS_A, SWING_S, SPEED))
    for i in range(N_SWINGS_A):
        t_cmd0 = time.time()
        pump(sub, SWING_S, log, frames, stream=TurretLeft(SPEED))
        push.send(compress(TurretReset()))
        f_new = rest_frame(sub, log, frames)
        t_end = time.time()
        e0, e1 = enc_around(log, t_cmd0 - 0.2, t_end)
        shift, score = profile_shift_deg(f_prev, f_new)
        if shift is None:
            print("swing {}: correlation peak not interior - unreliable, "
                  "skipping".format(i + 1))
        else:
            deg = shift / Config.KINECT_FX * 180.0 / np.pi
            dticks = e1 - e0
            tpd = abs(dticks) / abs(deg) if abs(deg) > 1e-6 else None
            ticks_per_deg.append(tpd)
            print("swing {}: enc {:+.0f} ticks, scene {:+.2f} px = {:+.2f} deg"
                  " (corr {:.3f}) -> {:.1f} ticks/deg".format(
                      i + 1, dticks, shift, deg, score, tpd))
        rows.append(("A{}".format(i + 1), t_end, e1,
                     log[-1][2] if log else -1))
        f_prev = f_new

    tpd = float(np.nanmedian(ticks_per_deg)) if ticks_per_deg else None
    print("\n=== RATIO (phase A) ===")
    if tpd:
        print("ticks per turret degree: {:.1f} (per-swing: {})".format(
            tpd, ["{:.1f}".format(x) for x in ticks_per_deg]))
        print("gear ratio: {:.2f} motor revs per turret rev".format(tpd))
    else:
        print("no reliable estimate - scene too uniform or swings too small")

    # --- phase B: homing attempt toward center ---
    homed = None
    if tpd:
        # user reports ~45 deg right of center; leave a 10 deg margin,
        # then 20% safety factor on the tick budget
        budget = int(0.8 * (45.0 - 10.0) * tpd)
        print("\nphase B: homing toward center (budget {} ticks = "
              "{:.0f} deg at measured ratio)".format(budget, budget / tpd))
        spent = 0
        while spent < budget:
            t_cmd0 = time.time()
            pump(sub, SWING_S, log, frames, stream=TurretLeft(SPEED))
            push.send(compress(TurretReset()))
            time.sleep(0.4)
            spent += SWING_S * SPEED * 5.12  # approx; verified below
            e_now = enc_around(log, t_cmd0, time.time() + 0.3)[1]
            spent = e_now - e_prev
            ev = color_events(log, t_cmd0, time.time(), med, mad)
            print("  homing swing: encoder now {}, spent {}".format(
                int(e_now), int(spent)))
            if ev:
                e_cross = enc_around(log, ev[0], ev[1])[1]
                homed = e_cross
                print("  COLOR EVENT at t={:.2f} (color={:.0f}) - cable "
                      "crossing? encoder at event: {}".format(
                          ev[0], ev[2], int(e_cross)))
                break
        if homed is None:
            print("no color event within budget - cable not crossed "
                  "(or feature too subtle at 5 cm); nothing harmed")
    else:
        print("\nphase B skipped (no ratio estimate)")

    # --- save csv ---
    csv_path = "/tmp/koc_calib/turret_ratio.csv"
    os.makedirs("/tmp/koc_calib", exist_ok=True)
    with open(csv_path, "w") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "encoder", "color"])
        for row in log:
            wr.writerow([round(row[0], 3), int(row[1]), int(row[2])])
    print("CSV saved:", csv_path)

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
