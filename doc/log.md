# Wiki Log

Append-only chronological record of wiki activity. **Newest entries at the top.**

Each entry starts with a consistent prefix so the log is greppable:

```
## [YYYY-MM-DD] <type> | <title>
```

Types: `ingest`, `decision`, `progress`, `lint`.
Timeline: `grep "^## \[" doc/log.md | head`.

---

## [2026-10-25] progress | Drive-ratio mission: track broke mid-run; re-diagnosed on the repositioned robot

The first drive-ratio run ended with a **broken rear track** (the sonar went
blind 6 s into motion, the backward leg jammed) — all run-1 data invalid,
retracted. Valid findings: the drive train is geared ~6x deeper than the
turret (~1.16 ticks/s per speed unit vs 7.2); the sonar is blind WHILE the
tracks turn (EMI/vibration) and only works at rest; the kinect depth reads
fine during motion. After the repair + repositioning: the obstacle now at
43 cm (sonar) / 0.50 m (kinect) — too close for the planned excursions.
**Mission blocked on the user repositioning the robot** to ~75-80 cm.
Raw: [sources/2026-10-25-drive-ratio-run.md](sources/2026-10-25-drive-ratio-run.md).

## [2026-10-25] progress | Self-healing kinect worker deployed and validated

Child rewritten on the callback API (process_events loop) with a stall
watchdog (10 s no-frames → os._exit → kernel releases camera+port) and
latest-wins DONTWAIT pushes (63-85% CPU vs 139% sustained before); the
server's reaper thread respawns it in ≤3 s — **validated by killing the
child mid-stream** (spawn count 2, frames resumed). server.py now terminates
the child on SIGTERM (no more orphans on restart). User constraint recorded:
the Kinect must stay on the powered hub chain (power source), so storms are
mitigated by recovery, not relocation.

## [2026-10-25] progress | Swing mission repeated: trajectory repeats ±10 ticks, center = +401

Repeat run (blob-driven recenter): all legs 100% again; the trajectory
matches run 2 within ~±10 ticks after the start-offset alignment; color
reproduces within 1-2 counts at every pose; return error 91 ticks (vs 6) —
the honest repeatability bound is ±100 ticks (±0.8°), set by the recenter.
Both runs' blob data fits `blob_x = 320 + (enc − 401) × 0.092` → **the true
center is encoder ≈ +401**; blob hysteresis ~12-15 px between approach
directions (the 252-tick backlash, confirmed). The per-frame ratio
cross-check failed on encoder timestamp skew — 125 ticks/° stands on the
optical method. Raw appended to
[sources/2026-10-25-swing90-run.md](sources/2026-10-25-swing90-run.md);
koc-swing90-repeat closed.

## [2026-10-25] progress | ±90° swing mission: reliable, return error 0.05°

Mission koc-swing90 complete: LEFT 90 → RIGHT 180 → LEFT 90 with
encoder-driven legs — 100% target achievement on all legs, no stalls, no
cable limits hit in the ±90° span; return error **6 ticks (0.05°)**. Run 1's
1641-tick miss was the 100-deep command queue backing up at 10 Hz streaming
(fixed: stream at the ~0.3 s consumption rate). Color fingerprint
reproduced exactly (768→768) and spans 734-768 across ±90°; sonar 75 cm
constant; kinect blob re-centered (x=335). Raw:
[sources/2026-10-25-swing90-run.md](sources/2026-10-25-swing90-run.md).
Queue-staleness noted on koc-v2-motord-driver; koc-swing90-sweep closed.

## [2026-10-25] progress | Turret centered (landmark reproduces); tilt diagnostic; accel bug cracked

Centering run: the blob re-centered at encoder **271-275** (right approach)
vs **+527** (left approach, previous run) — **gear backlash ≈ 252 ticks ≈ 2°**
measured; v2 homing must approach from one direction. Tilt diagnostic
(standalone probe, server stopped): pivot −8.5° moved the obstacle's depth
reading from raw 664 (0.79 m) to **579 (0.70 m)** — matching the sonar's
75 cm; level reading returned identically after. **Accelerometer mystery
cracked: mks is ~0 at all poses while the tilt angle tracks perfectly —
the angle comes from the motor controller; the accel data path is
dead/stubbed** (koc-hw-kinect-accel-axes re-diagnosed). Raw probe:
`testing/turret_center_tilt_probe.py`, `testing/kinect_tilt_depth_probe.py`.

## [2026-10-25] progress | Homing landmark measured (encoder +527 / color 790); fd leak fixed

First full homing sweep with sonar ground truth (75 cm obstacle dead-ahead):
the Kinect's nearest-depth blob centered at **encoder ≈ +527, color ≈ 790**
— the first measured homing landmark pair; sonar stayed 75 (chassis-fixed,
never occluded). En route found + fixed the true "telemetry death" root
cause: `get_voltage()` leaked one SMBus fd/call → `Too many open files`
killed the wrapper thread in ~15-20 min. Raw:
[sources/2026-10-25-turret-homing-run.md](sources/2026-10-25-turret-homing-run.md).
Turret now ≈ 6° left of center (encoder +1268).

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
