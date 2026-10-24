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

## Dependencies

- OS: Raspbian 9 stretch, Python 3.5.3 — pins the codebase's compat choices
  (pickle protocol 4, no f-strings in server paths).
- USB topology: Kinect hangs behind an NEC + Genesys hub chain — source of
  libfreenect resync storms; a dedicated port is advisable.

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
