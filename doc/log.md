# Wiki Log

Append-only chronological record of wiki activity. **Newest entries at the top.**

Each entry starts with a consistent prefix so the log is greppable:

```
## [YYYY-MM-DD] <type> | <title>
```

Types: `ingest`, `decision`, `progress`, `lint`.
Timeline: `grep "^## \[" doc/log.md | head`.

---

## [2026-10-25] progress | Self-healing kinect worker deployed and validated

Child rewritten on the callback API (process_events loop) with a stall
watchdog (10 s no-frames → os._exit → kernel releases camera+port) and
latest-wins DONTWAIT pushes (63-85% CPU vs 139% sustained before); the
server's reaper thread respawns it in ≤3 s — **validated by killing the
child mid-stream** (spawn count 2, frames resumed). server.py now terminates
the child on SIGTERM (no more orphans on restart). User constraint recorded:
the Kinect must stay on the powered hub chain (power source), so storms are
mitigated by recovery, not relocation.

## [2026-10-25] progress | Kinect wedge root-caused deeper; spawn+throttle deployed

The wedge is a **chain**: (1) fork-inherited ZMQ fds (fixed: spawn context),
(2) unthrottled capture flooding the aggregator (fixed: 10 fps cap — note
capture+compress alone eats >100 ms, so the cap only bounds push rate), (3)
**orphaned spawn children surviving restarts** (SIGTERM kills the parent
without reaping daemon children; they keep the camera + :5558 — restarts must
`pkill -f "multiprocessing.spa[w]n"` too), and (4) the **root hardware
cause: the Kinect USB link via the two-hub chain enters chronic libfreenect
resync storms ("Stream 70") within minutes of streaming** — the child then
spins at ~135% and jams the pipeline. Physical fix needed: Kinect on a
dedicated USB port. Watcher running on the robot
(`/tmp/koc_stream_watch.log`, 30 s window counts) to timestamp the
degradation. Color-sweep data: the color reading is a smooth reproducible
function of encoder position (no sharp corner feature in the swept arc).

## [2026-10-25] ingest | Turret gear ratio measured (~125:1), homing mark investigated

Constraint learned: cables run through the turret — rotation is limited, no
full revolutions (the cancelled first calibration assumed them; superseded by
`turret_ratio_probe.py` small swings). Gear ratio measured optically: scene
shift via Kinect frame correlation ÷ `KINECT_FX` vs encoder delta →
**~125 ticks/turret-degree ≈ 125:1** (±10%, 4 swings, corr ≥0.998). Color
sensor detects surface changes at ~45σ but the first feature (encoder −3468)
is not the expected cable position — identification open. Raw:
[sources/2026-10-25-turret-calibration.md](sources/2026-10-25-turret-calibration.md).

## [2026-10-25] ingest | Kinect tilt motor verified (user visually confirmed)

The Kinect base tilt motor (NUI Motor USB interface, ±27°, accelerometer
feedback) works: 0 → +12 → −12 → 0 commanded, ±1° accuracy, robot-side probe
`testing/kinect_tilt_probe.py`. V1 stubbed tilt out entirely; two-axis aiming
(yaw = turret, pitch = tilt) documented for v2 `camerad` (rate-limited
`camera.tilt` intent, LED as privacy indicator). Open: raw `get_mks_accel`
axis mapping printed near-zero at level. Camera and motor interfaces are
independent (tilt works while the server holds the camera).
[sources: kinect-interface tilt section](architecture/kinect-interface.md).

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
