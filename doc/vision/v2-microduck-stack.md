# V2: Microduck-Aligned Software Stack

**Paused 2026-10-28** during Phase 1 of the
[v2 plan](../plans/2026-10-25-koc-v2-implementation.md) — see
[ADR-0001](../decisions/ADR-0001-pause-active-development.md).

## Premise

Rebuild K.O.C's software as a Microduck-style stack — small single-purpose
daemons talking JSON-RPC 2.0 over Unix sockets, intents-not-motor-writes,
features-not-frames, health-gated updates — while keeping the existing
hardware platform (RPi 3 + BrickPi+ + Kinect) for v2. v1's ZeroMQ/pickle
transport is replaced, not wrapped.

## Motivation

v1 works (see [code assessment](../development/2026-10-24-koc-v1-code-assessment.md))
but has prototype-grade mechanics: pickle transport (RCE surface), command
types overloaded onto telemetry, a server that wedges silently under the
unthrottled Kinect process, and no update or test story. Microduck solved the
same problem class (remote-controlled robot, camera stream, motor control,
telemetry) with independently-validated patterns we can adopt wholesale; its
full source is cloned read-only in `external/` (manifest: `external/readme.md`).

## Sketch

Robot-side daemons (Rust workspace, one UDS + JSON-RPC 2.0 NDJSON each,
systemd-supervised), mapped onto our hardware:

| Daemon | Owns | K.O.C mapping |
|---|---|---|
| `motord` | BrickPi+ UART (`/dev/ttyS0`): motors PORT_A/D/C, sensors PORT_1/4, battery; 50–100 Hz loop; safety authority; deadman; intents in, encoder/sensor state out | replaces `BrickPiWrapper` |
| `camerad` | Kinect capture (libfreenect FFI), **throttled**, publishes frames + derived features; owns no motors | replaces `KinectProcess` |
| `configd` | wifi/identity/pairing via NetworkManager; reachable when `motord` is dead | new |
| `updaterd` | health-gated releases (start simple: systemd unit + git-tagged deploys; A/B later) | new |
| `robotctl` | the one CLI that must work on a broken robot | new |

Cross-cutting rules adopted from `external/microduck/docs/design/architecture.md`:
clients send **intents** ("rotate turret at 30%") never motor writes; the
control loop never blocks on another daemon (last-value-wins caches); **one
writer per piece of state**; control plane never carries frames — perception
publishes features; deadman/heartbeat stops motors when commands stop.

Client-side: v1's PyQt5 GUI is re-pointed at the new API behind a thin adapter
so the robot can be developed headlessly (our probes become the test harness);
web teleop (browser + gamepad) is the later direction, as Microduck does.

Indicative phasing (each phase ends with the probes passing against the real
robot):

1. **Phase 0** — capture & fix (current session output): kinect wedge, sync
   script, commit baseline.
2. **Phase 1** — `motord` prototype + probe parity tests (twitch/deadman/
   encoder behavior pinned by tests before rewrite).
3. **Phase 2** — `camerad` (throttled capture; stream parity with v1).
4. **Phase 3** — client adapter + `robotctl`; retire ZMQ pickle path.
5. **Phase 4** — update story (systemd units → signed releases).
6. **Phase 5** (optional) — onboard perception models (Microduck's `duck-detect`
   analog): the robot's USB "NPU" is the legacy Intel NCS1 (boot-mode, dead
   SDK — see [NCS state](../sources/2026-10-24-ncs-state.md)); default to CPU
   INT8 inference on the RPi 3 with accelerators as a pluggable backend.

## Open Questions

- **BrickPi driver in Rust**: protocol now fully decoded — see
  [brickpi-interface](../architecture/brickpi-interface.md). The board speaks
  **UART** (500 kbaud on `/dev/ttyS0`, two ATmega3250s at addresses 1/2,
  checksummed frames), *not* I2C as widely assumed. Recommendation: Rust
  driver on `serialport-rs`, enable the firmware deadman
  (`TIMEOUT_SETTINGS`), wire `E_STOP` to crash handlers, differential-test
  against `BrickPi.py` as the oracle. Confirm in the plan.
- **Kinect capture in Rust**: `freenect` crates exist but are thin (2015-era);
  the C API surface needed is ~15 functions
  ([kinect-interface](../architecture/kinect-interface.md)) — a minimal FFI
  or a C sidecar are both viable. Tied to the same decision.
- **Perception accelerator**: the NCS1 (Myriad 2, ~100 GFLOPS FP16) is
  present but boot-mode with a dead, archived SDK; Coral Edge TPU is EOL
  (2026); Hailo needs PCIe the RPi 3 lacks. Default: CPU INT8 inference for
  small models, keep any accelerator a pluggable backend — see
  [2026-10-24 NCS state](../sources/2026-10-24-ncs-state.md). Decide before
  Phase 5.
- **Client↔robot transport**: UDS is on-robot only; cross-network still needs
  something (keep ZMQ short-term? WebSocket gateway like Microduck's
  rendezvous lane? WebRTC later?).
- **OS path**: stay Raspbian stretch for v2.0 (Python 3.5 pins gone once Rust
  — Rust cross-compiles, robot runs binaries) vs upgrade to current Raspberry
  Pi OS vs Yocto A/B (`microduck_yocto` style, `meta-raspberrypi`) later.
- **RL scope**: Microduck's core is RL policies on a 15-DoF biped; K.O.C is a
  differential-drive rover — learned locomotion is not the win here. V2 uses
  the *software* stack patterns; RL/policies stay out of scope until a task
  justifies them.

## Prior Art / References

- `external/microduck/docs/design/architecture.md` — the pattern source
  (service split, invariants, IPC choice, safety, updates)
- `external/microduck_yocto` — A/B update machinery reference
- [2026-10-24 v1 assessment](../development/2026-10-24-koc-v1-code-assessment.md)
- [Robot hardware](../architecture/robot-hardware.md) — measured dynamics any
  v2 `motord` must reproduce
