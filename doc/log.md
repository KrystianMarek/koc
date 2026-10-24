# Wiki Log

Append-only chronological record of wiki activity. **Newest entries at the top.**

Each entry starts with a consistent prefix so the log is greppable:

```
## [YYYY-MM-DD] <type> | <title>
```

Types: `ingest`, `decision`, `progress`, `lint`.
Timeline: `grep "^## \[" doc/log.md | head`.

---

## [2026-10-24] ingest | Intel NCS (USB accelerator) verified + documented

Confirmed the NCS1 (`03e7:2150`, Myriad 2) on the robot: **boot mode**, no
loadable runtime (partial `/opt/movidius` NCSDK, no importable mvnc, no udev
rules), junk NCSDK tarballs in `~` (S3 error XML). Cloned
ncsdk/ncappzoo/libedgetpu into `external/` (ncsdk+ncappzoo match the existing
submodule pins). V2 stance: CPU INT8 default, accelerators pluggable —
[sources/2026-10-24-ncs-state.md](sources/2026-10-24-ncs-state.md),
hardware page section, vision Phase 5 updated. Fixed stale bd IDs
(`koc-hw-*`) across pages.

## [2026-10-24] ingest | BrickPi + Kinect library analysis for v2

Analyzed the hardware interface libraries v1 depends on. **Key correction**:
the BrickPi+ talks UART (500kbaud, `/dev/ttyS0` on RPi3), not I2C — two
ATmega3250s at addresses 1/2, checksummed frames, `MSG_TYPE_E_STOP` +
firmware `TIMEOUT_SETTINGS` deadman (v1 never enables it). Kinect stack =
libfreenect sync API, unthrottled. Cloned 8 upstream/reference repos into
`external/` (BrickPi, BrickPi_Python, BrickPi_C, libfreenect, libfreenect-sys/-rs,
rust-i2cdev, serialport-rs). Pages:
[architecture/brickpi-interface.md](architecture/brickpi-interface.md),
[architecture/kinect-interface.md](architecture/kinect-interface.md);
raw: [sources/2026-10-24-hardware-libs-capture.md](sources/2026-10-24-hardware-libs-capture.md).
Bugs/tasks: `koc-v2-motord-driver`, `koc-v2-camerad` added under `koc-v2`.

## [2026-10-24] decision | V2 direction: microduck-aligned software stack

Decided the project focus: build KOC v2 on the existing hardware (RPi 3 +
BrickPi+ + Kinect) with a tech stack aligned to Microduck — Rust daemons over
JSON-RPC/UDS, intents-not-motor-writes, features-not-frames, throttled capture,
health-gated updates. Direction sketched in
[vision/v2-microduck-stack.md](vision/v2-microduck-stack.md) with open
questions for the planning session; epic `koc-v2` + task `koc-v2-plan` in `bd`
(hw bugs linked as children). Also captured the v1 code assessment
([development/2026-10-24-koc-v1-code-assessment.md](development/2026-10-24-koc-v1-code-assessment.md))
as the v2 baseline, and filled overview/goals/status.

## [2026-10-24] ingest | Live robot survey: hardware data + software state

Connected to the robot (192.168.10.187) over SSH: surveyed system, hardware
(BrickPi ports A/D/C, sensors 1/4, Kinect on hubs, NCS present), deployment
(~/rpi_lego_robot, pi_robot3 venv). Verified Kinect stream end-to-end and
turret rotation (encoder −122 → −1147 ticks via streamed commands; discovered
the ~0.3 s deadman: single commands twitch, stream at ~10 Hz). Found + fixed
app/Networking casing locally; diagnosed Kinect wedge (unthrottled capture +
fork-inherited ZMQ fds). Raw: [sources/2026-10-24-robot-state-capture.md](sources/2026-10-24-robot-state-capture.md).
Synthesized: [architecture/robot-hardware.md](architecture/robot-hardware.md),
[development/robot-deployment.md](development/robot-deployment.md).
Bugs filed: `koc-hw-kinect-wedge`, `koc-hw-sync-target`.
New tools: `testing/kinect_stream_probe.py`, `testing/turret_rotate_probe.py`.

## [2026-10-24] ingest | Microduck robot research + external/ reference clones

Researched the NVIDIA GTC Berlin Microduck robot (Pollen Robotics × Hugging
Face): hardware spec, onboard Rust daemon stack, Yocto OS, Isaac Lab/Newton
training pipeline. Captured in
[sources/2026-10-24-microduck-analysis.md](sources/2026-10-24-microduck-analysis.md);
cloned five upstream repos into `external/` (manifest:
[external/readme.md](../external/readme.md)). Adopted the ai-assisted-development
template into the repo (AGENTS.md, doc wiki, pre-commit, bd).

## [2026-10-24] progress | Project bootstrapped from ai-assisted-development template

Adoption via `adopt.sh`: template skeleton (AGENTS.md, doc/ wiki tree,
.pre-commit-config.yaml, .claude settings), placeholder wiki core pages, BEADS
hook merged into pre-commit, `bd init` completed (note: upstream `bd init`
panicked in `updateAgentFile` on the template-fresh AGENTS.md — known bug,
critical files verified in place).
