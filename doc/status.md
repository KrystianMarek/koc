# Status

Current progress snapshot — the narrative complement to `bd status`. Refresh on
any status change and during each [wiki-lint](runbooks/wiki-lint.md) pass. For
the live work queue, run `bd ready` and `bd status`.

_Last updated: 2026-10-28_

## Project state: paused

**Active development is paused since 2026-10-28**
([ADR-0001](decisions/ADR-0001-pause-active-development.md)): every
electronic part of the robot is past its supported life (see the
[lifecycle capture](sources/2026-10-28-hardware-lifecycle.md)). Nothing is
in progress. Every open `bd` ticket is deferred with a handoff comment
(`bd list --status deferred`).

## Software stack as left

| Part | State |
|---|---|
| v1 server + client (`server.py`, `app/`, `gui.py`) | Working stack. Python 3.5 on the robot, ZeroMQ + pickle. Kinect capture throttled and self-healing; the fd leak fixed; ±180° turret cable guard |
| v2 `motord` (`robot/`) | Phase 1 partial: BrickPi+ read/motion parity with `BrickPi.py`, firmware deadman, drive/turret/estop/snapshot intents, ±180° cable guard. Not done: homing intent, stall detection, probe-shim acceptance, socket cleanup on exit |
| v2 `camerad`, `robotd`, `configd`, `updaterd`, perception | Not started |
| Probes (`testing/`) | Working; some still print ratios assuming 360 ticks/rev (`koc-probes-encoder-units`) |
| Tests | `python3 -m unittest testing.test_turret_guard` (11), `cargo test` in `robot/` (7); all passed on 2026-10-26 |

## Physical stack as known

Port map, measured constants and behavior:
[robot hardware](architecture/robot-hardware.md). Open physical questions:

- Drive gearing is inferred (12-tooth driving 20-tooth into a 6-tooth
  sprocket); the teeth were never counted (`koc-drive-gear-count`).
- Turret ticks per degree has two estimates 7 % apart
  (`koc-turret-ratio-confirm`).
- The Kinect "Stream 70" storms are physical (two-hub chain on the shared
  USB 2.0 bus) (`koc-hw-kinect-wedge`).
- The Kinect accelerometer reads ~0 at level (`koc-hw-kinect-accel-axes`).

## Robot state

**Last observed 2026-10-26**: v1 server running, motord stopped, motors
stopped, turret at C≈42308 (envelope center 42298), robot 0.55 m (Kinect)
from the obstacle ahead. **On 2026-10-28 the robot did not answer** ssh or
ping; it is probably powered off or off the network.

## Resume checklist

1. Read [AGENTS.md](../AGENTS.md), [agent lessons](development/agent-lessons.md)
   and [robot deployment](development/robot-deployment.md).
2. Power the robot, then check it answers:
   `ssh -o BatchMode=yes pi@192.168.10.187 true`.
3. Read the turret state before any motion:
   `$P testing/turret_envelope.py show`. If the BrickPi lost power, the
   encoders read 0 and the guards lock: follow the
   [turret centering runbook](runbooks/turret-centering.md) and
   re-reference only after the user confirms where the turret faces.
4. Run the tests (see the table above) on the robot's Python 3.5 and with
   `cargo test --release` on the robot.
5. Pick work from `bd list --status deferred`; un-defer it with
   `bd update <id> --status open`.

## Done before the pause

- 2026-10-26: **drive odometry corrected** (the first run missed the coast
  after each stop), drive gearing inferred, and the encoder resolution
  corrected (older pages assumed half of it). The values are in
  [Measured constants](architecture/robot-hardware.md#measured-constants); sonar agrees at rest — see
  [drive ratio re-run](sources/2026-10-26-drive-ratio-rerun.md).
- 2026-10-26: gearing and odometry numbers consolidated into that one table;
  other pages link to it.
- 2026-10-26: **turret cable envelope**: the turret cannot turn more than
  180° either way from camera-forward. The v1 server and motord both enforce
  it from `~/.koc/turret.json` and lock the turret when its position is
  unknown — see the [envelope plan](plans/2026-10-26-turret-envelope.md),
  [envelope run](sources/2026-10-26-turret-envelope-run.md) and
  [turret centering runbook](runbooks/turret-centering.md).
- 2026-10-26: user confirmed the turret faces camera-forward at **C=42298**
  and the cables are fine there (this is the envelope center).
- 2026-10-26: AGENTS.md rewritten for this project; agent lessons collected
  in [development/agent-lessons.md](development/agent-lessons.md).
- 2026-10-26: turret re-centered by Kinect; new evidence on turret ticks per
  turret turn — see [turret centering run](sources/2026-10-26-turret-centering-run.md).
- 2026-10-25: motord Phase 1 parity vs BrickPi.py; turret cable incident
  ([capture](sources/2026-10-25-turret-cable-incident.md)); first drive
  odometry run (since corrected).

## Related

- [goals.md](goals.md) · [log.md](log.md) · [index.md](index.md)
