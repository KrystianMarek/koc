# Wiki Log

Append-only chronological record of wiki activity. **Newest entries at the top.**

Each entry starts with a consistent prefix so the log is greppable:

```
## [YYYY-MM-DD] <type> | <title>
```

Types: `ingest`, `decision`, `progress`, `lint`.
Timeline: `grep "^## \[" doc/log.md | head`.

---

## [2026-10-26] lint | Wiki health check after the turret centering session

Overall: 🟡 Yellow → fixed to 🟢 except the items below
- Freshness: `status.md` updated today; `goals.md` (stale since 2026-10-24) and
  `development/robot-deployment.md` (pre-motord) rewritten.
- Contradictions fixed: v2 plan constants (drive "1.16 ticks/s per unit" units
  error → 6–8; sonar "dead" → works at rest; turret ratio caveat ~116.7);
  vision page said motord uses I2C (it is UART); `brickpi-interface.md` now
  records the libc implementation, VALUES packing order and the lock lesson.
  Raw sources left untouched; the cable-incident "stall" reading is corrected
  in `robot-hardware.md`.
- Orphans: 5 development pages (v1-era TODO/guidance) now linked from
  `development/README.md` and `index.md`.
- Broken links: 11 found, all fixed — template leftovers (adopt.sh plans,
  inbox row, `adopting-with-script.md`) removed or unlinked; wrong paths in
  `overview.md`, `robot-hardware.md`, the v1 code assessment.
- Index/log integrity: every `doc/` page is now in `index.md` (added the
  2026-10-25 sources, the plans, the legacy v1 docs); sources README index
  completed.
- Ticket/wiki consistency: `koc-hw-sonar-dead` closed and reflected; centering
  plan stays Active until the user's visual check.
Next steps:
1. AGENTS.md still carries the template's initialization checklist and empty
   Project Overview / Development Conventions sections (user decision).
2. Kinect-interface strategy now records the hand-rolled FFI decision; the
   rest of that page gets a refresh when `camerad` starts.
3. A turret-centering runbook would make the 2026-10-26 procedure repeatable
   (not created — flag).

## [2026-10-26] progress | Turret re-centered by Kinect; motord snapshot starvation fixed

An audit found the previous turret "home" (297+45000) was ~25° off and two
probe overshoots made it worse (peak C=46084, cable wrap over one turn).
Fixed: motord held its cache lock across the loop sleep (snapshot 8–46 s →
1–2 ms); probe `rotate_to` now stops by position; stale-socket and
self-matching `pkill` traps; `kinect_bearing.py` now segments the obstacle
by sonar range. Four moves landed within 12 ticks; final Kinect bearing
+0.10°, surface yaw +0.25° at **C=42298**. Implies ~42000 ticks per turret
turn (~116.7 ticks/°). Sonar reads 61 cm — not dead.
Raw: [sources/2026-10-26-turret-centering-run.md](sources/2026-10-26-turret-centering-run.md).

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

## [2026-10-25] incident | Turret cable wedged after parity tests; robot idle and safe

The parity session wound the Kinect tether ~187° CW; the recovery attempts
hit the stall in both directions (13-55 ticks/s vs ~600 free; the battery
verified healthy at 8.872 V). The stall guard aborted; the motors float;
the turret rests at encoder ~19771 (155° CW of camera-forward) awaiting
physical cable freeing. Root causes + the v2 rules (the absolute envelope,
the in-daemon stall detection, the dedicated refresh stream) captured in
[sources/2026-10-25-turret-cable-incident.md](sources/2026-10-25-turret-cable-incident.md).
The motion parity itself was PROVEN in the same session (the motord 602/s
vs the v1 612/s at pwm 82; the v1 swing repeatability 6 ticks).

## [2026-10-25] progress | Phase 1 motord: read+motion parity with v1 oracle, deadman verified

`robot/` Rust workspace (brickpi protocol crate + rpc + motord + robotctl,
zero-dep except libc, built on the Pi in 2 min). The golden tests pin the
framing/checksum/bit-packing to BrickPi.py's own logic. The differential
probe (testing/motord_parity_probe.py) achieved **exact encoder parity**
(A=-7500 B=0 C=297 D=8914 — bit-for-bit vs the oracle) after fixing a
decode-order bug (the firmware sends ALL count fields, THEN all value
fields — hand-decoding the raw dump proved it; the "encoder jump" was our
bug, the robot never moved). Motion parity: the same PWM-51 twitch gives
315 (motord) vs 289 (v1) ticks. The firmware deadman (TIMEOUT_SETTINGS,
300 ms) verified: SIGKILL mid-drive → the motion stops within the window.
The drive rate corrected to ~6-8 ticks/s per PWM unit (the old 1.16 was a
units error; the v5 CSV + both twitches agree). Remaining in Phase 1: the
turret parity, the estop drill, the turret homing intent, the probe-shim
acceptance. bd koc-v2-motord-driver.

## [2026-10-25] decision | v2 implementation plan written; all six open questions resolved

[doc/plans/2026-10-25-koc-v2-implementation.md](plans/2026-10-25-koc-v2-implementation.md):
Rust motord (serialport-rs, firmware deadman, E_STOP-on-crash) + camerad
(hand-rolled libfreenect FFI, demand-driven) + robotd WS gateway
(JSON-RPC 2.0 on UDS locally, WebSocket remotely), Raspbian stretch stays
for v2.0 (cross-compiled armv7), CPU INT8 perception, RL out of scope.
Five phases, each gated by probe parity against the real robot; the
measured constants (161 ticks/cm, 125 ticks/deg, the backlash) are the
motord contract. Awaiting user approval before any v2 code (bd koc-v2-plan).

## [2026-10-25] progress | Drive odometry calibrated: 161.0 ± 0.2 ticks/cm

The sonar written off (koc-hw-sonar-dead); the mission re-run on the kinect
oracle with 20 cm encoder-driven legs — **three legs agree to 0.2%:
161.0 ± 0.2 ticks/cm of travel**, the drivetrain backlash/slip under
0.4 cm per 40 cm round trip, GoForward = toward the obstacle (the left
encoder negative, the right positive). The kinect recovery waits (~16 s
per measurement) covered the post-motion USB respawns with zero losses.
Raw: [sources/2026-10-25-drive-ratio-run.md](sources/2026-10-25-drive-ratio-run.md)
(v5 section). koc-drive-ratio-sweep closed with the results.

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
