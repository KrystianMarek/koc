# Robot Hardware

## Purpose

Inventory and measured behavior of the physical robot that the K.O.C server
controls: Raspberry Pi 3 + BrickPi+ + Xbox 360 Kinect (+ legacy Intel NCS).
Anyone debugging against the live robot starts here.

## Context

Server side of the client/server split (see [overview](../overview.md)). The
robot runs `server.py`; all client connections are inbound (5556/5559/5560).

## Interfaces

| Interface | Mapping |
|---|---|
| BrickPi PORT_A | left track motor |
| BrickPi PORT_D | right track motor |
| BrickPi PORT_C | **turret motor (rotates the Kinect)** |
| BrickPi PORT_1 | color/light sensor (`TYPE_SENSOR_LIGHT_ON`) |
| BrickPi PORT_4 | ultrasonic sensor (continuous) |
| BrickPi battery | 8.854 V measured (healthy); `dtparam=brickpi_battery=okay` |
| Kinect USB | Camera 045e:02ae, Motor 02b0, Audio 02ad — all enumerated; video 480×640×3 uint8, depth 480×640 uint16 |
| Intel NCS (USB accelerator) | `03e7:2150` Myriad 2 — **boot mode**, firmware not loaded; partial NCSDK in `/opt/movidius` (no importable API, no udev rules); see [NCS state](../sources/2026-10-24-ncs-state.md) + [NCS support](../development/ncs-legacy-support.md) |

## Internals (measured behavior)

- **Turret dynamics**: NXT encoder 360 ticks/motor-shaft-rev. Streamed
  `TurretRight(80)` (PWM duty ≈31%) for 2 s → 1025 ticks ≈ **510 ticks/s ≈ 85 rpm**
  at the motor shaft; actual turret rate is geared down from that. Direction:
  `TurretRight` = negative encoder ticks.
- **Encoder persistence**: turret encoder value survived a full server restart
  (−122 before and after) — the BrickPi holds encoder state while powered;
  do not assume angle 0 after a reboot of `server.py`.
- **Deadman**: `BrickPiWrapper` re-sends zero speeds after
  `COMMAND_QUEUE_GRACE=3` command-less cycles (~0.3 s). A single command
  produces a ~0.3 s twitch; **commands must be streamed at ~10 Hz** to hold
  motion (the GUI does this on key-hold). This surprised us: see
  [state capture](../sources/2026-10-24-robot-state-capture.md).
- **Depth encoding**: raw Kinect depth is *disparity* (0–2047); values >1023
  invalid; valid range observed 554–1023 for the desk scene. Display path:
  clip to 10 bits, `>> 2` (see `Config.DEPTH_DISPLAY_BITS`).
- **Drive odometry (measured 2026-10-25)**: **161.0 ± 0.2 ticks per cm of
  travel** (three 20 cm legs, kinect-oracle measured, 0.2% spread);
  the drivetrain backlash/slip < 0.4 cm per 40 cm round trip; GoForward
  runs the LEFT encoder negative and the RIGHT positive. The drive rate is
  **~6-8 ticks/s per PWM unit** (v5 CSV ~470 ticks/s at PWM 60; the v1/motord
  parity twitches ~290-315 at PWM 51 — the earlier "1.16 ticks/s per unit"
  note was a units error, corrected 2026-10-25 during the motord parity).
  See [drive ratio run](../sources/2026-10-25-drive-ratio-run.md).
- **Two-axis camera aiming**: yaw = BrickPi turret (PORT_C, drivable via
  `TurretLeft/Right`, verified); pitch = **Kinect internal tilt motor**
  (±27°, accelerometer feedback, verified 2026-10-25 — see
  [kinect interface](kinect-interface.md)). V1 wires only the yaw; tilt is
  stubbed out end-to-end (no packet, `kinect_process.py` returns 0).
- **Turret gearing**: **~125 ticks per turret degree ≈ 125:1** (measured
  2026-10-25 via Kinect optical angle reference, ±10% — see
  [turret calibration](../sources/2026-10-25-turret-calibration.md)).
  **2026-10-26 evidence points lower: one full turn ≈ 42000 ticks
  (≈116.7 ticks/°)**, from re-centering by Kinect at C≈42298 vs the
  session-start spot C=297 — see
  [turret centering run](../sources/2026-10-26-turret-centering-run.md).
  Do not compute "same facing" positions with 45000 ticks per turn.
  At speed 80 the turret pans ~4°/s. **Cables run through the turret —
  rotation is limited; never rotate unbounded.** Position is tracked by the
  cumulative encoder (persists while the BrickPi is powered).
- **Turret homing mark**: the color sensor (PORT_1) sweeps ~5 cm above the
  body; a cable at the body's back marks camera-forward (the original paper
  dial is destroyed). Signal quality is excellent (σ≈1 counts, features
  ~45σ), but the first detected feature (encoder ≈ −3468, 2026-10-25) does
  not match the expected cable position — identification open.
- **Homing run 2026-10-25**: with an obstacle 75 cm dead-ahead (sonar-
  confirmed, steady 75 across the whole sweep), the Kinect's nearest-depth
  blob centered at **encoder ≈ +527, color ≈ 790** — the first measured
  homing landmark pair. See
  [turret homing run](../sources/2026-10-25-turret-homing-run.md).
- **fd-leak fixed**: `get_voltage()` leaked one SMBus fd per call →
  `Too many open files` killed the wrapper thread (~15-20 min) — the true
  "telemetry death" root cause. Now closed per read (bd
  `koc-hw-kinect-wedge`).

## Dependencies

- OS: Raspbian 9 stretch, Python 3.5.3 — pins the codebase's compat choices
  (pickle protocol 4, no f-strings in server paths).
- USB topology + power: the Kinect sits on an NEC + Genesys hub chain
  **because the chain provides power the RPi 3 port alone cannot** (user
  constraint — a direct port is *not* an option). The chronic "Stream 70"
  resync storms within minutes of streaming are the visible symptom of
  (a) two hub hops in series, (b) the Kinect's ~25 MB/s wire load eating a
  large share of the Pi's single shared 480 Mbps USB root bus (which also
  carries Ethernet and the NCS), and (c) power sharing on the chain.
  Mitigations: one quality *powered* hub instead of the daisy chain;
  demand-driven capture in v2 `camerad` (stream only while a consumer
  wants frames); self-healing worker for v1 (re-open device on sync
  timeouts). See [kinect interface](kinect-interface.md).

## Intel NCS (USB accelerator)

The robot carries an Intel Movidius Neural Compute Stick (Myriad 2 VPU,
~100 GFLOPS FP16, ~1 W) — its "NPU via USB", analogous to Microduck's
onboard NPU running `duck-detect`. State as of 2026-10-24:

- Device enumerated in **boot mode** (`03e7:2150`; running = `03e7:f63b`) on
  the **same nested hub chain as the Kinect** (hub path `1-1.5.3`).
- Partial NCSDK at `/opt/movidius` (headers, `mvncapi.py`, firmware for both
  armv7l/x86_64) but **no importable `mvnc` API, no udev rules, no libmvnc
  runtime wired up** — nothing loads the firmware today.
- The NCSDK tarballs in `~` are junk (an S3 error XML saved as a .tar.gz);
  the working mirror documented in [NCS support](../development/ncs-legacy-support.md)
  is the sanctioned path.
- Ecosystem: NCSDK archived 2019; OpenVINO never supported NCS1; Coral Edge
  TPU EOL 2026; Hailo needs PCIe. **CPU INT8 inference is the only
  future-proof default on this platform** — treat any accelerator as a
  pluggable backend.
- **Vs Microduck's NPU**: the RK3566 NPU is ~0.8 TOPS INT8 — roughly **16×
  the MAC throughput** of the NCS1's ~100 GFLOPS FP16, with no USB bottleneck
  (on-SoC, shared memory) and a live toolchain (RKNN-Toolkit2 vs archived
  NCSDK). Still an entry-class accelerator (Rockchip: "a practical
  accelerator, not a miracle worker") — Microduck's `duck-detect` is a
  deliberately tiny one-class model, sized to the job, not the peak number.

Raw evidence: [2026-10-24 NCS state](../sources/2026-10-24-ncs-state.md).

## Operational Notes

- Runs hot-ish but stable: 52–53°C CPU idle-to-light load.
- `i2cdetect` is not installed — probe BrickPi via its Python library instead.
- Known wedge: unthrottled Kinect capture + fork-inherited ZMQ fds can stall
  telemetry after minutes; restart `server.py` to recover. Details + fixes:
  [robot deployment state](../development/robot-deployment.md), bug
  `koc-hw-kinect-wedge` in `bd`.

## References

- [2026-10-24 robot state capture](../sources/2026-10-24-robot-state-capture.md) (raw data)
- `testing/kinect_stream_probe.py`, `testing/turret_rotate_probe.py` (measurement tools)
- [Architecture overview](README.md) · [Networking](../networking) — port map
