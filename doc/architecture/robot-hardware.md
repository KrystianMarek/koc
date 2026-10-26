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

## Measured constants

**This table is the single source for encoder, gearing, odometry and rate
numbers.** Other pages link here instead of repeating values; when a new
measurement changes a value, update this row, file the raw capture in
`doc/sources/`, and add a `log.md` entry. Sources dated before 2026-10-26
assume 360 ticks per motor revolution and call ticks per degree a "ratio";
read their raw tick counts, not their derived ratios.

| Constant | Value | Status | Evidence |
|---|---|---|---|
| Encoder resolution | **720 ticks per motor revolution** (0.5° per tick) | BrickPi library fact | `testing/brickpi/LEGO-Encoder_Test.py` |
| Drive odometry | **166.6 ± 1.1 ticks per cm** of travel, rest to rest | measured 2026-10-26 (six 19 cm legs) | [drive ratio re-run](../sources/2026-10-26-drive-ratio-rerun.md) |
| Track travel per motor revolution | **4.32 cm** (720 / 166.6) | derived | same |
| Drive gearing | **12-tooth driving 20-tooth (1.67:1)** into a 6-tooth sprocket on the 42055 track (12 mm pitch, 7.2 cm per sprocket revolution); predicts 166.7 ticks/cm | inferred from odometry and `pictures/`; teeth not counted | same |
| Drive coast after a stop | ~100–150 ticks at PWM 60 | measured 2026-10-26 | same |
| Drive left/right balance | forward: right encoder turns ~2 % more than left; backward: equal | measured 2026-10-26 | same |
| Drive round-trip repeatability | < 0.6 cm per 38 cm out and back | measured 2026-10-26 | same |
| Drive rate | ~6–8 ticks/s per PWM unit, non-linear (~470 ticks/s at PWM 60) | measured 2026-10-25 | [drive ratio run](../sources/2026-10-25-drive-ratio-run.md) |
| Turret ticks per turret degree | **~116.7** working value (one turn ≈ 42000 ticks); the earlier optical estimate was 125 ± 10 % | **unconfirmed**: the two estimates differ by 7 % | [centering run](../sources/2026-10-26-turret-centering-run.md), [turret calibration](../sources/2026-10-25-turret-calibration.md) |
| Turret reduction, motor : turret | **~58:1** (42000 / 720); 62.5:1 if 125 ticks/° | derived from the row above | — |
| Turret gear backlash | ~252 ticks (~2°) between approach directions | measured 2026-10-25 | [log 2026-10-25](../log.md), [swing90 run](../sources/2026-10-25-swing90-run.md) |
| Turret motor rate | ~510 ticks/s at PWM 80 (~42 motor rpm, ~4°/s at the turret) | measured 2026-10-24 | [state capture](../sources/2026-10-24-robot-state-capture.md) |
| Turret envelope | `center` 42298, `half_range` 21000 ticks (guard rules under Internals) | configuration in `~/.koc/turret.json` | [envelope run](../sources/2026-10-26-turret-envelope-run.md) |
| Sonar vs Kinect offset | sonar reads ~7 cm less than the Kinect blob distance | measured 2026-10-26 | [drive ratio re-run](../sources/2026-10-26-drive-ratio-rerun.md) |

## Internals (measured behavior)

- **Drive train**: skid-steer on two 42055 tracks. Each NXT motor drives
  one track through the gearing in the table. The motors are mounted
  opposite: GoForward runs the left encoder negative and the right
  positive, and equal commands spin the robot in place (TurnLeft = both
  −v, TurnRight = both +v). Count drive ticks from rest to rest: the tracks
  coast after a stop command. The 2026-10-25 odometry of 161.0 ticks/cm
  counted at the stop command and is superseded.
- **Turret direction**: `TurretRight` = negative encoder ticks; positive
  ticks = turret left (the user's CCW seen from above). Do not compute
  "same facing" positions from a ticks-per-turn figure until the turret
  ratio is confirmed; find camera-forward with the Kinect.
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
- **Two-axis camera aiming**: yaw = BrickPi turret (PORT_C, drivable via
  `TurretLeft/Right`, verified); pitch = **Kinect internal tilt motor**
  (±27°, accelerometer feedback, verified 2026-10-25 — see
  [kinect interface](kinect-interface.md)). V1 wires only the yaw; tilt is
  stubbed out end-to-end (no packet, `kinect_process.py` returns 0).
- **Turret cable envelope (2026-10-26)**: cables run through the turret and
  are neutral at camera-forward. **The turret never turns more than 180°
  either way from it.** Both motor writers enforce this from
  `~/.koc/turret.json` (values in [Measured constants](#measured-constants)): the
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
- **Sonar (PORT_4)**: works — 61 cm with an obstacle the Kinect puts at
  0.61–0.67 m (2026-10-26). It read during motion on the 2026-10-26 drive
  re-run (an earlier run saw 255 while the tracks turned), in 1 cm steps.
  255 means no echo in its cone: on 2026-10-26 it lost a flat obstacle
  beyond ~62 cm. The 2026-10-25 "dead" readings were aim/range
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
