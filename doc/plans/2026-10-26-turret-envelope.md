# Plan: Turret Cable Envelope (±180°) Enforcement

## Objective

Harden the turret rule (user, 2026-10-26): **never turn the turret more than
180° in either direction from camera-forward**, which the user confirmed is
also the cable-neutral position (C≈42298). Enforce it where the motor is
written, so no client, probe or GUI can break it.

## Design

- **State file** `~/.koc/turret.json` on the robot:
  `{"center": <ticks>, "half_range": 21000, "last": <ticks>}`.
  21000 ticks = 180° at the lower measured ratio (116.7 ticks/°) and 168° at
  125 ticks/°, so the cap holds whichever ratio is right.
- **One guard, two writers.** The same rules in the v1 server
  (`app/server/turret_guard.py`, used by `BrickPiWrapper`) and in `motord`
  (`robot/motord/src/guard.rs`):
  1. Missing/invalid file → **locked** (turret speed forced to 0).
  2. First encoder read differs from `last` by > 400 ticks → **locked**
     (BrickPi power cycle or hand move; the facing is unknown).
  3. Otherwise a turret command is zeroed when the encoder is within 800 ticks
     (300 in the first draft; see the notes) of `center ± half_range` and the
     command points outward.
  4. `last` is persisted (atomic rename) at most every 0.25 s while it
     changes by ≥ 20 ticks.
- **motord** reports the guard state in `snapshot` and rejects `turret`
  intents that are locked or outward at the limit.
- **Re-reference** tool `testing/turret_envelope.py`: `show`, and
  `set-center --encoder N [--current-deg X]` (X = degrees left of
  camera-forward, when the turret is not at center). Daemons pick it up on
  restart.
- Probe modes that write `BrickPi.MotorSpeed` directly use the Python guard;
  the obsolete `return` mode (default target 297, now outside the envelope)
  is removed and `rotate` requires an explicit target.

## Tasks

- [x] Python guard + unit tests (Python 3.5 compatible); wire into `BrickPiWrapper`
- [x] Rust guard + unit tests; wire into motord loop, `turret` RPC, `snapshot`
- [x] `turret_envelope.py`; guard the probe's direct-BrickPi modes
- [x] Deploy; initialise the state file at the confirmed center
- [x] Live checks with a temporary small half-range (both daemons stop
      the turret near the limit), a forced discontinuity (locked), then restore
- [x] Docs: AGENTS.md hard rule, runbook, hardware page

## Implementation notes

- **Stop margin raised from 300 to 800 ticks** after measuring the v1
  server's overshoot: up to 458 ticks past the stop point at pwm 250 (10 Hz
  loop plus coast); motord overshoots ~15 ticks at 16 %. The worst case is
  then ~20700 ticks from center (177° at 116.7 ticks/°). A temporary
  half-range must now exceed 800 (1000 used for the checks).
- **Added rule: no turret motion on a stale reading.** After a failed
  encoder exchange the guard writes 0 until the next good read.
- motord logs a blocked command once per episode; the `turret` RPC returns
  error -2 (`turret blocked: …`) for locked and limit cases and zeroes the
  intent.
- `testing/brickpi/main.py` (legacy curses control) also writes the turret
  directly; all its exchanges now pass through the Python guard.
- Measurements: [envelope run](../sources/2026-10-26-turret-envelope-run.md).

## Success Criteria

Both daemons stop a turret move at the temporary limit and refuse motion when
locked; unit tests pass on the dev machine (and the Python ones on the robot's
Python 3.5); the real state file holds center = the confirmed C.

## Related

- [Turret centering fixes](2026-10-26-turret-centering-fixes.md)
- [Turret cable incident](../sources/2026-10-25-turret-cable-incident.md)
- [Envelope run](../sources/2026-10-26-turret-envelope-run.md) · [Turret centering runbook](../runbooks/turret-centering.md)
