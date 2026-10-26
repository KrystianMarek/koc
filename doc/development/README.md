# Development Documentation

Documentation for developers working on this project — setup, workflow, debugging, and internal guides.

## Quick Start

For new developers:

1. Read [AGENTS.md](../../AGENTS.md) for project conventions and tech stack.
2. Review the current [Roadmap](../plans/README.md) and active plans.
3. Check [Runbooks](../runbooks/README.md) for operational procedures.

## Naming Convention

Descriptive kebab-case filenames (e.g., `test-strategy.md`, `dependency-upgrade-guide.md`). Use date prefixes (`YYYY-MM-DD-`) for point-in-time documents like post-mortems or investigation logs.

## Index

| Document | Description |
|----------|-------------|
| [robot-deployment.md](robot-deployment.md) | Software state on the robot: deployment, v2 build, UART ownership, known issues, operating commands |
| [agent-lessons.md](agent-lessons.md) | Rules agents learned on the live robot (turret, daemons, shell, measurement), each with its evidence |
| [2026-10-24-koc-v1-code-assessment.md](2026-10-24-koc-v1-code-assessment.md) | V1 codebase assessment — v2 baseline |
| [project-structure.md](project-structure.md) | Code organization (v1) |
| [refactor-networking.md](refactor-networking.md) | Networking refactor plan (completed Dec 2025) |
| [todo-code-cleanup-refactor.md](todo-code-cleanup-refactor.md) | Code cleanup and naming refactor (completed) |
| [todo-dependency-management.md](todo-dependency-management.md) | Dependency management refactor TODO |
| [todo-gui-layout-refactor.md](todo-gui-layout-refactor.md) | GUI layout refactor TODO |
| [todo-improvements.md](todo-improvements.md) | Future improvements backlog |
| [architecture-improvements.md](architecture-improvements.md) | Preparatory refactoring proposals |
| [todo-3d-scene-reconstruction.md](todo-3d-scene-reconstruction.md) | 3D scene reconstruction plan |
| [guidance-request-3d-reconstruction.md](guidance-request-3d-reconstruction.md) | Guidance request: 3D reconstruction |
| [guidance-3d-reconstruction.md](guidance-3d-reconstruction.md) | Guidance response: 3D reconstruction |
| [guidance-request.md](guidance-request.md) | General technical guidance request |

## Bugs & Post-Mortems

**Detected bugs are tracked in `bd`, not here.** File each bug as a `bd` issue
(`bd create "..." --type bug`) so it gets dependencies, claims, and status. This
directory is the home for the *narrative* — a post-mortem written after a
significant bug is resolved.

- Naming: `YYYY-MM-DD-postmortem-<slug>.md`.
- Cross-link both ways: reference the `bd` ticket ID(s) in the post-mortem, and
  point the ticket back with `--external-ref` or the doc path.
- Suggested sections: Summary · Impact · Timeline · Root cause · Fix ·
  Prevention / follow-up tickets.

## Adding Documentation

Place developer-centric documents here:

- Setup and configuration guides
- Development workflow documentation
- Debugging guides and troubleshooting
- Investigation logs and post-mortems (see above)

## Related

- Wiki hub: [Overview](../overview.md) · [Index](../index.md) · [Status](../status.md)
- [System Architecture](../architecture/README.md)
- [Architecture Decisions](../decisions/README.md)
- [Implementation Plans](../plans/README.md)
- [Operational Runbooks](../runbooks/README.md)
