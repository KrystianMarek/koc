#!/usr/bin/env python3
"""
Turret rotation probe - rotates the Kinect turret and verifies it via telemetry.

1. Handshake to robot:5556 (idempotent if hardware already started)
2. Subscribe to :5559, capture baseline turret encoder angle + a frame
3. PUSH TurretRight(SPEED) to :5560 at ~10 Hz for SECONDS, then TurretReset
4. Track the turret encoder angle from telemetry during rotation
5. Save before/after frames and report the encoder delta + frame difference

Usage:
    .venv/bin/python testing/turret_rotate_probe.py [robot_ip] [speed] [seconds]
"""
import os
import sys
import time

import numpy as np
import zmq
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.common.serialization import compress, decompress
from app.networking import (
    HeartbeatRequest, KinectPacket, TelemetryPacket, TurretRight, TurretReset)

ROBOT_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.10.187"
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 80
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    ctx = zmq.Context()

    # --- Handshake (harmless if hardware already running) ---
    req = ctx.socket(zmq.REQ)
    req.setsockopt(zmq.LINGER, 0)
    req.setsockopt(zmq.RCVTIMEO, 8000)
    req.connect("tcp://{}:5556".format(ROBOT_IP))
    req.send(compress(HeartbeatRequest(sequence=0, running=True, network={}, sleep=1.0)))
    try:
        response = decompress(req.recv())
        print("handshake ok: {} (seq {})".format(type(response).__name__, response.sequence))
    except zmq.Again:
        sys.exit("no handshake response - is the server running?")
    req.close()

    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://{}:5559".format(ROBOT_IP))
    sub.setsockopt(zmq.SUBSCRIBE, b"")
    sub.setsockopt(zmq.RCVTIMEO, 3000)

    push = ctx.socket(zmq.PUSH)
    push.connect("tcp://{}:5560".format(ROBOT_IP))

    # --- Baseline: turret angle + one frame ---
    print("capturing baseline angle + frame ...")
    base_angle = None
    before_frame = None
    deadline = time.time() + 8
    while time.time() < deadline and (base_angle is None or before_frame is None):
        try:
            packet = decompress(sub.recv())
        except zmq.Again:
            continue
        if isinstance(packet, TelemetryPacket):
            base_angle = packet.turret_motor.angle
        elif isinstance(packet, KinectPacket) and before_frame is None:
            before_frame = np.asarray(packet.get_video_frame())
    if base_angle is None:
        sys.exit("no telemetry received - BrickPi not started?")
    print("baseline turret encoder: {}".format(base_angle))

    # --- Rotate ---
    # NOTE: the server applies a deadman - BrickPiWrapper re-sends zero speeds
    # after ~3 command-less cycles (~0.3 s, COMMAND_QUEUE_GRACE=3 @ 0.1 s).
    # A single command only twitches the turret; stream commands at ~10 Hz.
    print("rotating: TurretRight({}) streamed for {} s ...".format(SPEED, SECONDS))
    lo = hi = last = base_angle
    end = time.time() + SECONDS
    next_send = 0.0
    sent = 0
    while True:
        now = time.time()
        if now >= end:
            break
        if now >= next_send:
            push.send(compress(TurretRight(SPEED)))
            sent += 1
            next_send = now + 0.1
        try:
            packet = decompress(sub.recv(zmq.NOBLOCK))
        except zmq.Again:
            time.sleep(0.01)
            continue
        if isinstance(packet, TelemetryPacket):
            last = packet.turret_motor.angle
            lo, hi = min(lo, last), max(hi, last)
    print("streamed {} TurretRight packets".format(sent))

    push.send(compress(TurretReset()))
    print("turret stopped (TurretReset sent)")

    # --- Settle + after frame ---
    after_frame = None
    final_angle = last
    deadline = time.time() + 5
    while time.time() < deadline and after_frame is None:
        try:
            packet = decompress(sub.recv())
        except zmq.Again:
            continue
        if isinstance(packet, TelemetryPacket):
            final_angle = packet.turret_motor.angle
        elif isinstance(packet, KinectPacket) and after_frame is None:
            after_frame = np.asarray(packet.get_video_frame())

    # --- Report ---
    print("encoder: baseline={} during=[{} .. {}] (span {}) final={}".format(
        base_angle, lo, hi, hi - lo, final_angle))
    print("net rotation: {:+d} ticks".format(final_angle - base_angle))

    before_path = os.path.join(OUT_DIR, "turret_before.png")
    after_path = os.path.join(OUT_DIR, "turret_after.png")
    Image.fromarray(before_frame).save(before_path)
    Image.fromarray(after_frame).save(after_path)
    diff = np.mean(np.abs(after_frame.astype(float) - before_frame.astype(float)))
    print("saved {} + {}".format(before_path, after_path))
    print("frame difference (mean abs, 0=identical): {:.1f}".format(diff))

    sub.close()
    push.close()
    ctx.term()


if __name__ == "__main__":
    main()
