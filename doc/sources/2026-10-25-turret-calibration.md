# Turret Calibration Capture — 2026-10-25

Raw evidence for the turret gear-ratio measurement and the color-sensor homing
investigation. Synthesis: [robot-hardware](../architecture/robot-hardware.md).
Probes: `testing/turret_ratio_probe.py` (this session),
`testing/turret_calibration_probe.py` (superseded — assumed full rotations,
which the cable constraint forbids).

## Hardware facts (user-provided)

- **Cables run through the turret** (Kinect, turret motor, color sensor) —
  rotation is **limited**; no full revolutions. Ever.
- The turret drives the Kinect mount through an **unknown gear train**.
- A LEGO color sensor rides on the turret (BrickPi PORT_1, light-on mode),
  ~5 cm above the body. It was originally a "primitive rotation encoder"
  reading a **paper dial — now destroyed**.
- A cable sticks from the back of the robot ~5 cm below the sensor's sweep,
  at the body position marking **camera forward**. The sensor should detect
  a slight color difference there → usable as a homing index.
- Turret position at session start: **~45° right of center** (user estimate).

## Gear ratio — measured optically (Kinect as the angle reference)

Method: small swings (0.6 s @ speed 25, deadman-streamed); at each rest,
average 4 Kinect frames; measure the horizontal scene shift between rests by
normalized cross-correlation of the row-averaged intensity profile (rows
150–300, sub-pixel); convert px → degrees with `Config.KINECT_FX = 594.21`;
divide the encoder delta by the angle.

| swing | encoder Δ | scene shift | angle | ticks/° |
|---|---|---|---|---|
| 1 | +108 | +8.96 px (corr 0.999) | +0.86° | 125.1 |
| 2 | +111 | +9.71 px (corr 0.998) | +0.94° | 118.6 |
| 3 | +107 | +8.29 px (corr 0.999) | +0.80° | 133.8 |
| 4 | +99 | +8.20 px (corr 0.998) | +0.79° | 125.2 |

**Result: ~125 ticks per turret degree ≈ 125:1 gearing** (±10%; the spread is
±1 px correlation quantization). Sanity: static-scene control shift was
+0.00 px (corr 1.000) — measurement conditions excellent. Cross-check vs
session history: the 2026-10-24 probes netted ≈1147 ticks and produced a
small heading change, consistent with a large ratio (a 1:1 turret would have
spun ~3 revolutions).

## Color sensor findings

- Baseline at rest: median 717, **mad = 1.0** — extremely stable signal.
- First homing swing (toward center): a sustained deviation fired at
  **encoder ≈ −3468** (color 717 → ≥763, ~+46 = ~45σ). Real surface change,
  hugely detectable — **but only ~425 ticks ≈ 3.8° from the start position**,
  while the cable (forward mark) should be ~45° away at 125 ticks/°.
  → The feature is **not yet identified**: another body detail (LEGO part,
  dial remnant, a second cable?) — or the sensor/camera angular offset
  geometry differs from the assumed one.
- Probe stopped at the first event by design; turret ended at encoder
  **−3420 ≈ 41° right of center** (est.). CSV: `/tmp/koc_calib/` on the robot.

## Open questions

1. Identify the −3468 feature: swing back/forth across it — a fixed landmark
   re-appears at the *same encoder value*; the cable should appear at
   ~center (encoder ≈ −3893 + 45° × 125 ≈ +1730 if the start estimate and
   ratio hold).
2. The raw `get_mks_accel` axis oddity (near-zero at level) still unexplained.
3. Turret travel limits in each direction — unknown; approach center slowly
   and log color continuously; never rotate unbounded.
4. Confirm the ratio at larger accumulated angles (sum several swings to
   ~20° and compare the summed px shift) — tightens the ±10% band.
