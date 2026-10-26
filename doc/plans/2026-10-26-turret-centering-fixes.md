# Plan: Turret Centering Fixes

## Objective

Center the turret on the obstacle straight ahead of the robot after two
probe-caused overshoots. User report (2026-10-26): the turret faces ~40° left
of center at encoder C=43442. Fix the tooling defects found in the audit so
motion stops by position and bearing readings can be trusted.

## Scope

Included: motord cache-lock starvation, probe `rotate_to`, Kinect bearing
tool, one centering session. Excluded: homing intent, in-daemon cable
envelope (still `koc-v2-turret-homing` / `koc-v2-motord-driver`).

## Tasks

- [ ] motord: decode exchanges into a loop-local cache and hold the shared
      cache lock only to copy it; never hold it across `sleep`. (The guard
      lived for the whole loop body, starving `snapshot` 8–46 s.)
- [ ] Probe `rotate_to`: poll position during motion (cheap after the lock
      fix), stop at target minus a coast allowance, cap each call at 15°,
      stall guard on real elapsed time, abort if a snapshot takes >0.5 s,
      direction labels per user convention (positive = left / user CCW).
- [ ] `kinect_bearing.py`: per-column median depth in a central row band,
      obstacle columns = within ±0.10 m of the sonar range, largest
      contiguous run, untrusted if it touches the frame edge.
- [ ] Centering: blind 25° move right (unwinds cable), then Kinect-guided
      steps of at most 3°, confirming the image moves the expected way after
      the first step; user visual check at the end.

## Milestones

1. motord rebuilt on the robot; snapshot latency under motion < 50 ms.
2. Turret within ±1.5° of the obstacle by Kinect, confirmed by the user.

## Dependencies

Obstacle stays ~60 cm in front of the chassis (sonar ~61 confirms).

## Success Criteria

Kinect obstacle segment centered within ±15 px, not edge-touching; user
confirms the turret looks straight ahead; no motion overshoots its target by
more than 1°.

## Related

- [Turret cable incident](../sources/2026-10-25-turret-cable-incident.md)
- [K.O.C v2 implementation](2026-10-25-koc-v2-implementation.md)
