#!/usr/bin/env python3
"""
kinect_bearing.py - run ON the robot with the v1 server up (motord stopped).

    python3 testing/kinect_bearing.py [sonar_cm]

Finds the obstacle's horizontal bearing in the Kinect depth image:

1. Per column, the median valid depth over a central row band, in metres,
   then the median of that profile across ~10 s of frames.
2. Obstacle columns: within +-0.12 m of the reference range - the sonar
   reading when given (chassis-fixed, so it is the obstacle straight ahead
   of the body), otherwise the nearest column.
3. The largest contiguous run of obstacle columns (gaps <= 4 px bridged).

The reading is UNTRUSTED when the run touches the frame edge (the obstacle
is partly out of view, so its centre is unknown) or is narrower than 10 px.

Bearing: atan((x - 320) / 585). x > 320 means the obstacle is right of the
image centre. The image's handedness is not assumed: verify it with a small
known turret step before trusting the sign.
"""
import sys
import time
import warnings

import numpy as np
import zmq

sys.path.insert(0, "/home/pi/rpi_lego_robot")

from app.common.serialization import compress, decompress
from app.networking import HeartbeatRequest, KinectPacket

TAN_SCALE, TAN_OFFSET = 2842.5, 1.1863
VALID_MIN, VALID_MAX = 300, 1008
ROW_BAND = (160, 320)
FX = 585.0
CENTER_X = 320.0
SAMPLE_S = 10.0
BAND_M = 0.12
GAP_PX = 4
EDGE_PX = 8
MIN_WIDTH_PX = 10


def column_profile(depth):
    """Per-column median valid depth (metres) over ROW_BAND; NaN if sparse."""
    band = depth[ROW_BAND[0]:ROW_BAND[1], :].astype(np.float64)
    band[(band < VALID_MIN) | (band > VALID_MAX)] = np.nan
    enough = np.sum(~np.isnan(band), axis=0) >= 0.2 * band.shape[0]
    raw = np.full(band.shape[1], np.nan)
    if enough.any():
        raw[enough] = np.nanmedian(band[:, enough], axis=0)
    return 0.1236 * np.tan(raw / TAN_SCALE + TAN_OFFSET)


def runs(mask):
    """Contiguous True runs as (start, end) inclusive, bridging small gaps."""
    out = []
    start = None
    gap = 0
    for i, m in enumerate(mask):
        if m:
            if start is None:
                start = i
            gap = 0
            end = i
        elif start is not None:
            gap += 1
            if gap > GAP_PX:
                out.append((start, end))
                start = None
    if start is not None:
        out.append((start, end))
    return out


def capture(seconds):
    ctx = zmq.Context()
    req = ctx.socket(zmq.REQ)
    req.setsockopt(zmq.LINGER, 0)
    req.setsockopt(zmq.RCVTIMEO, 8000)
    req.connect("tcp://127.0.0.1:5556")
    req.send(compress(HeartbeatRequest(sequence=0, running=True, network={}, sleep=1.0)))
    try:
        decompress(req.recv())
    except zmq.Again:
        sys.exit("no handshake response - is the server running?")
    req.close()
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://127.0.0.1:5559")
    sub.setsockopt(zmq.SUBSCRIBE, b"")
    profiles = []
    t0 = time.time()
    while time.time() - t0 < seconds:
        try:
            packet = decompress(sub.recv(zmq.NOBLOCK))
        except zmq.Again:
            time.sleep(0.005)
            continue
        if isinstance(packet, KinectPacket):
            profiles.append(column_profile(np.asarray(packet.get_depth())))
    sub.close()
    ctx.term()
    return profiles


def main():
    warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN columns are expected
    sonar_cm = float(sys.argv[1]) if len(sys.argv) > 1 else None
    profiles = capture(SAMPLE_S)
    if not profiles:
        sys.exit("no Kinect frames")
    prof = np.nanmedian(np.vstack(profiles), axis=0)
    print("frames: {}".format(len(profiles)))
    print("profile (x: metres): " + " ".join(
        "{}:{:.2f}".format(x, prof[x]) if not np.isnan(prof[x]) else "{}:--".format(x)
        for x in range(0, 640, 40)))
    if sonar_cm is not None and 10 <= sonar_cm < 255:
        ref, ref_src = sonar_cm / 100.0, "sonar"
    else:
        ref, ref_src = float(np.nanmin(prof)), "nearest column"
    mask = np.abs(prof - ref) <= BAND_M
    candidates = sorted(runs(mask), key=lambda r: r[1] - r[0], reverse=True)
    print("reference {:.2f} m ({}); candidate runs (start-end px): {}".format(
        ref, ref_src, candidates[:4]))
    if not candidates:
        print("RESULT: no obstacle columns within {:.2f} m of {:.2f} m - obstacle not in view".format(
            BAND_M, ref))
        return
    s, e = candidates[0]
    x = (s + e) / 2.0
    width = e - s + 1
    dist = float(np.nanmedian(prof[s:e + 1]))
    edge = s <= EDGE_PX or e >= 639 - EDGE_PX
    ang = float(np.degrees(np.arctan((x - CENTER_X) / FX)))
    trusted = not edge and width >= MIN_WIDTH_PX
    print("RESULT: x={:.1f} px width={} px dist={:.2f} m bearing={:+.2f} deg ({} of centre) {}".format(
        x, width, dist, ang, "right" if x > CENTER_X else "left",
        "TRUSTED" if trusted else "UNTRUSTED ({})".format(
            "touches frame edge" if edge else "too narrow")))
    # A flat face square to the camera has constant depth across the image;
    # a slope means the camera is yawed against the face's normal.
    cols = np.arange(s, e + 1)
    z = prof[s:e + 1]
    ok = ~np.isnan(z)
    if ok.sum() >= MIN_WIDTH_PX:
        lateral = (cols[ok] - CENTER_X) * z[ok] / FX
        slope = np.polyfit(lateral, z[ok], 1)[0]
        print("SURFACE: yaw {:+.2f} deg vs face normal ({} side nearer)".format(
            float(np.degrees(np.arctan(-slope))), "right" if slope < 0 else "left"))


if __name__ == "__main__":
    main()
