# Sources — Immutable Raw Layer

The **source-of-truth** layer of the wiki. Requirements, transcripts, external
references, research notes, spec dumps, and anything the wiki synthesizes *from*.

> **Immutable.** Agents **read** from these files but **never rewrite** them. If a
> source is updated upstream, add a new dated file rather than editing the old
> one. The synthesized understanding lives in the wiki pages, not here.

## Workflow (ingest)

1. Drop the raw material here (or link it, for large/binary sources).
2. Integrate it into the wiki: update [overview](../overview.md) if the big
   picture shifted, update the relevant topical page(s), and register new pages
   in [index.md](../index.md).
3. Append an `ingest` entry to [log.md](../log.md).

See [AGENTS.md → Documentation wiki](../../AGENTS.md#documentation-wiki).

## Naming Convention

- `YYYY-MM-DD-<source>-<topic>.md` for dated captures (articles, transcripts,
  meeting notes) — e.g., `2026-07-10-user-interview-onboarding.md`.
- `<ref>.md` for stable references — e.g., `external-api-contract.md`.

## Index

| Document | Source | Date | Ingested? |
|----------|--------|------|-----------|
| [2026-10-24-microduck-analysis.md](2026-10-24-microduck-analysis.md) | Web research + `external/` clones (Pollen/HF Microduck) | 2026-10-24 | ✅ |
| [2026-10-24-robot-state-capture.md](2026-10-24-robot-state-capture.md) | SSH surveys + probe transcripts from live robot 192.168.10.187 | 2026-10-24 | ✅ |
| [2026-10-24-hardware-libs-capture.md](2026-10-24-hardware-libs-capture.md) | BrickPi UART protocol + libfreenect API facts, upstream repo status | 2026-10-24 | ✅ |
| [2026-10-24-ncs-state.md](2026-10-24-ncs-state.md) | Intel NCS (USB accelerator) state on the robot + ecosystem status | 2026-10-24 | ✅ |
| [2026-10-25-turret-calibration.md](2026-10-25-turret-calibration.md) | Turret gear ratio (~125 ticks/°) via Kinect optical reference; color homing mark | 2026-10-25 | ✅ |
| [2026-10-25-turret-homing-run.md](2026-10-25-turret-homing-run.md) | First homing sweep: sonar + Kinect + color landmark pair | 2026-10-25 | ✅ |
| [2026-10-25-swing90-run.md](2026-10-25-swing90-run.md) | 90/180/90 turret swing reliability (encoder, color, Kinect) | 2026-10-25 | ✅ |
| [2026-10-25-drive-ratio-run.md](2026-10-25-drive-ratio-run.md) | Drive odometry mission: track break, repositioning, 161.0 ticks/cm | 2026-10-25 | ✅ |
| [2026-10-25-turret-cable-incident.md](2026-10-25-turret-cable-incident.md) | Turret cable wrap during motord parity; rules for v2 | 2026-10-25 | ✅ |
| [2026-10-26-turret-centering-run.md](2026-10-26-turret-centering-run.md) | Live turret re-centering: tooling defects, moves, Kinect readings, one-turn ≈ 42000 ticks | 2026-10-26 | ✅ |
| [2026-10-26-turret-envelope-run.md](2026-10-26-turret-envelope-run.md) | ±180° envelope live checks: locked cases, limit stops, overshoot per writer | 2026-10-26 | ✅ |
| [2026-10-26-drive-ratio-rerun.md](2026-10-26-drive-ratio-rerun.md) | Drive re-run with sonar cross-check: 166.6 ticks/cm rest-to-rest, 20:12 gearing inferred | 2026-10-26 | ✅ |
| [2026-10-28-hardware-lifecycle.md](2026-10-28-hardware-lifecycle.md) | End-of-life status of each robot part; robot unreachable 2026-10-28 | 2026-10-28 | ✅ |

## Related

- [Guidance](../guidance/README.md) — external expert consultations (also raw source)
- [Inbox](../inbox/README.md) — untriaged incoming requests
- [Wiki Index](../index.md)
- [Overview](../overview.md)
