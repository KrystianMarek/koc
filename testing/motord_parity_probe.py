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
import threading
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


class RpcClient:
    """Persistent UDS connection: one connect, many calls (~us each).
    The per-call connect+thread-spawn cost motord ~0.8 s/call, which is
    unusable for the position loops. Thread-safe: the refresh thread and
    the monitor share one client."""

    def __init__(self, path=SOCK):
        self.path = path
        self.sock = None
        self.f = None
        self.lock = threading.Lock()

    def _ensure(self):
        if self.sock is None:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(self.path)
            self.f = self.sock.makefile()

    def call(self, method, params="{}"):
        with self.lock:
            self._ensure()
            self.sock.sendall(json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method,
                 "params": json.loads(params) if isinstance(params, str) else params}
            ).encode() + b"\n")
            return json.loads(self.f.readline())

    def close(self):
        with self.lock:
            if self.sock:
                self.sock.close()
                self.sock = None
                self.f = None


_CLIENT = [None]


def rpc(method, params="{}"):
    if _CLIENT[0] is None:
        _CLIENT[0] = RpcClient()
    try:
        return _CLIENT[0].call(method, params)
    except (socket.error, ValueError, EOFError):
        _CLIENT[0].close()  # motord restarted: reconnect once
        return _CLIENT[0].call(method, params)


def motord_running():
    return os.path.exists(SOCK)


def stop_motord():
    if _CLIENT[0] is not None:
        _CLIENT[0].close()
    out = subprocess.run(["pgrep", "-x", "motord"],
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


def v1_turret_twitch(speed=51, seconds=1.0):
    """Drive the C motor (turret) at `speed` via BrickPi.py, then stop.

    The v1's TurretRight maps to NEGATIVE encoder ticks, so use -speed to
    match the motord's positive-pwm convention sign-for-sign.
    """
    import BrickPi
    BrickPi.BrickPiSetup()
    BrickPi.BrickPi.MotorEnable[2] = 1
    BrickPi.BrickPiSetupSensors()
    t0 = time.time()
    while time.time() - t0 < seconds:
        BrickPi.BrickPi.MotorSpeed[2] = -speed
        BrickPi.BrickPiUpdateValues()
        time.sleep(0.05)
    BrickPi.BrickPi.MotorSpeed[2] = 0
    BrickPi.BrickPiUpdateValues()


def snap_encoders():
    """Encoder dict from motord's own snapshot (safe while motord streams)."""
    return rpc("snapshot")["result"]["encoders"]


def estop_drill():
    """estop latches -> drive rejected -> motors float -> clear_estop restores.
    All encoder reads via motord snapshots (the oracle can't touch the UART
    while motord streams)."""
    if not motord_running() and not start_motord():
        sys.exit("motord failed to start")
    e0 = snap_encoders()
    t0 = time.time()
    while time.time() - t0 < 0.3:
        rpc("drive", '{"left":20,"right":20}')
        time.sleep(0.08)
    r = rpc("estop")
    print("estop:", r.get("result", r))
    err = rpc("drive", '{"left":20,"right":20}')
    print("drive after estop (must be an error):", err.get("error", err))
    time.sleep(1.0)
    e1 = snap_encoders()
    print("estop drift over 1.0s: dA={} dD={} (must be ~0)".format(
        e1["A"] - e0["A"], e1["D"] - e0["D"]))
    rpc("clear_estop")
    r = rpc("drive", '{"left":0,"right":0}')
    print("drive after clear_estop (must be ok):", r.get("result", r))
    return e1  # motord stays running; caller keeps using snapshots


def _turret_encoder():
    """Turret encoder via the ORACLE (only call while motord is stopped)."""
    return _oracle_encoders()["C"]


def turret_parity():
    """Twitch the turret via motord and via the v1 oracle; compare |deltas|."""
    if not motord_running() and not start_motord():
        sys.exit("motord failed to start")
    c0 = snap_encoders()["C"]
    t0 = time.time()
    while time.time() - t0 < 1.0:
        rpc("turret", '{"pct":20}')
        time.sleep(0.1)
    rpc("turret", '{"pct":0}')
    time.sleep(0.5)
    c1 = snap_encoders()["C"]
    print("motord turret twitch: dC={} ({:.1f}s)".format(c1 - c0, time.time() - t0))

    stop_motord()
    c2 = _turret_encoder()
    v1_turret_twitch(51, 1.0)
    c3 = _turret_encoder()
    print("v1     turret twitch: dC={} (motord direction was {}, v1 used -)".format(
        c3 - c2, "+" if c1 > c0 else "-"))
    return c3


def swing90_motord(ticks_per_deg=125.0, speed_pct=32, ccw_first=True):
    """The koc-swing90 mission via motord: relative +-90 deg out and back.

    The turret intent is a velocity; the probe closes the position loop on
    MOTORD'S OWN SNAPSHOT encoder (the UART is motord's while it streams).
    LEG ORDER MATTERS: pick the direction whose endpoints stay inside the
    verified cable envelope [-10849, 11651] from the current position.
    speed_pct must be >= ~31 (pwm 80): below the breakaway the turret
    near-stalls under the Kinect mass + cable drag (measured 2026-10-25:
    pwm 61 crawled at 14-55 ticks/s; pwm 51 twitch free-spinning gave 317).

    Repeatability = the final snapshot C vs the start C (the v1 mission
    standard: +-10 ticks), cross-checked against the oracle after the stop.
    """
    if not motord_running() and not start_motord():
        sys.exit("motord failed to start")
    target = int(ticks_per_deg * 90)
    c_start = snap_encoders()["C"]
    print("swing90: start C={}, target {} ticks/leg (pwm {})".format(
        c_start, target, int(speed_pct * 255 / 100)))
    if ccw_first:
        legs = [(-1, "leg1 CCW 90"), (1, "leg2 home"), (-1, "leg3 CCW 90"), (1, "leg4 home")]
    else:
        legs = [(1, "leg1 CW 90"), (-1, "leg2 home"), (1, "leg3 CW 90"), (-1, "leg4 home")]
    for i, (direction, name) in enumerate(legs):
        c0 = snap_encoders()["C"]
        t0 = time.time()
        capped = False
        while True:
            c_now = snap_encoders()["C"]
            if abs(c_now - c0) >= target:
                break
            if time.time() - t0 > 60.0:
                capped = True
                break
            rpc("turret", json.dumps({"pct": speed_pct * direction}))
            time.sleep(0.1)
        rpc("turret", '{"pct":0}')
        c1 = snap_encoders()["C"]
        print("  {}: dC={} ({:.1f}s{})".format(
            name, c1 - c0, time.time() - t0, " CAP HIT" if capped else ""))
        time.sleep(0.5)
    c_end = snap_encoders()["C"]
    print("swing90 repeatability: start C={}, end C={}, error={} ticks "
          "(v1 standard: +-10)".format(c_start, c_end, c_end - c_start))
    stop_motord()
    c_oracle = _turret_encoder()
    print("oracle cross-check after stop: C={} (delta vs snapshot: {})".format(
        c_oracle, c_oracle - c_end))


def v1_swing90(ticks_per_deg=125.0, speed=82, ccw_first=True):
    """The IDENTICAL swing90 mission via the v1 oracle (BrickPi.py direct).

    Requires motord STOPPED (the oracle owns the UART). Same legs, same pwm,
    same position-target loop - the direct comparison for the turret rate
    variance: if v1 crawls/varies like motord did, the variance is hardware
    (cable drag), not a v2 defect.
    """
    import BrickPi
    BrickPi.BrickPiSetup()
    BrickPi.BrickPi.MotorEnable[2] = 1
    BrickPi.BrickPi.SensorType = [
        BrickPi.TYPE_SENSOR_LIGHT_ON, 0, 0, BrickPi.TYPE_SENSOR_ULTRASONIC_CONT]
    BrickPi.BrickPiSetupSensors()
    target = int(ticks_per_deg * 90)
    BrickPi.BrickPiUpdateValues()
    c_start = BrickPi.BrickPi.Encoder[2]
    print("v1swing90: start C={}, target {} ticks/leg (pwm {})".format(
        c_start, target, speed))
    if ccw_first:
        legs = [(-1, "leg1 CCW 90"), (1, "leg2 home"), (-1, "leg3 CCW 90"), (1, "leg4 home")]
    else:
        legs = [(1, "leg1 CW 90"), (-1, "leg2 home"), (1, "leg3 CW 90"), (-1, "leg4 home")]
    for i, (direction, name) in enumerate(legs):
        BrickPi.BrickPiUpdateValues()
        c0 = BrickPi.BrickPi.Encoder[2]
        t0 = time.time()
        capped = False
        while True:
            BrickPi.BrickPi.MotorSpeed[2] = speed * direction
            BrickPi.BrickPiUpdateValues()
            c_now = BrickPi.BrickPi.Encoder[2]
            if abs(c_now - c0) >= target:
                break
            if time.time() - t0 > 60.0:
                capped = True
                break
        BrickPi.BrickPi.MotorSpeed[2] = 0
        BrickPi.BrickPiUpdateValues()
        c1 = BrickPi.BrickPi.Encoder[2]
        print("  {}: dC={} ({:.1f}s{})".format(
            name, c1 - c0, time.time() - t0, " CAP HIT" if capped else ""))
        time.sleep(0.5)
    BrickPi.BrickPiUpdateValues()
    c_end = BrickPi.BrickPi.Encoder[2]
    print("v1swing90 repeatability: start C={}, end C={}, error={} ticks".format(
        c_start, c_end, c_end - c_start))


def turret_const(seconds=18.4, speed_pct=32):
    """Constant turret pwm via motord for a fixed time - the direct
    comparison with a v1 swing leg (11250 ticks in 18.4 s at pwm 82).
    Prints the rate + the error counter so a failing UART exchange is visible."""
    if not motord_running() and not start_motord():
        sys.exit("motord failed to start")
    c0 = snap_encoders()
    t0 = time.time()
    while time.time() - t0 < seconds:
        rpc("turret", json.dumps({"pct": speed_pct}))
        time.sleep(0.1)
    rpc("turret", '{"pct":0}')
    time.sleep(0.5)
    c1 = snap_encoders()
    dt = time.time() - t0
    print("motord const turret: dC={} in {:.1f}s = {:.0f} ticks/s "
          "(v1 leg: 11250 in 18.4s = 612/s) errors={}".format(
              c1["C"] - c0["C"], dt, (c1["C"] - c0["C"]) / dt, c1.get("errors")))


def return_to(target=297, speed_pct=32):
    """Rotate the turret back to an absolute encoder position.

    The intent refresh runs in a dedicated 10 Hz thread (independent of the
    position checks) - the swing90 crawl was the refresh cadence dropping
    below the 400 ms expiry whenever a slow snapshot interleaved.
    """
    import threading

    # Always restart fresh: a stale socket file masquerades as a running
    # daemon, and two motord instances would fight over the UART.
    stop_motord()
    if not start_motord():
        sys.exit("motord failed to start")
    c0 = snap_encoders()["C"]
    need = target - c0
    direction = 1 if need > 0 else -1
    print("return: from C={} to {} ({} ticks = {:.1f} deg, direction {})".format(
        c0, target, need, need / 125.0, "CW" if direction > 0 else "CCW"))

    go = [True]

    def refresh():
        while go[0]:
            try:
                rpc("turret", json.dumps({"pct": speed_pct * direction}))
            except Exception:
                pass
            time.sleep(0.1)

    thr = threading.Thread(target=refresh)
    thr.start()
    t0 = time.time()
    capped = False
    try:
        while True:
            c_now = snap_encoders()["C"]
            remaining = target - c_now
            if abs(remaining) < 150:
                break  # on target; the coast adds ~100 ticks
            if (remaining > 0) != (need > 0):
                break  # overshot past the target
            if time.time() - t0 > 180.0:
                capped = True
                break
            # slow to ~pwm 20 for the final 2500 ticks (the overshoot shrinks)
            if abs(remaining) < 2500 and speed_pct > 10:
                speed_pct = 10
            time.sleep(0.15)
    finally:
        go[0] = False
        thr.join()
        rpc("turret", '{"pct":0}')
    time.sleep(0.8)
    c_end = snap_encoders()["C"]
    print("return done: C={} (target {}, error {} ticks = {:.2f} deg{})".format(
        c_end, target, c_end - target, (c_end - target) / 125.0,
        " CAP HIT" if capped else ""))
    stop_motord()
    c_oracle = _turret_encoder()
    print("oracle cross-check: C={} (delta {})".format(c_oracle, c_oracle - c_end))


def rotate_to(target=297, speed_pct=32, burst_s=12.0):
    """Rotate the turret to an absolute encoder position, direction auto.

    The direction follows the sign of (target - current), so the wrap
    stays minimal: to return to the original facing use the original
    position itself (297), NOT 297+45000 (that would wrap a full turn).

    Stall guard: aborts if a full burst progresses <100 ticks/s (the
    cable-binding signature). The final 2500 ticks run at pwm ~20 so the
    coast lands within ~50 ticks of the target.
    """
    stop_motord()
    if not start_motord():
        sys.exit("motord failed to start")
    c0 = snap_encoders()["C"]
    remaining = target - c0
    direction = 1 if remaining > 0 else -1
    print("rotate_to: start C={}, target {}, remaining {} ticks "
          "({:.1f} deg, direction {})".format(
              c0, target, remaining, remaining / 125.0,
              "CW" if direction > 0 else "CCW"))
    if abs(remaining) < 150:
        print("already at target - no motion")
        stop_motord()
        return
    leg = 0
    while True:
        leg += 1
        c_leg0 = snap_encoders()["C"]
        gap = target - c_leg0
        if abs(gap) < 300:
            break  # close enough; the coast lands it
        pct = speed_pct if abs(gap) > 2500 else 10  # the gentle final approach
        go = [True]

        def refresh():
            while go[0]:
                try:
                    rpc("turret", json.dumps({"pct": pct * direction}))
                except Exception:
                    pass
                time.sleep(0.1)

        thr = threading.Thread(target=refresh)
        thr.start()
        t0 = time.time()
        early = False
        while time.time() - t0 < burst_s:
            time.sleep(0.1)
            if abs(target - snap_encoders()["C"]) < 300:
                early = True
                break
        go[0] = False
        thr.join()
        rpc("turret", json.dumps({"pct": 0}))
        time.sleep(0.6)
        c_now = snap_encoders()["C"]
        rate = abs(c_now - c_leg0) / (time.time() - t0)
        print("  burst {}: dC={} (now C={}, remaining {}, rate {:.0f} ticks/s)".format(
            leg, c_now - c_leg0, c_now, target - c_now, rate))
        if early or abs(target - c_now) < 300:
            break
        if rate < 100.0:
            print("  ABORT: rate collapsed - possible cable binding; robot idle")
            stop_motord()
            return
        if leg > 20:
            print("  ABORT: too many bursts")
            stop_motord()
            return
    time.sleep(0.8)
    c_end = snap_encoders()["C"]
    print("rotate_to done: C={} (target {}; error {} ticks = {:.2f} deg)".format(
        c_end, target, c_end - target, (c_end - target) / 125.0))
    stop_motord()
    print("motord stopped - robot idle")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    if mode == "motion":
        motion_parity()
        return
    if mode == "turret":
        estop_drill()
        turret_parity()
        swing90_motord()
        return
    if mode == "swing":
        swing90_motord()
        return
    if mode == "v1swing":
        stop_motord()
        v1_swing90()
        return
    if mode == "turretconst":
        turret_const()
        return
    if mode == "return":
        tgt = int(sys.argv[2]) if len(sys.argv) > 2 else 297
        return_to(tgt)
        return
    if mode == "cw":
        secs = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
        rotate_to(target=297 + 45000, burst_s=secs)
        return
    if mode == "rotate":
        tgt = int(sys.argv[2]) if len(sys.argv) > 2 else 297
        rotate_to(target=tgt, burst_s=12.0)
        return
    if mode == "rel":
        delta = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        if not motord_running() and not start_motord():
            sys.exit("motord failed to start")
        c0 = snap_encoders()["C"]
        print("rel: current C={}, delta {} -> target {}".format(c0, delta, c0 + delta))
        rotate_to(target=c0 + delta, burst_s=12.0)
        return
    if mode == "burst":
        secs = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
        pct = int(sys.argv[3]) if len(sys.argv) > 3 else 32
        stop_motord()
        if not start_motord():
            sys.exit("motord failed to start")
        c0 = snap_encoders()["C"]
        print("burst: start C={}, pct {} for {:.1f}s".format(c0, pct, secs))
        go = [True]

        def refresh():
            while go[0]:
                try:
                    rpc("turret", json.dumps({"pct": pct}))
                except Exception:
                    pass
                time.sleep(0.1)

        thr = threading.Thread(target=refresh)
        thr.start()
        time.sleep(secs)
        go[0] = False
        thr.join()
        rpc("turret", json.dumps({"pct": 0}))
        time.sleep(0.8)
        c1 = snap_encoders()["C"]
        print("burst done: C={} (dC={} ticks = {:.1f} deg)".format(
            c1, c1 - c0, (c1 - c0) / 125.0))
        stop_motord()
        print("motord stopped - robot idle")
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
