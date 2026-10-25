# Turret Cable Wrap Incident — 2026-10-25

## What happened

During the Phase-1 motord parity session, the turret accumulated ~187° of CW
rotation across tests (the swing90 legs, the constant-pwm run), wrapping the
Kinect tether cable. The user saw the turret "facing almost backwards". The
recovery attempts (CCW return, then CW bursts per the user's direction
preference) revealed the cable is now wedged: **both directions stall at
13-55 ticks/s where free motion is ~600 ticks/s** (pwm 82, battery healthy
at 8.872 V — verified during the incident).

The robot was left idle and safe: motors floating, motord stopped, turret at
encoder ~19771 (~155° CW of camera-forward). **The cable needs physical
attention before any further rotation.**

## Timeline (encoder C, 125 ticks/deg, camera-forward ≈ 401)

| Event | C position | Notes |
|---|---|---|
| Session start | 297 | near center; user's "original spot" |
| Turret twitches (parity) | 297 → 661 → ~323 | ±364/338 ticks, free |
| swing90 leg1 (pwm 61) | → -972 | crawled 14 ticks/s — FIRST stall sign, misread as "battery sag" |
| swing90 remaining legs | → 12510 | 24-260 ticks/s, wildly position-dependent |
| Const-pwm test (pwm 82) | → 23830 | 602 ticks/s — FREE (this heading was slack) |
| Cancelled CCW return | → ~15579 | crawled 14-55/s; user hit stop |
| 6 s CW burst | → 19280 | 617 ticks/s — free (the user chose CW) |
| CW continue at 19280 | → 19771 | **13 ticks/s — STALLED; the stall guard aborted** |

## Root causes

1. **My test design ignored the cable envelope.** The swing90 legs targeted
   ±11250 ticks relative, but the accumulated absolute positions wandered
   far past the historically verified band ([−10849, 11651]). The cable's
   free window is narrow and shifts with the wrap history.
2. **The probe's refresh cadence starved below the 400 ms intent expiry**
   during the first swing run (a slow snapshot RPC interleaved with the
   intent refreshes) — the pwm zeroed between refreshes, producing the
   crawl that looked like a hardware fault. Fixed: the dedicated 10 Hz
   refresh thread, independent of position monitoring.
3. **No stall detection in motord itself** — the probe noticed; the daemon
   must (see bd koc-v2-motord-driver).

## Validated facts (survive the incident)

- **Motion parity is real**: the motord constant-pwm turret run did 11314
  ticks in ~18.8 s (602/s) vs the v1's 612/s at the same pwm 82. The
  crawl was always the refresh cadence, never the daemon.
- **The v1 swing90 in the same session: 4 legs within ±4 ticks of target,
  the repeatability 6 ticks** — when the cable is slack, both stacks are
  excellent.
- **The safety nets held under every failure**: the probe killed mid-leg →
  the intent expiry (400 ms) stopped the turret; the SIGKILL drill → the
  firmware deadman (300 ms) floated the motors; the stall guard aborted.
- The battery is NOT the variable: 8.872 V measured mid-incident
  (8.854 documented).
- The encoder tracks hand rotation (it counts through the 125:1 gearing).

## Rules for v2 (and for any future turret motion)

1. **The absolute cable envelope is a first-class motord constraint** —
   intents beyond it are rejected; the envelope is calibrated after the
   cable is physically freed (the free window observed today is narrower
   than the historical band).
2. **Stall detection in motord**: if |d(encoder)|/dt collapses below a
   threshold while the pwm is significant, cut the intent and report a
   stall event (the probe's guard, promoted into the daemon).
3. **The intent refresh must be a dedicated 10 Hz stream**, never coupled
   to telemetry reads (the same pattern as the v1 GUI's key-hold).
4. **Never accumulate >±90° from the last known-good cable state without
   a visual check.**

Related: [drive ratio run](2026-10-25-drive-ratio-run.md) · bd
`koc-v2-motord-driver` · [robot hardware](../architecture/robot-hardware.md)
