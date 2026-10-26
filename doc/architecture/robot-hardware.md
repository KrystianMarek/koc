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
| Intel NCS (USB accelerator) | `03e7:2150` Myriad 2 — **boot mode**, firmware not loaded; partial NCSDK in `/opt/movidius` (no importable API, no udev rules); see [NCS state](../sources/2026-10-24-ncs-state.md) + [NCS support](../ncs-legacy-support.md) |

## Internals (measured behavior)

- **Encoder units**: the BrickPi counts **720 ticks per motor revolution**
  (0.5° per tick; `testing/brickpi/LEGO-Encoder_Test.py`). Pages before
  2026-10-26 assumed 360.
- **Turret dynamics**: streamed
  `TurretRight(80)` (PWM duty ≈31%) for 2 s → 1025 ticks ≈ **510 ticks/s ≈ 42 rpm**
  at the motor shaft; actual turret rate is geared down from that. Direction:
  `TurretRight` = negative encoder ticks; positive ticks = turret left
  (the user's CCW seen from above).
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
- **Drive odometry (measured 2026-10-26)**: **166.6 ± 1.1 ticks per cm of
  travel**, rest-to-rest encoder deltas over six 19 cm Kinect-measured legs.
  The 2026-10-25 value of 161.0 counted ticks at the stop command and missed
  the ~100–150 ticks the tracks coast before stopping. Round-trip error
  < 0.6 cm per 38 cm; GoForward runs the LEFT encoder negative and the RIGHT
  positive, with the right turning ~2 % more than the left. The sonar agrees
  at rest (10 cm vs 9.9 cm on a 10 cm move), sits ~7 cm behind the Kinect
  reading, and loses the echo beyond ~62 cm on that obstacle. See
  [drive ratio re-run](../sources/2026-10-26-drive-ratio-rerun.md).
- **Drive gearing (inferred 2026-10-26)**: 720 / 166.6 = **4.32 cm of track
  per motor revolution**. With the 42055 track's 12 mm pitch on a 6-tooth
  sprocket (7.2 cm per sprocket revolution) that is **1.67:1, a 12-tooth
  driving a 20-tooth gear** (tan double-bevel gears visible on the front
  cross axle in `pictures/`); predicted 166.7 ticks/cm. Tooth counts not yet
  checked on the robot. Skid-steer: the motors are mounted opposite, so equal
  commands spin the robot in place (TurnLeft = both −v, TurnRight = both +v).
- **Drive rate**: **~6-8 ticks/s per PWM unit** (v5 CSV ~470 ticks/s at PWM 60; the v1/motord
  parity twitches ~290-315 at PWM 51 — the earlier "1.16 ticks/s per unit"
  note was a units error, corrected 2026-10-25 during the motord parity).
  See the [drive ratio run](../sources/2026-10-25-drive-ratio-run.md).
- **Two-axis camera aiming**: yaw = BrickPi turret (PORT_C, drivable via
  `TurretLeft/Right`, verified); pitch = **Kinect internal tilt motor**
  (±27°, accelerometer feedback, verified 2026-10-25 — see
  [kinect interface](kinect-interface.md)). V1 wires only the yaw; tilt is
  stubbed out end-to-end (no packet, `kinect_process.py` returns 0).
- **Turret gearing**: **~125 ticks per turret degree** (measured
  2026-10-25 via Kinect optical angle reference, ±10% — see
  [turret calibration](../sources/2026-10-25-turret-calibration.md)).
  **2026-10-26 evidence points lower: one full turn ≈ 42000 ticks
  (≈116.7 ticks/°)**, from re-centering by Kinect at C≈42298 vs the
  session-start spot C=297 — see
  [turret centering run](../sources/2026-10-26-turret-centering-run.md).
  Do not compute "same facing" positions with 45000 ticks per turn.
  At 720 ticks per motor revolution, 42000 ticks per turn is a **~58:1**
  motor:turret reduction (older pages call 125 ticks/° "125:1"; that is
  ticks per degree, not a gear ratio).
  At speed 80 the turret pans ~4°/s. Position is tracked by the
  cumulative encoder (persists while the BrickPi is powered).
- **Turret cable envelope (2026-10-26)**: cables run through the turret and
  are neutral at camera-forward. **The turret never turns more than 180°
  either way from it.** Both motor writers enforce this from
  `~/.koc/turret.json` (`center` 42298, `half_range` 21000 ticks): the
  v1 server via `app/server/turret_guard.py`, motord via
  `robot/motord/src/guard.rs`. Outward commands stop 800 ticks short of the
  limit (the v1 server coasts up to ~460 ticks past a stop at pwm 250). A
  missing file, or a first reading more than 400 ticks from the saved
  position (power cycle, hand turn), **locks** the turret until it is
  re-referenced — see the [turret centering runbook](../runbooks/turret-centering.md)
  and [envelope run](../sources/2026-10-26-turret-envelope-run.md). This
  supersedes the "±90° without a visual check" rule of the
  [cable incident](../sources/2026-10-25-turret-cable-incident.md).
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
- **Camera-forward reference (2026-10-26)**: **C=42298** on the front
  obstacle, approached from the left (Kinect bearing +0.10°). **User
  confirmed the facing and that the cables are fine there**; it is the
  envelope center. The 2026-10-25 "cable stalls" were probe artifacts
  (intent refresh starved by slow snapshots), not binding — see
  [centering run](../sources/2026-10-26-turret-centering-run.md).
- **Sonar (PORT_4)**: works at rest — 61 cm with an obstacle the Kinect puts
  at 0.61–0.67 m (2026-10-26). Blind while the tracks turn. The 255 (no
  echo) readings of 2026-10-25 were aim/range, not a dead sensor
  (`koc-hw-sonar-dead` closed).
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
  the working mirror documented in [NCS support](../ncs-legacy-support.md)
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
- `testing/kinect_stream_probe.py`, `testing/turret_rotate_probe.py` (v1 measurement tools)
- `testing/motord_parity_probe.py` (motord parity + turret moves), `testing/kinect_bearing.py` (obstacle bearing), `testing/turret_envelope.py` (show / re-reference the envelope)
- [Agent lessons](../development/agent-lessons.md) — rules learned on this hardware
- [Architecture overview](README.md) · [Networking](../networking.md) — port map
