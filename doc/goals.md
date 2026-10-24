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

- [ ] Commit the 2026-10-24 session (template adoption, casing fix, docs, probes) — working tree holds it all
- [ ] Fix `koc-hw-kinect-wedge` (throttle capture + fork before ZMQ setup) and redeploy
- [ ] Fix `koc-hw-sync-target` (target dir + excludes)
- [ ] Decide the v2 open questions (BrickPi driver strategy, capture sidecar, client↔robot transport, OS path) and write the v2 implementation plan in `doc/plans/` — user approval required before coding

## Achieved

- 2026-10-24: ai-assisted-development template adopted; wiki seeded
- 2026-10-24: live robot surveyed; Kinect stream verified end-to-end; turret
  rotation measured (deadman + streaming dynamics documented)
- 2026-10-24: v1 code assessment; bugs `koc-hw-kinect-wedge`,
  `koc-hw-sync-target` filed; `app/Networking` casing fixed locally

## Related

- [overview.md](overview.md) · [status.md](status.md)
- [vision/](vision/README.md) · [plans/](plans/README.md)
