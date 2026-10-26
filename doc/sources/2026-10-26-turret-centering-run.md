# Turret Centering Run — 2026-10-26

Raw capture of the session that re-centered the turret after two
probe-caused overshoots. Plan:
[turret centering fixes](../plans/2026-10-26-turret-centering-fixes.md).
Background: [turret cable incident](2026-10-25-turret-cable-incident.md).

## Starting state

- User report: the turret faced ~40° left of center; an obstacle stood
  directly in front of the robot.
- Encoder C=46084 (not 43442 as the last probe line suggested): the old
  `rotate_to` fixed its direction at the start, so after overshooting it kept
  driving the same way until `timeout 90` killed it mid-burst.
- Sonar (PORT_4, chassis-fixed) read a steady 61 — the sensor works.

## Defects found and fixed

| Defect | Effect | Fix |
|---|---|---|
| motord loop held the cache mutex across both UART exchanges **and** the period sleep | `snapshot` starved 8–46 s under motion | exchange into a loop-local copy; lock only to copy in/out |
| Probe `rotate_to` had no position stop inside a 12 s burst and kept its initial direction | overshoots of 1185 and 1247 ticks, then a wrong-way burst | polls position at ~50 Hz, releases at target minus 40 ticks, ±15° per-move cap, stall/latency/time aborts |
| Probe `motord_running()` trusted the socket file | motord's signal exit leaves `/tmp/motord.sock`; the probe then failed with ECONNREFUSED | test with a real connect, unlink a stale socket |
| `pkill -f "python server.p[y]"` in the same ssh command as `python server.py` | pattern matched the remote shell itself; commands died silently (ssh rc 255) | start the server via `$P server.py` so the literal never appears |
| `kinect_bearing.py` averaged the nearest 10 % of pixels across the whole frame | readings jumped to the frame edges (x=46, x=602); not the obstacle | per-column depth profile, sonar-gated ±0.12 m band, largest contiguous run, untrusted when edge-touching; surface-yaw fit as a second cue |

## Moves (motord, speed 16 %)

| Move | From → to (C) | Target error | Duration | Max snapshot latency |
|---|---|---|---|---|
| −15° blind | 46084 → 44216 | +7 ticks | 7.5 s | 0.001 s |
| −10° blind | 44216 → 42972 | +6 ticks | 5.3 s | 0.002 s |
| −3° check | 42972 → 42606 | +9 ticks | 2.3 s | 0.001 s |
| −2.6° final | 42606 → 42298 | +12 ticks | 2.1 s | 0.001 s |

## Kinect readings (sonar reference 0.61 m)

| C | Obstacle columns | Center x | Bearing | Surface yaw | Trust |
|---|---|---|---|---|---|
| 42972 | 192–587 | 389.5 | +6.78° | (not yet computed) | trusted |
| 42606 | 157–547 | 352.0 | +3.13° | +2.61° | trusted |
| 42298 | 126–516 | 321.0 | **+0.10°** | **+0.25°** | trusted |

The obstacle face reads 0.66–0.67 m across the whole run at the end (flat
profile). The −3° step moved the image left (edges −35/−40 px), confirming
the image is not mirrored: x > 320 means the turret points left of the
target; move encoder-negative (right / user CW).

## Derived facts

- **Camera-forward (this obstacle, approached from the left): C ≈ 42298.**
- C=42298 is 42001 ticks above the session-start spot C=297. If that spot
  was also camera-forward, **one turret turn ≈ 42000 ticks ≈ 116.7
  ticks/°**, not 45000 / 125. This explains the original miss: the target
  297+45000 was ~3000 ticks (≈25°) too far left, matching the first Kinect
  reading of +25.7° at C=45215. The −3° step gave ~3.7° of image motion,
  pointing the same way (fewer ticks per degree than 125). Not yet
  confirmed by an independent full-scale measurement.
- **Cable wrap: about one full turn** relative to C=297. At its peak
  (C=46084) the wrap was over one turn. Unwinding needs a 360° move the
  other way, which the user rule forbids without explicit approval.
