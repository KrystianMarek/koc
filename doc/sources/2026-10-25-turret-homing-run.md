# Turret Homing Run — Sonar + Kinect + Color — 2026-10-25

Raw evidence from the first full homing sweep. Probes:
`turret_homing_probe.py`; CSVs on the robot at `/tmp/koc_calib/`.
Synthesis: [robot-hardware](../architecture/robot-hardware.md).

## Setup (user)

- Obstacle directly in front of the base chassis, ~70 cm from the ultrasonic
  sensor (PORT_4, chassis-fixed). Turret ~30° right of center; turning LEFT
  centers the Kinect on the obstacle. Color sensor (PORT_1) is turret-mounted.

## Critical bug found and fixed during this run

`BrickPiWrapper.get_voltage()` created a fresh `smbus2.SMBus(1)` per call and
never closed it → **one leaked fd per second** → `OSError: Too many open
files` after ~15-20 min → the wrapper thread died → telemetry gone forever.
This was the true root cause of the recurring "telemetry death" (the log
showed exactly one traceback: `brick_pi_wrapper.py read_temp → errno 24`).
**Fixed**: SMBus in a `with` block (closed per read). Deployed.

## The sweep (30 × 1.0 s swings @ speed 25, TurretLeft, ~1°/swing)

- Start: encoder **−3004**; end: **+1268** (net +4272 ticks ≈ 34.2° at
  125 ticks/°; tick budget stopped it).
- **Sonar: 75 cm constant** (range 75..75 across all 30 swings) — the
  obstacle confirmed; the turret never occludes the sonar's cone. The
  sonar is the *distance oracle*, not an angle sensor (it is chassis-fixed).
- **Obstacle blob** (nearest-valid-depth cluster, raw window 300–1008):
  tracked smoothly across the image, x = 266 → 72 → 58 → … → 319 → 490;
  blob pixel count grew to 148k at center (the obstacle filled the view).
  Blob raw drifted 612 → 665 (0.71 → 0.79 m per `raw_depth_to_meters`) —
  parallax from the camera's offset from the turret axis + surface geometry.
- **Centered on obstacle: encoder ≈ +527** (blob centroid crossed image
  center x=320 at swing 19; interpolated 531). **Color at center ≈ 790**;
  the color trace is a smooth reproducible gradient 780 → 793 across the
  whole sweep (no sharp step — fingerprint curve, not a step landmark).
- End state: encoder +1268 ≈ **6° left of center**; the obstacle now sits
  ~16° right of the camera axis (blob x=490).

## Landmarks for the homing system (v2)

| Landmark | Value |
|---|---|
| Camera centered on the 75 cm obstacle | encoder **≈ +527** |
| Color raw at that center | **≈ 790** (gradient curve, not a step) |
| Sonar ground truth | **75 cm** steady (chassis-fixed, never occluded) |
| Gear ratio | ~125 ticks/° (optical, ±10%); this sweep's near-field blob is parallax-polluted — do not refine the ratio from it |

## Open questions

1. The ratio disagreement (125 far-scene vs ~165-198 implied by this
   near-field sweep) is expected parallax; re-measure against a DISTANT
   target (parallax → 0) for a clean number.
2. The color gradient needs a full-travel calibration curve (color ↔
   encoder) to serve as a secondary angle sensor.
3. Turret travel limits still unknown past ~±5° from center; the next
   exploration should map them carefully.
