# Microduck (Pollen Robotics × Hugging Face) — Research Capture

**Date:** 2026-10-24
**Question:** What is the NVIDIA-shown Microduck robot — its hardware spec, and what
software runs on it?
**Method:** Web research (product page, Hugging Face engineering blog, community
coverage) plus shallow clones of the relevant repositories into `external/`
(manifest: [`external/readme.md`](../../external/readme.md)).

## What it is

Microduck is a 25 cm, ~800 g open-source bipedal robot by Pollen Robotics and
Hugging Face, unveiled on stage by Jensen Huang at NVIDIA GTC Berlin (October 2026).
Every behaviour it ships with is a neural policy trained in simulation (MuJoCo /
Isaac Lab + Newton), exported to ONNX, and run on the robot at 50 Hz. The full
stack — SDK, simulation, RL training, OS — is Apache-2.0 on GitHub. Pre-orders
opened 27 August 2026 at $399 (shipping targeted December 2026); four colourways.

Sources: [product page](https://pollen-robotics.com/microduck/),
[HF sim-to-real blog](https://huggingface.co/blog/nvidia/microduck-isaac-lab-sim-to-real),
[awesome-microduck](https://github.com/joeynyc/awesome-microduck).

## Hardware spec

| Item | Value |
|---|---|
| Size / weight | 25 cm tall, ~800 g |
| Actuators | 15 servos on one half-duplex serial bus (Dynamixel-protocol class; Feetech HD-1910 per replica projects) |
| Sensors | Head camera, 8×8 ToF depth matrix (VL53L5/8CX class, on I²C/SPI HAT), two IMUs |
| Compute | Rockchip RK3566 (custom beta PCB; Radxa Zero 3W as dev stand-in); NPU used for INT8 vision models |
| Control loop | 50 Hz onboard policy loop (61 obs → 14 joint positions) |
| In the box | Robot, battery, USB-C cable, game controller (charger/dev/accessory packs extra: $39/$119/$39) |
| Moves shipped | Walk, sit & stand, kick, grab (beak), roller skating, self-recovery — each a swappable ONNX policy; ten published on the Hub as `microduck-policies` |
| Not open | Hardware (no BOM/CAD/PCB); MJCF model + STL meshes are public |

## Software running on the robot

Two layers: a Yocto-built OS and a set of Rust daemons.

### Microduck OS (`external/microduck_yocto`)

Yocto 6.0 *wrynose* on the Rockchip vendor BSP (kernel 6.1), built with kas. Boots
straight into the robot's daemons. A/B rootfs slots updated via signed RAUC
bundles; U-Boot falls back to the healthy slot (retry counters in the U-Boot env),
and a slot only counts as good after a 180 s health check. User data lives on a
separate 8 GiB `data` partition mounted at `/var/lib/robot`, so updates and
rollbacks never touch it. No RTC: TLS fails until network time sync.

### Daemon layer (`external/microduck`)

A single Rust workspace: **seven daemons on one board, one Unix socket each,
talking JSON-RPC 2.0 (NDJSON)**, supervised by systemd:

| Service | Owns |
|---|---|
| `robotd` | **The only process that touches motors.** 50 Hz control loop, Dynamixel bus, kinematics, odometry, ONNX policy runtime, safety (fall detection, joint/thermal limits), `robot.health` |
| `configd` | Wifi (drives NetworkManager over D-Bus), robot identity/name, pairing PIN, gamepad bonding |
| `updaterd` | Signed releases under `/opt/robot/daemon/releases/<ver>/`, atomic `current` symlink swap, health-gated auto-rollback, boot counter |
| `btd` | BLE transport (phone) — a *subset* of the same API; owns nothing |
| `padd` / `netpadd` | Gamepad transports (USB/BLE / UDP on LAN); own nothing |
| `mediad` | Camera + mic pipeline, WebRTC (video tracks + `control`/`teleop` data channels); the remote gateway; runs perception next to the camera |
| `tofd` | Publishes the 8×8 depth matrix; reads nothing |
| `robotctl` / `duckctl` | CLI over every socket; `duckctl` works over Bluetooth with no network |

Design invariants worth copying: `btd`/`configd`/`updaterd` survive a dead
`robotd` (recovery path); clients send **intents, never motor writes**; the
control loop never blocks on another service (last-value-wins caches); one
writer per piece of state; deadman/heartbeat stops the robot when commands stop
arriving; control plane (JSON-RPC on UDS) never carries media frames — perception
publishes *features*, not frames.

Policy distribution: `robotctl policy list|load|add|reset` installs `.onnx` +
schema-2 `manifest.json` from Hugging Face Hub repos. Onboard vision
(`duck-detect`) runs a duck detector as INT8 RKNN on the RK3566 NPU.

### Training stack (off-robot)

- `external/microduck_rl`: mjlab (MuJoCo Warp) + PPO, BAM servo actuator models,
  backlash simulation, domain randomization (mass/CoM, friction, encoder offsets,
  battery sag, latency, per-joint backlash). CUDA GPU required.
- `external/IsaacLab`: Isaac Lab 3.0 contrib tasks `IsaacContrib-Velocity-{Flat,Rough}-MicroDuck`
  (Newton MJWarp solver, RSL-RL). Trains 4096 parallel envs (1.25M steps/s on
  16 GPUs); playback exports `policy.pt` + `policy.onnx` for the onboard runtime.
- **Microduck Arena** (HF Space): server-side validation of submitted policies
  (61 obs / 14 actions / ≤64 MiB) on fixed courses with perturbed seeds.

## Cloned repositories (manifest detail)

All shallow (`--depth 1`), recorded by commit; see [`external/readme.md`](../../external/readme.md).

| Clone | Commit | Size | Notes |
|---|---|---|---|
| `pollen-robotics/microduck` | `942e58e` | 14 MB | The robot's brain: daemons, `robotctl`, `docs/design/` (excellent architecture write-ups), cheatsheets |
| `pollen-robotics/microduck_rl` | `b02fdea` | 35 MB | RL training envs (mjlab/MuJoCo + PPO) |
| `pollen-robotics/microduck_yocto` | `9169123` | 1.5 MB | Microduck OS: Yocto layers, A/B update machinery |
| `joeynyc/awesome-microduck` | `fcd4948` | 372 KB | Community index: spec summary, every ecosystem project, coverage links |
| `isaac-sim/IsaacLab` | `88f4896` | 95 MB | Isaac Lab 3.0; Microduck tasks in `source/isaaclab_tasks/isaaclab_tasks/contrib/microduck/` |

Skipped (noted for completeness): `newton-physics/newton` (physics engine one
level down the training dependency tree — only needed to train locally),
`pollen-robotics/microduck-arena` (competition harness).

## Relevance to K.O.C

K.O.C and Microduck solve the same shape of problem (remote-controlled robot,
camera stream, motor control, telemetry) with different tools — K.O.C: RPi 3 +
BrickPi + Kinect + ZeroMQ/pickle; Microduck: RK3566 + serial servo bus + Rust
daemons on UDS/JSON-RPC. Transferable patterns:

1. **Intents, not motor writes** — K.O.C's `CommandReceiver` already translates
   high-level commands; Microduck makes the safety layer inside the motor owner
   authoritative. Same idea, stricter.
2. **Deadman/heartbeat** — K.O.C's `TelemetryClient` timeout ↔ Microduck's
   `robotd` stopping on lost heartbeat.
3. **Control vs data plane** — K.O.C multiplexes video + telemetry on one ZMQ PUB
   socket; Microduck never lets frames cross the control plane.
4. **Features, not frames** — perception next to the camera publishing derived
   features instead of shipping raw frames to the controller.
5. **Single writer per state / one socket per service** — vs K.O.C's ad-hoc
   aggregator republishing raw PUSH payloads.
6. **Signed A/B updates with health gates** — K.O.C has no update story at all.

## Open questions

- None blocking. The hardware is pre-release (nobody outside Pollen has shipped
  units), so all hardware-facing community tooling is unvalidated on real robots
  — worth remembering when reading ecosystem projects.
