# Status

Current progress snapshot — the narrative complement to `bd status`. Refresh on
any status change and during each [wiki-lint](runbooks/wiki-lint.md) pass. For
the live work queue, run `bd ready` and `bd status`.

_Last updated: 2026-10-24_

## In progress

- Nothing mid-flight; working tree holds the uncommitted 2026-10-24 session
  (template adoption + casing fix + docs + probes) awaiting a commit decision.

## Done recently

- 2026-10-24: adopted ai-assisted-development template (AGENTS.md, doc wiki,
  pre-commit, bd); researched Microduck and cloned its stack into `external/`.
- 2026-10-24: live robot session — Kinect stream + turret verified, dynamics
  measured, server wedge diagnosed, v1 code assessed.
- Bugs filed: `koc-hw-kinect-wedge`, `koc-hw-sync-target`.
- `app/Networking` → `app/networking` casing fix staged locally.

## Blocked / waiting

- Commit/push decision for the session work (user).

## Next up

- Fix `koc-hw-kinect-wedge`, fix `koc-hw-sync-target`.
- V2 planning: resolve open questions in [vision/v2-microduck-stack.md](vision/v2-microduck-stack.md),
  then write the implementation plan in `doc/plans/`.

## Related

- [goals.md](goals.md) · [log.md](log.md) · [index.md](index.md)
