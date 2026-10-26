# Status

Current progress snapshot — the narrative complement to `bd status`. Refresh on
any status change and during each [wiki-lint](runbooks/wiki-lint.md) pass. For
the live work queue, run `bd ready` and `bd status`.

_Last updated: 2026-10-26_

## In progress

- `koc-v2-motord-driver` (Phase 1 of the
  [v2 plan](plans/2026-10-25-koc-v2-implementation.md)): read/motion parity
  done; snapshot starvation fixed 2026-10-26. Remaining: homing intent,
  in-daemon cable envelope + stall detection, probe-shim acceptance.

## Done recently

- 2026-10-26: turret re-centered on the obstacle by Kinect at **C≈42298**
  (bearing +0.10°); evidence for ~42000 ticks per turret turn — see
  [turret centering run](sources/2026-10-26-turret-centering-run.md).
- 2026-10-25: motord Phase 1 parity vs BrickPi.py; turret cable incident
  ([capture](sources/2026-10-25-turret-cable-incident.md)); drive odometry
  161.0 ticks/cm.

## Blocked / waiting

- User visual check that the turret looks straight ahead.
- Cable wrap is about one full turn relative to C=297; unwinding needs a
  360° move, which needs explicit user approval.

## Next up

- Confirm the turret ratio (~116.7 vs 125 ticks/°) with an independent
  measurement before any absolute-position targets.
- `koc-v2-turret-homing`, then the in-daemon cable envelope.

## Related

- [goals.md](goals.md) · [log.md](log.md) · [index.md](index.md)
