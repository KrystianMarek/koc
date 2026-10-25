# Drive Ratio Mission — Track Break & Repositioned Robot — 2026-10-25

Raw evidence for the drive-ratio mission (bd `koc-drive-ratio`). Probe:
`drive_ratio_probe.py` (v3: kinect-oracle legs — the sonar goes blind during
motion; CSVs at `/tmp/koc_calib/drive_ratio_v2.csv`).

## What happened

1. **Run 1**: the drive worked (~3002 encoder ticks) but the **rear track
   broke mid-experiment** — the sonar went 255 (blind) 6 s into the motion,
   the "backward stall" was the broken track jamming, and the encoders
   lurched sign. **All run-1 data invalid**, including the earlier
   158 ticks/cm estimate (the kinect reading it was derived from was taken
   after the break) and the "rear wall 6 cm" interpretation.
2. The track was repaired; the robot repositioned.

## Valid findings (survive the break and the repositioning)

- **The drive train is heavily geared**: ~970 drive ticks in 18.7 s of
  smooth motion at speed 45 = **52 ticks/s ≈ 1.16 ticks/s per speed unit** —
  ~6× deeper than the turret's 7.2 (which explains the robot's slow,
  torquey tracks). Measured smoothly; the "stall" abort that ended the leg
  was a false positive from assuming the turret's rate.
- **The sonar is blind WHILE the tracks turn**: 255 during motion in both
  runs (with the fixed track too) — drive EMI/vibration breaks the echo.
  At rest it reads steadily (75, then 43-55 at the new position). The
  sonar is an at-rest sensor only.
- **The kinect depth reads fine during motion** (it tracked the direction
  blip) but the chronic USB storms can gap it for seconds — fragile but
  self-healing.

## Current geometry (after the repositioning)

| Sensor | Reading |
|---|---|
| Sonar | **43 cm** steady (99 samples, one value) |
| Kinect nearest-cluster | **0.50 m** (p50 raw 403); valid fraction 0.95 |
| Kinect room behind | 1.43 m (p90) |

The sensors agree (the ~7 cm difference = the mounting offsets). **The
obstacle is too close for a 15 cm forward excursion** (it would end at
~28-35 cm) — the robot needs to move back to ~75-80 cm from the obstacle
before the mission re-runs.

## SUCCESSFUL RUN (v5, kinect oracle, same day after the repositioning)

The sonar written off (koc-hw-sonar-dead); the kinect depth as the sole
oracle (+-1-3 mm at this range per the FrameProcessor docstring), with
~16 s post-motion recovery waits per measurement. The robot repositioned:
the obstacle ~0.77 m dead-ahead (kinect), GoForward drives TOWARD it.

| Leg | Drive ticks | Kinect travel | Ticks/cm |
|---|---|---|---|
| rate blip (1500 ticks) | +1508 | 9.8 cm | 153.6 |
| round 1 away / back | −3097 / +3072 | 19.2 / — | 161.3 / — |
| round 2 away / back | −3074 / +3102 | 19.1 / — | 160.9 / — |
| round 3 away / back | −3106 / +3090 | 19.3 / — | 160.9 / — |

- **Ticks per cm of travel: 161.0 +- 0.2** (the three calibrated legs
  agree to 0.2 percent; the blip's 153.6 is within the kinect's accuracy
  band). THE odometry constant for v2's motord.
- **Round-trip errors: +0.1 / -0.4 / -0.3 cm** — the drivetrain
  backlash/slip is under half a centimeter per 40 cm round trip.
- **Direction**: GoForward = toward the obstacle; the forward motion runs
  the LEFT encoder negative and the RIGHT positive.
- The kinect recovery waits (~16 s per measurement) fully covered the
  post-motion USB respawn cycle - zero measurement losses in ~10 minutes.
- The sign convention: the away legs' ticks are negative (GoBackward);
  the magnitudes carry the calibration.

## Drive gearing interpretation

161 ticks/cm with a 360 ticks/rev motor: the effective wheel circumference
per MOTOR rev = 360/161 = 2.24 cm. At a 17 cm effective sprocket/track
diameter (53 cm circumference): the motor revs per wheel rev ~ 7.6:1. The
true ratio needs the sprocket diameter measured (the user's task); every
cm of sprocket diameter shifts it by ~0.5.

## Blocked on (resolved by the successful run)

- The user repositioning the robot (~75-80 cm obstacle distance, ≥40 cm
  clear behind) or confirming the current clearances.
- The drive rate must be modeled at ~1.16 ticks/s per speed unit (not the
  turret's 7.2) in all leg budgets.
