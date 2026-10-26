# Turret Centering and Re-referencing

## Purpose

Point the turret at camera-forward (the Kinect looks straight ahead of the
body, and the cables are neutral) and record that position as the center of
the cable envelope in `~/.koc/turret.json` on the robot. Both motor writers
(the v1 server and motord) refuse turret motion until this file is valid.

## When to use

- A guard reports **locked**: motord `snapshot` shows
  `"turret_guard": {"locked": true, ...}`, or the v1 server log says
  `turret LOCKED`. Causes: the state file is missing, or the first encoder
  reading did not match the saved `last` (BrickPi power cycle resets the
  encoders to 0; a hand turn of the turret moves them).
- The user says the turret does not look straight ahead.
- Before any work that needs an accurate absolute turret angle.

## Rules

- **Re-reference only after the user confirms where the turret faces.** The
  envelope is only as good as its center; a wrong center lets the turret wind
  its cables past 180°.
- **The turret never turns more than 180° either way from camera-forward.**
  When a guard stops a move at its limit, the move was wrong; go back toward
  the center.
- Moves go through `testing/motord_parity_probe.py rel <ticks>`: position-
  stopped, at most 15° per move, aborts on stall or stale position.
- Turret sign: **positive ticks = turret left** (the user's CCW seen from
  above); negative = right. Turret ticks per degree is not confirmed (see
  [Measured constants](../architecture/robot-hardware.md#measured-constants)), so prefer several small moves.

## Prerequisites

- An obstacle with a flat face directly in front of the robot body, about
  0.5–0.8 m away, wider than the Kinect's view of a few degrees (a box or a
  wall section). The sonar on PORT_4 is chassis-fixed, so it measures the
  obstacle straight ahead of the body.
- SSH access to `pi@192.168.10.187`; on the robot,
  `P=/home/pi/.virtualenvs/pi_robot3/bin/python` and `cd ~/rpi_lego_robot`.
- The user available to look at the robot.

## Procedure

Run each robot command as one ssh call, redirecting output to a file and
`cat`-ing it in the same call (see
[robot deployment](../development/robot-deployment.md)).

### Step 1: read the current state

The v1 server must be stopped (one UART owner).

```bash
$P testing/turret_envelope.py show
$P testing/motord_parity_probe.py motord   # encoders, sonar, turret_guard
```

Note the turret encoder `C` and `sonar` (cm). Snapshots work while the
turret is locked.

### Step 2: unlock with a provisional center (only when locked)

Ask the user how far the turret faces from straight ahead, in degrees
(left positive, right negative). Back up the old file, then write a
provisional center from the user's estimate:

```bash
cp -f ~/.koc/turret.json ~/.koc/turret.json.bak 2>/dev/null
$P testing/turret_envelope.py set-center --encoder <C> --current-deg <X>
```

Restart motord (the probe restarts it on every move) to apply.

### Step 3: measure the bearing with the Kinect

Stop motord (`pkill -x motord`), start the v1 server, wait ~10 s for the
Kinect, then:

```bash
$P testing/kinect_bearing.py <sonar_cm>
```

Use the `RESULT:` line only when it is not marked untrusted. A positive
bearing (obstacle right of image center) means the turret points left of the
obstacle: move encoder-negative. The move is about
`-bearing_deg × ticks_per_degree` ticks, with the working value from
[Measured constants](../architecture/robot-hardware.md#measured-constants). The `SURFACE:` yaw is a second cue; both should
agree within about 1°.

### Step 4: move

Stop the v1 server, then:

```bash
$P testing/motord_parity_probe.py rel <ticks>
```

For moves over 15°, repeat in steps of at most 15° with a bearing check in
between. Make the final approach from the same side each time (the
2026-10-26 center was approached from the left, i.e. with an encoder-negative
final move): see the turret backlash in
[Measured constants](../architecture/robot-hardware.md#measured-constants).

### Step 5: repeat until centered

Repeat steps 3–4 until the bearing is within ±0.5° and the surface yaw
agrees. Then ask the user to confirm visually that the turret looks straight
ahead.

### Step 6: record the center

With the v1 server stopped:

```bash
pkill -x motord; sleep 2
$P testing/motord_parity_probe.py v1            # direct reads: the final C
$P testing/turret_envelope.py set-center --encoder <C>
$P testing/turret_envelope.py show
```

## Verification

- `turret_envelope.py show` prints the new center and the stop positions
  (center ± 20200 ticks).
- A fresh `motord_parity_probe.py motord` shows `turret_guard.locked: false`
  and the same center.
- Record the run (moves, bearings, final C) in a `doc/sources/` capture and
  update the camera-forward line in
  [robot hardware](../architecture/robot-hardware.md).

## Rollback

`cp -f ~/.koc/turret.json.bak ~/.koc/turret.json` restores the previous
reference, valid only if the encoders have not been reset since it was
written.

## Gotchas

- **Kinect "Stream 70" storms** stall frames for 10–20 s after motion; if
  `kinect_bearing.py` reports few frames, wait and run it again.
- **Sonar reads 255 when the obstacle is out of its cone** (on 2026-10-26
  beyond ~62 cm); readings during motion are coarse, so use one taken at
  rest.
- **Edge-touching obstacle runs are untrusted**: the obstacle is partly out
  of view, so its center is unknown. Make a smaller move toward it first.
- **The 0.12 m depth gate** uses the sonar distance; a wrong sonar argument
  selects the wrong object.
- **A false lock after a crash**: if a writer died mid-move, `last` may lag
  the real position by more than 400 ticks and the turret locks although
  nothing moved it. Re-reference as above; do not raise the tolerance.
- **v1 overshoot**: the v1 server runs at 10 Hz and coasts up to ~500 ticks
  past a stop at full speed; the guards stop 800 ticks short of the
  180° limit for that reason.

## Related

- [Turret envelope plan](../plans/2026-10-26-turret-envelope.md) · guards:
  `app/server/turret_guard.py`, `robot/motord/src/guard.rs`
- [Turret centering run 2026-10-26](../sources/2026-10-26-turret-centering-run.md)
- [Turret cable incident 2026-10-25](../sources/2026-10-25-turret-cable-incident.md)
- [Robot hardware](../architecture/robot-hardware.md) · [Robot deployment](../development/robot-deployment.md)
