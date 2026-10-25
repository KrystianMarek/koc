# Plan: K.O.C v2 — Microduck-Aligned Stack Implementation

## Objective

Rebuild the robot's software as small single-purpose Rust daemons over
JSON-RPC 2.0, replacing the v1 ZeroMQ/pickle stack, while the v1 stack keeps
running until each phase passes probe parity against the real robot. The
pattern source is Microduck (`external/microduck/docs/design/architecture.md`);
the hardware facts are already decoded and measured (see
[brickpi-interface](../architecture/brickpi-interface.md),
[robot-hardware](../architecture/robot-hardware.md)).

## Resolved Decisions (the open questions from the vision doc)

| # | Question | Decision | Rationale |
|---|---|---|---|
| 1 | BrickPi driver | **Rust `motord` on `serialport-rs`**, protocol per brickpi-interface.md; firmware deadman (`TIMEOUT_SETTINGS`) enabled; `E_STOP` on Drop/panic; US-sensor I2C workaround ported verbatim; v1 `BrickPi.py` is the differential-test oracle | Protocol is small (5 message types, one checksummed frame per ATmega per cycle) and frozen (hardware discontinued — no upstream to track) |
| 2 | Kinect capture | **Rust `camerad` with a hand-rolled FFI over the ~15 libfreenect C functions** (no C sidecar, no 2015-era `freenect` crate) | One runtime, one build system, one supervision story; the C API surface is tiny; the fragile part of v1 was the Python bindings + fork, not the C library |
| 3 | Client↔robot transport | **JSON-RPC 2.0 over UDS on-robot; JSON-RPC 2.0 over WebSocket (tokio-tungstenite) for the remote client.** Same message schema on both transports; the WS gateway is a thin task inside the daemon supervisor, not a new daemon | Local consumers (probes, robotctl, other daemons) must not need TCP; the GUI/browser needs network; one schema keeps the client adapter trivial. ZMQ/pickle is retired in phase 3, not wrapped |
| 4 | OS path | **Stay on Raspbian stretch for v2.0.** Rust cross-compiles (`armv7-unknown-linux-gnueabihf`, or musl for static binaries); the robot runs compiled artifacts, no toolchain on-device | Python 3.5 pins die with the Rust rewrite; an OS upgrade is its own high-risk project and buys nothing v2.0 needs. Revisit (Yocto A/B à la `microduck_yocto`) only when the update story demands it |
| 5 | Perception accelerator | **CPU INT8 on the RPi 3 is the default**; accelerators behind a pluggable trait (`InferenceBackend`). The NCS1 stays dead; no new hardware purchase in v2.0 | NCS1 SDK archived, Coral EOL 2026, Hailo needs PCIe the RPi 3 lacks (see [NCS state](../sources/2026-10-24-ncs-state.md)) |
| 6 | RL / learned policies | **Out of scope** | Differential-drive rover; Microduck's RL core solves a biped's problem we don't have. We adopt the software stack patterns |

## Architecture

Robot-side Rust workspace (`robot/`), one binary per daemon, each speaking
NDJSON JSON-RPC 2.0 on its UDS socket, systemd-supervised:

| Daemon | Owns | Replaces |
|---|---|---|
| `motord` | BrickPi+ UART: PORT_A/D (drive), PORT_C (turret), PORT_1 (color), PORT_4 (sonar), battery; 50–100 Hz `VALUES` loop; intents in → encoder/sensor state out; deadman; safety authority (the only motor writer) | `brick_pi_wrapper.py` |
| `camerad` | Kinect RGB+depth capture (libfreenect FFI), throttled, demand-driven (stream only while a consumer subscribes), self-healing re-open on sync timeouts; publishes derived features (blob distance, not raw frames) to the control plane | `kinect_process.py` |
| `robotd` | The supervisor + WS gateway: exposes motord/camerad state over WebSocket for the remote client; health aggregation; crash ⇒ `E_STOP` to motord | `server.py` |
| `robotctl` | The one CLI that must work on a broken robot (status, estop, logs, stream on/off) | ad-hoc ssh |
| `configd` / `updaterd` | Phase 4 (below) | — |

Cross-cutting invariants (from Microduck, non-negotiable):

- **Intents, never motor writes** — clients send `{"intent": "turret_rotate", "deg_s": 15}`; motord owns PWM.
- **One writer per state** — only motord touches the BrickPi; only camerad touches the Kinect.
- **Control plane never carries frames** — perception publishes features (blob distance, obstacle presence); raw frames go only to subscribed stream consumers.
- **Never block the control loop on another daemon** — last-value-wins caches on both sides.
- **Deadman at two layers** — the BrickPi firmware `TIMEOUT_SETTINGS` (hardware, set to ~3× the motord loop period) + motord's own intent expiry; motors float on daemon crash via Drop/panic hooks.

## Measured constants contract (v2 must reproduce; sources in robot-hardware.md)

- Drive odometry: **161.0 ± 0.2 ticks/cm**; GoForward = LEFT encoder negative, RIGHT positive; drivetrain backlash < 0.4 cm per 40 cm round trip.
- Turret: **~125 ticks/turret-degree (±10%)**; approach-direction backlash **~252 ticks** — homing must approach from one direction or model it.
- Drive PWM→speed is non-linear and gear-deep: ~1.16 ticks/s per speed unit at speed 45-60; calibrate a per-speed table, don't assume linearity.
- Encoder state persists while the BrickPi is powered — never assume 0 after a daemon restart.
- Sonar: PORT_4 presumed dead (20-year-old sensor, reads 255 constantly — bd `koc-hw-sonar-dead`); motord implements the I2C workaround anyway, but nothing may *depend* on sonar data.
- Kinect USB chain: post-motion respawn takes ~13–16 s — camerad's self-heal budget and every probe must tolerate it; the two-hub power chain stays until physically replaced.

## Phases (each ends with probes passing against the real robot)

### Phase 0 — capture & fix ✅ (this session, complete)

Kinect wedge chain fixed (spawn/throttle/self-heal), fd leak fixed, sync.sh
fixed, telemetry/depth bugs fixed, drive odometry + turret constants
measured. v1 is healthy enough to serve as the test oracle.

### Phase 1 — `motord` + differential parity harness

- [ ] Workspace skeleton: `robot/` cargo workspace, `motord` binary, shared `rpc` crate (NDJSON JSON-RPC over UDS), `robotctl` stub.
- [ ] BrickPi protocol module: framing, checksum, the 5 message types; unit tests against golden frames captured from `BrickPi.py`.
- [ ] Differential harness on the robot: v1 server and motord alternate the same scripted commands (twitch, rotate, sensor reads); assert encoder deltas agree within tolerance (the `differential-bootstrap` pattern; `BrickPi.py` is the oracle).
- [ ] Firmware deadman enabled + verified (motors float when motord is SIGKILLed).
- [ ] Intents implemented: drive (left/right %, or arc), turret_rotate, turret_home (color-landmark + approach-direction aware — closes `koc-v2-turret-homing`), estop, sensor snapshot.
- [ ] Acceptance: the existing probes (`turret_swing90_probe.py`, `drive_ratio_probe.py`) re-run against a motord-backed shim and reproduce their published constants.

### Phase 2 — `camerad`

- [ ] FFI module over the ~15 libfreenect functions (device open, video/depth callbacks, tilt motor/state); `bindgen` optional, hand-rolled acceptable.
- [ ] Throttled, demand-driven capture (stream only with ≥1 subscriber; the v1 lesson: 10 fps cap, spawn isolation, re-open on sync timeouts).
- [ ] Publishes: blob-distance feature (the `frame_processor.py` math, tan-domain validated: raw 300..1008) + optional raw frame stream to subscribers.
- [ ] Acceptance: 30-minute soak with zero wedges; the post-motion recovery ≤ v1's ~16 s; `kinect_stream_probe.py` parity.

### Phase 3 — `robotd` + client adapter; retire ZMQ

- [ ] `robotd`: supervises motord/camerad UDS sockets, aggregates health, exposes the WS gateway with the same schema.
- [ ] `robotctl`: status, estop, stream on/off, journal tail — the broken-robot CLI.
- [ ] Client: a thin `RobotConnection` adapter (same intents) re-pointing the PyQt5 GUI from ZMQ/pickle to WS/JSON-RPC; the v1 GUI survives until a web teleop page replaces it (later, not in this plan).
- [ ] Acceptance: a full teleop session (drive, turret, camera, tilt) over WS with latency indistinguishable from v1; ZMQ path disabled on the robot (`systemctl disable koc-v1`), revertible for one release.

### Phase 4 — operations: systemd, `configd`, `updaterd`

- [ ] systemd units (Restart=always, the deadman as the safety net), journald structured logs.
- [ ] `configd`: NetworkManager-based identity/pairing (reachable when motord is dead — Microduck's rule).
- [ ] `updaterd`: git-tagged deploys with a health gate (motord heartbeat + camerad frame rate) and automatic rollback on gate failure; A/B partitions explicitly deferred.
- [ ] Acceptance: an update pushed over WS or scp self-applies and rolls back on a failed health gate, with the robot reachable throughout.

### Phase 5 — perception (CPU INT8)

- [ ] `InferenceBackend` trait; CPU INT8 reference backend (a tiny one-class detector, `duck-detect`-sized to the job).
- [ ] Feature publication: detections as intents-compatible events (e.g. `obstacle_seen {bearing, distance}`), never frames on the control plane.
- [ ] Acceptance: ≥2 fps detection on the RPi 3 without starving motord's loop or camerad's stream (measured, not assumed).

## Dependencies

- Phase 1 needs nothing new (the protocol is decoded; the constants are measured).
- Phase 2 needs the physical hub chain decision (the user may replace the daisy chain with one powered hub — recommended but not blocking; camerad's self-heal is designed around it either way).
- Phase 5 is blocked until phases 1–4 land; the accelerator question stays open until then by design.

## Explicitly out of scope

RL policies, new SBC/hardware purchases, OS upgrade, the web teleop GUI, sonar revival (a physical check remains the user's optional task), Kinect audio.

## Risks

- **The BrickPi UART is the Pi's mini-UART** (`ttyS0`, clock-patched) — motord must open it with the exact baud/clock assumptions or nothing talks. Mitigation: the golden-frame tests + the differential harness before any motor moves under Rust.
- **armv7 cross-compilation of libfreenect FFI** — freenect is already installed on the robot; motord/camerad link against the robot's existing `.so`s (build on-device is the fallback for camerad only).
- **Single USB root bus contention** (Kinect + Ethernet + everything) — demand-driven capture is the mitigation; if storms persist, the powered-hub swap is the physical fix.

## Success criteria

- The probes reproduce the measured constants through the v2 stack (odometry, turret ratio, swing reliability).
- A full teleop session over the WS gateway at v1-comparable latency.
- `SIGKILL` on any daemon leaves the motors floating within the deadman window.
- v1 is disabled but one command away from restoration for one release cycle, then deleted.

## Related

- [Vision](../vision/v2-microduck-stack.md) · [BrickPi interface](../architecture/brickpi-interface.md) · [Robot hardware](../architecture/robot-hardware.md) · [v1 assessment](../development/2026-10-24-koc-v1-code-assessment.md) · bd epic `koc-v2`
