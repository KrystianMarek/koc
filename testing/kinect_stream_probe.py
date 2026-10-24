#!/usr/bin/env python3
"""
Kinect stream probe - headless client for a running K.O.C server.

1. REQ handshake to robot:5556 (first connect triggers BrickPi/Kinect startup)
2. SUB to robot:5559 and collect the first TelemetryPacket and KinectPacket
3. Save the RGB frame and depth map as PNGs, print a short report

No PyQt5 needed - useful for verifying the server end-to-end from a machine
without a display.

Usage:
    .venv/bin/python testing/kinect_stream_probe.py [robot_ip]
"""
import os
import sys
import time

import numpy as np
import zmq

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False  # robot venv has no PIL; frame saving skipped

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.common.serialization import compress, decompress
from app.networking import HeartbeatRequest, KinectPacket, TelemetryPacket

ROBOT_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.10.187"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    ctx = zmq.Context()

    # --- 1. Handshake (starts hardware on the robot on first connect) ---
    req = ctx.socket(zmq.REQ)
    req.setsockopt(zmq.LINGER, 0)
    req.setsockopt(zmq.RCVTIMEO, 8000)
    req.connect("tcp://{}:5556".format(ROBOT_IP))
    print("handshake -> {}".format(ROBOT_IP))
    req.send(compress(HeartbeatRequest(
        sequence=0, running=True, network={}, sleep=1.0)))
    try:
        response = decompress(req.recv())
    except zmq.Again:
        sys.exit("no handshake response from {} - is the server running?".format(ROBOT_IP))
    print("handshake ok: {} (seq {})".format(type(response).__name__, response.sequence))
    req.close()

    # --- 2. Subscribe to the telemetry stream ---
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://{}:5559".format(ROBOT_IP))
    sub.setsockopt(zmq.SUBSCRIBE, b"")
    sub.setsockopt(zmq.RCVTIMEO, 5000)

    print("waiting for telemetry + kinect packets on :5559 ...")
    telemetry = None
    kinect = None
    kinect_fps_counter = 0
    deadline = time.time() + 30
    while time.time() < deadline and (telemetry is None or kinect is None):
        try:
            packet = decompress(sub.recv())
        except zmq.Again:
            continue
        if isinstance(packet, TelemetryPacket) and telemetry is None:
            telemetry = packet
            print("  first TelemetryPacket received")
        elif isinstance(packet, KinectPacket) and kinect is None:
            kinect = packet
            print("  first KinectPacket received")
        elif isinstance(packet, KinectPacket):
            kinect_fps_counter += 1

    if telemetry is None and kinect is None:
        sys.exit("no packets within 30 s")

    # --- 3. Report + save frames ---
    if telemetry is not None:
        stats = telemetry.system_stats
        print("telemetry: seq={} voltage={}V temp={}C".format(
            telemetry.sequence, telemetry.voltage, telemetry.temperature))
        print("  motors: left {}/{} right {}/{} turret {}/{} (speed/desired)".format(
            telemetry.left_motor.speed, telemetry.left_motor.desired_speed,
            telemetry.right_motor.speed, telemetry.right_motor.desired_speed,
            telemetry.turret_motor.speed, telemetry.turret_motor.desired_speed))
        print("  system: cpu={}%, ram={}%, net sent={}B".format(
            stats.cpu_percent, stats.ram_percent, stats.net_bytes_sent))
        print("  sensors: ultrasound={}, color={}".format(
            telemetry.ultrasound_sensor.raw, telemetry.color_sensor.raw))

    if kinect is not None:
        video = np.asarray(kinect.get_video_frame())
        depth = np.asarray(kinect.get_depth())
        print("kinect seq={}: video {} {}, depth {} {} (raw min {} / max {})".format(
            kinect.sequence, video.shape, video.dtype,
            depth.shape, depth.dtype, depth.min(), depth.max()))

        rgb_path = os.path.join(OUT_DIR, "kinect_rgb.png")
        if HAVE_PIL:
            Image.fromarray(video).save(rgb_path)
            print("saved", rgb_path)

        # Display conversion per Config.DEPTH_DISPLAY_BITS: clip to 10 bits, >> 2
        depth_8bit = (np.clip(depth, 0, 2**10 - 1) >> 2).astype(np.uint8)
        depth_path = os.path.join(OUT_DIR, "kinect_depth.png")
        if HAVE_PIL:
            Image.fromarray(depth_8bit).save(depth_path)
            print("saved", depth_path)
        print("(received {} further kinect frames while waiting)".format(kinect_fps_counter))
    else:
        print("no KinectPacket - check robot log: tail /tmp/koc_server.log")

    sub.close()
    ctx.term()


if __name__ == "__main__":
    main()
