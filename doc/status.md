# Status

Current progress snapshot — the narrative complement to `bd status`. Refresh on
any status change and during each [wiki-lint](runbooks/wiki-lint.md) pass. For
the live work queue, run `bd ready` and `bd status`.

_Last updated: 2026-10-26_

## In progress

- `koc-v2-motord-driver` (Phase 1 of the
  [v2 plan](plans/2026-10-25-koc-v2-implementation.md)): read/motion parity
  done; snapshot starvation fixed; ±180° cable envelope enforced. Remaining:
  homing intent, stall detection, probe-shim acceptance.

## Done recently

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

## Robot state

Turret at C≈42308 (envelope center 42298), v1 server running, motord
stopped. Robot 0.55 m (Kinect) from the obstacle ahead, 11 cm closer than
at the start of the drive re-run.

## Next up

- Count the drive sprocket and gear teeth to confirm the inferred drive
  gearing; fix the drive-ratio probe's at-stop tick counting
  (`koc-drive-ratio-probe-coast`).
- Confirm turret ticks per degree (two estimates in
  [Measured constants](architecture/robot-hardware.md#measured-constants)) with an independent
  measurement before any absolute-position targets.
- `koc-v2-turret-homing`: a homing landmark would let a locked turret
  re-reference without a user check.

## Related

- [goals.md](goals.md) · [log.md](log.md) · [index.md](index.md)
