# Implementation Plans & Tasks

This directory contains implementation plans, feature roadmaps, and design documents.

> **Hard rule (from CLAUDE.md):** All implementation plans MUST be saved here **before implementation begins**. Agents must save the plan file and get user approval before writing any implementation code.

## Naming Convention

- `YYYY-MM-DD-<description>.md` for dated plans
- `<topic>.md` for ongoing tracking documents (e.g., `prehistoryk-issues-log.md`)

## Plans Index

| Plan | Description | Status | Date |
|------|-------------|--------|------|
| [adopt.sh](2026-04-17-adopt-script.md) | Automate template adoption | Parked | 2026-04-17 |
| [LLM Wiki migration](2026-07-10-llm-wiki-migration.md) | Turn `doc/` into a development-focused LLM Wiki | Planning | 2026-07-10 |
| [Log, external/, hygiene](2026-09-28-log-external-hygiene.md) | Conflict-free one-line log, `external/` scaffold, repo hygiene duty | Planning | 2026-09-28 |
| [K.O.C v2 implementation](2026-10-25-koc-v2-implementation.md) | Microduck-aligned Rust daemon stack; all open questions resolved | Approved | 2026-10-25 |
| [Turret centering fixes](2026-10-26-turret-centering-fixes.md) | motord lock starvation, position-stopped turret moves, sonar-gated Kinect bearing | Active (awaiting user visual check) | 2026-10-26 |

Status vocabulary: `Planning` → `Approved` → `Active` → `Complete` / `Superseded` / `Parked` / `Disabled`.

## Plan Template

```markdown
# Plan: <Title>

## Objective
What are we trying to achieve?

## Scope
What is included / excluded?

## Tasks
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

## Milestones
Target milestones (no time estimates — focus on what, not how long).

## Dependencies
Prerequisites and blockers.

## Success Criteria
How do we know this is done?
```

## Related

- Wiki hub: [Overview](../overview.md) · [Index](../index.md) · [Goals](../goals.md) · [Status](../status.md)
- [Operational Runbooks](../runbooks/README.md)
- [Inbox — Incoming Requests](../inbox/README.md)
- [Architecture Decisions](../decisions/README.md)
- [Vision & Ideas](../vision/README.md)
