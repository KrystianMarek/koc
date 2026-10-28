# ADR-0001: Pause Active Development of K.O.C

## Status

Accepted

## Date

2026-10-28

## Context

Every electronic part of the robot is past the end of its supported life:
the Kinect (out of production since 2017), the BrickPi+ (superseded in
2017), the NXT motors and sensors (Mindstorms discontinued in 2022), the
NCS1 (SDK archived in 2019), Raspbian 9 and Python 3.5. See the
[lifecycle capture](../sources/2026-10-28-hardware-lifecycle.md).

Recent sessions went mostly into keeping this hardware usable: the turret
cable wrap, the Kinect USB storms on the shared USB 2.0 bus, a sonar that
looked dead, and encoder units. The v2 plan's later phases (`camerad`,
`robotd`, perception) would be new work on the same hardware.

The user has moved active development to a different project.

## Decision

Pause K.O.C. Leave it in a state that reflects what is known about the
physical and software stack:

- The wiki records the hardware facts, the measured constants, the turret
  safety rules and the open questions as of 2026-10-28.
- v1 stays the working stack; `motord` (v2 Phase 1) stays as built.
- Every open `bd` ticket is deferred with a handoff comment; nothing is in
  progress.
- No further hardware, OS or v2 work is planned.

## Consequences

### Positive

- No more effort spent on end-of-life hardware.
- Anyone resuming starts from the [status page](../status.md) resume
  checklist instead of re-deriving the robot's state.

### Negative

- v2 stops at a partial Phase 1: no homing intent, no stall detection, no
  `camerad`; v1 (Python 3.5, ZeroMQ + pickle) remains the only full stack.
- Open measurements (drive gear teeth, turret ticks per degree) stay
  unconfirmed.

### Risks

- After a BrickPi power cycle the encoders read 0 and both turret guards
  lock; resuming needs the [turret centering runbook](../runbooks/turret-centering.md).
- Hardware may degrade while idle (battery, 20-year-old sensors, track
  links).

## Alternatives Considered

- **Continue v2 on the current hardware** (`camerad`, `robotd`,
  perception): rejected; it invests further in end-of-life parts.
- **Replace the electronics** (newer computer, current depth camera,
  BrickPi3): not pursued now; it would be a new hardware project with its
  own plan.

## References

- [Hardware lifecycle capture](../sources/2026-10-28-hardware-lifecycle.md)
- [v2 implementation plan](../plans/2026-10-25-koc-v2-implementation.md)
- [Status](../status.md) · [Robot hardware](../architecture/robot-hardware.md)
