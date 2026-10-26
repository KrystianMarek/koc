# Goals

Long-horizon (north star) and short-horizon (current cycle) goals. When a goal
is met, move it to "Achieved"; when direction changes, revise it and note the
change in [log.md](log.md).

## North star (long horizon)

- **K.O.C v2**: a maintainable, safe, observable robot software stack on the
  existing hardware (RPi 3 + BrickPi+ + Kinect), architected like Microduck:
  single-purpose daemons over JSON-RPC/UDS, intents-not-motor-writes,
  features-not-frames, throttled capture, health-gated updates, headless-first
  testability. Direction: [vision/v2-microduck-stack.md](vision/v2-microduck-stack.md).
- Keep v1 running as the reference while v2 phases land — each v2 phase must
  pass probe parity against the real robot before replacing v1 components.

## Current cycle (short horizon)

- [ ] Finish Phase 1 (`koc-v2-motord-driver`): homing intent
      (`koc-v2-turret-homing`), in-daemon cable envelope + stall detection,
      probe-shim acceptance
- [ ] Confirm the turret ratio (~116.7 vs 125 ticks/°) with an independent
      measurement before using absolute turret targets
- [ ] Decide whether to unwind the ~one-turn turret cable wrap (a 360° move —
      user approval required)
- [ ] `koc-hw-kinect-wedge`: Stream-70 storms persist on the two-hub chain

## Achieved

- 2026-10-24: ai-assisted-development template adopted; wiki seeded
- 2026-10-24: live robot surveyed; Kinect stream verified end-to-end; turret
  rotation measured (deadman + streaming dynamics documented)
- 2026-10-24: v1 code assessment; bugs `koc-hw-kinect-wedge`,
  `koc-hw-sync-target` filed; `app/Networking` casing fixed and committed
- 2026-10-25: `sync.sh` fixed (`koc-hw-sync-target` closed); Kinect wedge
  mitigations deployed; drive odometry 161.0 ticks/cm; turret ratio and
  homing landmarks measured
- 2026-10-25: [v2 implementation plan](plans/2026-10-25-koc-v2-implementation.md)
  approved; Phase 1 `motord` reached read/motion parity with `BrickPi.py`
- 2026-10-26: turret re-centered by Kinect; `motord` snapshot starvation
  fixed; sonar confirmed working ([centering run](sources/2026-10-26-turret-centering-run.md))

## Related

- [overview.md](overview.md) · [status.md](status.md)
- [vision/](vision/README.md) · [plans/](plans/README.md)
