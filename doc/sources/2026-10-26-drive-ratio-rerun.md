# Drive Ratio Re-run with Sonar Cross-check — 2026-10-26

Raw evidence for the drive gearing question (bd `koc-drive-ratio`). Probe:
`testing/drive_ratio_probe.py` v5, unchanged, `3 60` (three rounds at
PWM 60). Kinect depth is the position oracle; the probe also logs the
ultrasonic reading in its telemetry CSV (`/tmp/koc_calib/drive_ratio_v5.csv`
on the robot, overwritten by every run). Robot faces a flat obstacle
(Kinect yaw −0.9° vs its face normal); turret at C≈42308.

## Probe output (as printed)

| Leg | Ticks at stop | Kinect at rest after leg |
|---|---|---|
| baseline | — | 0.660 m |
| blip (toward) | +1540 | 0.561 m |
| round 1 away / back | −3102 / +3098 | 0.752 / 0.560 m |
| round 2 away / back | −3112 / +3128 | 0.752 / 0.554 m |
| round 3 away / back | −3120 / +3093 | 0.747 / 0.553 m |

The probe reported 154.2 (blip) and 162 / 162 / 161 ticks/cm (away legs).

## The probe undercounts each leg's ticks

`drive_ticks()` returns the encoder delta at the moment it sends the stop.
The motors then coast **~100–150 ticks** before they come to rest, and the
Kinect measures the rest position. Rest-to-rest deltas from the CSV:

| Leg | Rest-to-rest ticks | Coast | L / R ticks | Kinect travel | Ticks/cm |
|---|---|---|---|---|---|
| blip toward | 1644 | +104 | 1637 / 1652 | 9.9 cm | 166.1 |
| r1 away | 3206 | +104 | 3208 / 3205 | 19.1 cm | 167.9 |
| r1 back | 3202 | +104 | 3171 / 3233 | 19.2 cm | 166.8 |
| r2 away | 3215 | +103 | 3217 / 3213 | 19.2 cm | 167.4 |
| r2 back | 3280 | +152 | 3246 / 3313 | 19.8 cm | 165.6 |
| r3 away | 3222 | +102 | 3225 / 3219 | 19.3 cm | 166.9 |
| r3 back | 3200 | +107 | 3162 / 3237 | 19.4 cm | 164.9 |

- **166.6 ± 1.1 ticks/cm** (mean ± sd of the six 19 cm legs; the blip
  agrees at 166.1). The Kinect distances are printed to 1 mm, which is
  ±0.5 % per 19 cm leg; the spread is about that size.
- The 2026-10-25 figure of 161.0 used the same at-stop counting. Its own
  pairs (3097 ticks / 19.2 cm) reproduce today's at-stop 161–162, so the
  two runs agree; the corrected value is about 3.5 % higher.
- Round-trip position error (Kinect, at rest): −0.1 / −0.6 / −0.1 cm.
- Driving toward the obstacle (GoForward), the right encoder turns ~2 %
  more than the left (L/R 0.977–0.981); driving away the two match
  (1.001–1.002).
- Final rest check (12 s): Kinect blob 0.5522 m (sd 0.2 mm, 27 frames),
  sonar steady 48, encoders L −7909 R 11845.

## Ultrasonic cross-check

At-rest readings at the leg ends (first/last CSV samples of each leg):

| Kinect | Sonar | Kinect − sonar |
|---|---|---|
| 0.660 m | 59 cm | 7.0 cm |
| 0.561 m | 49 cm | 7.1 cm |
| 0.560 m | 49 cm | 7.0 cm |
| 0.554 m | 49 cm | 6.4 cm |
| 0.553 m | 48 cm | 7.3 cm |
| 0.75 m (far end, 3×) | 255 (no echo) | — |

- On the blip the sonar moved **10 cm vs the Kinect's 9.9 cm** (1644 /
  10 = 164 ticks/cm at the sonar's 1 cm resolution, ±10 %). The two
  sensors differ by a constant ~7 cm (their mounting offset).
- **The sonar loses the echo beyond ~62 cm here** (sonar scale, from the
  encoder position; the largest valid reading was 65; every far-end
  reading was 255), so it could not check the 19 cm legs at rest. The
  LEGO sensor's rated range is ~250 cm, so the likely cause is the beam
  missing the obstacle, not range.
- **The sonar reads during motion** in this run (312 of 456 moving samples
  valid; every 255 is beyond the ~62 cm cut-off). A per-leg linear fit of sonar vs
  encoder gives 154–161 ticks/cm on the away legs and 143–146 on the
  toward legs: the 1 cm quantization and the echo cut-off near the far
  end bias these fits, so they confirm the scale only to ~10 %.

## Derived drive gearing

- BrickPi encoder: **720 ticks per motor revolution** (0.5° per tick;
  `testing/brickpi/LEGO-Encoder_Test.py`: "360 degrees = 720 enc").
- Travel per motor revolution: 720 / 166.6 = **4.32 cm**.
- 42055 tracks: 12 mm link pitch. A 6-tooth drive sprocket moves the
  track 7.2 cm per sprocket revolution, so motor:sprocket =
  7.2 / 4.32 = **1.67:1 = 20:12**, which matches the tan 12-tooth and
  20-tooth double-bevel gears visible on the front cross axle in
  `pictures/pic1.jpg` / `pic2.jpg`. The 20:12 + 6-tooth prediction is
  166.7 ticks/cm; measured 166.6.
- Not yet confirmed by counting teeth on the robot.
