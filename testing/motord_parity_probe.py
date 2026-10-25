#!/usr/bin/env python3
"""
motord parity probe - run ON the robot. The Phase-1 differential harness.

Compares the v2 Rust daemon (motord, UDS JSON-RPC) against the v1 oracle
(BrickPi.py direct) on the same bus, same instant-ish:

    python3 testing/motord_parity_probe.py v1        # oracle reads only
    python3 testing/motord_parity_probe.py motord    # daemon snapshots only
    python3 testing/motord_parity_probe.py both      # v1 -> release -> motord

'both' stops motord (SIGTERM, motors float), runs N oracle exchanges, then
starts motord and takes M snapshots, printing side-by-side values. Encoders
are cumulative so the ABSOLUTE values carry over (the BrickPi holds state
while powered); sensors are instantaneous.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SOCK = "/tmp/motord.sock"
MOTORD_BIN = os.path.expanduser(
    "~/rpi_lego_robot/robot/target/release/motord")
CTL_BIN = os.path.expanduser(
    "~/rpi_lego_robot/robot/target/release/robotctl")
N = 5


def oracle_reads():
    """Direct BrickPi.py: setup + N exchanges, print encoders/sensors."""
    import BrickPi  # the v1 oracle (venv site-packages)
    BrickPi.BrickPi.Address = [1, 2]
    BrickPi.BrickPi.SensorType = [
        BrickPi.TYPE_SENSOR_LIGHT_ON, 0, 0, BrickPi.TYPE_SENSOR_ULTRASONIC_CONT]
    BrickPi.BrickPi.Timeout = 300
    BrickPi.BrickPiSetup()
    BrickPi.BrickPiSetupSensors()
    BrickPi.BrickPiSetTimeout()
    for i in range(N):
        BrickPi.BrickPiUpdateValues()
        print("oracle[{}]: enc A={} B={} C={} D={} | color={} sonar={}".format(
            i,
            BrickPi.BrickPi.Encoder[0], BrickPi.BrickPi.Encoder[1],
            BrickPi.BrickPi.Encoder[2], BrickPi.BrickPi.Encoder[3],
            BrickPi.BrickPi.Sensor[0], BrickPi.BrickPi.Sensor[3]))
        time.sleep(0.05)


def rpc(method, params="{}"):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK)
    s.sendall(json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": json.loads(params)}
    ).encode() + b"\n")
    buf = s.makefile().readline()
    s.close()
    return json.loads(buf)


def motord_running():
    return os.path.exists(SOCK)


def stop_motord():
    out = subprocess.run(["pgrep", "-f", "target/release/motord"],
                         stdout=subprocess.PIPE).stdout.decode().split()
    for pid in out:
        os.kill(int(pid), signal.SIGTERM)
    if out:
        time.sleep(1.5)
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    print("motord stopped" if out else "motord was not running")


def start_motord():
    if os.path.exists(SOCK):
        os.unlink(SOCK)  # stale socket after SIGKILL
    subprocess.Popen(["nohup", MOTORD_BIN, SOCK, "/dev/ttyS0", "60"],
                     stdout=open("/tmp/motord.log", "a"), stderr=subprocess.STDOUT)
    for _ in range(40):
        if motord_running():
            time.sleep(1.0)
            return True
        time.sleep(0.25)
    return False


def motord_snapshots():
    for i in range(N):
        r = rpc("snapshot")
        res = r.get("result", r)
        e = res.get("encoders", {})
        print("motord[{}]: enc A={} B={} C={} D={} | color={} sonar={} errors={} loops={}".format(
            i, e.get("A"), e.get("B"), e.get("C"), e.get("D"),
            res.get("color_raw"), res.get("sonar_raw"),
            res.get("errors"), res.get("loops")))
        time.sleep(0.05)


def v1_twitch(speed=51, seconds=1.0):
    """Drive A+D at `speed` via BrickPi.py directly for `seconds`, then stop."""
    import BrickPi
    BrickPi.BrickPiSetup()
    BrickPi.BrickPi.MotorEnable[0] = 1
    BrickPi.BrickPi.MotorEnable[3] = 1
    BrickPi.BrickPiSetupSensors()
    t0 = time.time()
    while time.time() - t0 < seconds:
        BrickPi.BrickPi.MotorSpeed[0] = speed
        BrickPi.BrickPi.MotorSpeed[3] = speed
        BrickPi.BrickPiUpdateValues()
        time.sleep(0.05)
    BrickPi.BrickPi.MotorSpeed[0] = 0
    BrickPi.BrickPi.MotorSpeed[3] = 0
    BrickPi.BrickPiUpdateValues()


def _oracle_encoders():
    """Encoder snapshot via the oracle. MUST configure the same sensor types
    as motord does - the firmware's response layout depends on them."""
    import BrickPi
    BrickPi.BrickPiSetup()  # (re)open the UART - motord may have held it at import
    BrickPi.BrickPi.SensorType = [
        BrickPi.TYPE_SENSOR_LIGHT_ON, 0, 0, BrickPi.TYPE_SENSOR_ULTRASONIC_CONT]
    BrickPi.BrickPiSetupSensors()
    BrickPi.BrickPiUpdateValues()
    return dict(A=BrickPi.BrickPi.Encoder[0], B=BrickPi.BrickPi.Encoder[1],
                C=BrickPi.BrickPi.Encoder[2], D=BrickPi.BrickPi.Encoder[3])


def motion_parity():
    """Twitch via motord, twitch via v1 oracle, compare deltas. ~4 mm each."""
    if not motord_running() and not start_motord():
        sys.exit("motord failed to start")
    e0 = _oracle_encoders()
    t0 = time.time()
    while time.time() - t0 < 1.0:
        rpc("drive", '{"left":20,"right":20}')
        time.sleep(0.1)
    rpc("drive", '{"left":0,"right":0}')
    time.sleep(0.5)
    e1 = _oracle_encoders()
    print("motord twitch deltas: dA={} dD={} ({:.1f}s)".format(
        e1["A"] - e0["A"], e1["D"] - e0["D"], time.time() - t0))

    stop_motord()
    e2 = _oracle_encoders()
    v1_twitch(51, 1.0)
    e3 = _oracle_encoders()
    print("v1     twitch deltas: dA={} dD={}".format(
        e3["A"] - e2["A"], e3["D"] - e2["D"]))

    # Deadman: drive, SIGKILL mid-motion, verify the robot stops within ~0.3s.
    if not start_motord():
        sys.exit("motord failed to start")
    e4 = _oracle_encoders()
    t1 = time.time()
    while time.time() - t1 < 0.3:
        rpc("drive", '{"left":20,"right":20}')
        time.sleep(0.08)
    out = subprocess.run(["pgrep", "-x", "motord"], stdout=subprocess.PIPE).stdout.decode().split()
    for pid in out:
        os.kill(int(pid), signal.SIGKILL)
    print("motord SIGKILLed mid-drive")
    time.sleep(1.5)
    e5 = _oracle_encoders()
    print("deadman deltas after SIGKILL: dA={} dD={} (must be small, <100)".format(
        e5["A"] - e4["A"], e5["D"] - e4["D"]))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    if mode == "motion":
        motion_parity()
        return
    if mode in ("v1", "both"):
        if mode == "both" and motord_running():
            stop_motord()
        oracle_reads()
    if mode in ("motord", "both"):
        if mode == "both" or not motord_running():
            if not start_motord():
                sys.exit("motord failed to start")
        motord_snapshots()


if __name__ == "__main__":
    main()
