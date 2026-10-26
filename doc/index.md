# Wiki Index

Master catalog of every page in this development-focused LLM Wiki. Read this
first when answering a query, then drill into the relevant pages. Update it on
every ingest (see [AGENTS.md → Documentation wiki](../AGENTS.md#documentation-wiki)).

Status: ✅ live · 🚧 stub / planned

## Core wiki pages

| Page | Summary | Status |
|---|---|---|
| [overview.md](overview.md) | High-level idea: what this project is, who uses it, headline tech | ✅ |
| [goals.md](goals.md) | Long-horizon (north star) and short-horizon (current cycle) goals | ✅ |
| [status.md](status.md) | Current progress snapshot, cross-linked to `bd` | ✅ |
| [log.md](log.md) | Append-only chronological log of ingests / decisions / progress / lint | ✅ |
| [index.md](index.md) | This catalog | ✅ |

## Raw sources (immutable)

| Area | Summary |
|---|---|
| [sources/](sources/README.md) | Requirements, transcripts, external references, research notes |
| [sources/2026-10-24-microduck-analysis.md](sources/2026-10-24-microduck-analysis.md) | NVIDIA/Pollen/HF Microduck robot: spec, onboard software, training stack, clones in `external/` |
| [sources/2026-10-24-robot-state-capture.md](sources/2026-10-24-robot-state-capture.md) | SSH surveys + probe transcripts from the live robot |
| [sources/2026-10-24-hardware-libs-capture.md](sources/2026-10-24-hardware-libs-capture.md) | BrickPi UART protocol + libfreenect API facts, upstream repo status |
| [sources/2026-10-24-ncs-state.md](sources/2026-10-24-ncs-state.md) | Intel NCS (USB accelerator) state on the robot + ecosystem status |
| [sources/2026-10-25-turret-calibration.md](sources/2026-10-25-turret-calibration.md) | First turret ticks-per-degree estimate (~125, ±10 %) + color homing mark |
| [sources/2026-10-25-turret-homing-run.md](sources/2026-10-25-turret-homing-run.md) | First homing sweep: sonar + Kinect + color landmark pair |
| [sources/2026-10-25-swing90-run.md](sources/2026-10-25-swing90-run.md) | 90/180/90 turret swing reliability run |
| [sources/2026-10-25-drive-ratio-run.md](sources/2026-10-25-drive-ratio-run.md) | First drive odometry run (counted at the stop command; superseded) |
| [sources/2026-10-25-turret-cable-incident.md](sources/2026-10-25-turret-cable-incident.md) | Turret cable wrap incident + v2 turret rules |
| [sources/2026-10-26-turret-centering-run.md](sources/2026-10-26-turret-centering-run.md) | Turret re-centered by Kinect (C≈42298); motord lock starvation fixed; second turret ticks-per-degree estimate |
| [sources/2026-10-26-turret-envelope-run.md](sources/2026-10-26-turret-envelope-run.md) | ±180° envelope live checks: locks, limit stops and overshoot per writer |
| [sources/2026-10-26-drive-ratio-rerun.md](sources/2026-10-26-drive-ratio-rerun.md) | Drive odometry re-run rest to rest; sonar cross-check; drive gearing inferred |
| [guidance/](guidance/README.md) | External expert consultations (requests + responses) |
| [inbox/](inbox/README.md) | Untriaged incoming feature requests |

## Knowledge & decisions

| Area | Summary |
|---|---|
| [architecture/](architecture/README.md) | System design, component / concept pages |
| [architecture/robot-hardware.md](architecture/robot-hardware.md) | Physical robot: port map, **Measured constants** (single source for gearing, odometry, rates), Kinect/NCS |
| [architecture/brickpi-interface.md](architecture/brickpi-interface.md) | BrickPi+ UART protocol + v2 driver strategy |
| [architecture/kinect-interface.md](architecture/kinect-interface.md) | Kinect v1 / libfreenect stack + v2 capture strategy |
| [decisions/](decisions/README.md) | Architecture Decision Records (ADRs) |
| [considerations/](considerations/README.md) | Open trade-offs, risks, unresolved questions |
| [vision/](vision/README.md) | Exploratory product ideas and future concepts |
| [vision/v2-microduck-stack.md](vision/v2-microduck-stack.md) | V2 direction: microduck-aligned Rust daemon stack on existing hardware |
| [development/robot-deployment.md](development/robot-deployment.md) | Software state on the robot + known issues |
| [development/agent-lessons.md](development/agent-lessons.md) | Rules agents learned on the live robot, each with its evidence |
| [development/2026-10-24-koc-v1-code-assessment.md](development/2026-10-24-koc-v1-code-assessment.md) | V1 codebase assessment — v2 baseline |

## Legacy v1 reference docs

Pre-wiki pages (December 2025 – January 2026). Still accurate for the v1
stack unless a newer wiki page says otherwise.

| Page | Summary |
|---|---|
| [architecture.md](architecture.md) | v1 client/server architecture over ZeroMQ |
| [networking.md](networking.md) | v1 ZeroMQ + pickle protocol and packet formats |
| [hardware.md](hardware.md) | Motor/sensor wiring and BrickPi configuration |
| [raspberry-pi-setup.md](raspberry-pi-setup.md) | Raspberry Pi OS setup guide (uv-based; see robot-deployment for stretch) |
| [ncs-legacy-support.md](ncs-legacy-support.md) | Intel Movidius NCS legacy support |
| [development/project-structure.md](development/project-structure.md) | Code organization |
| [development/refactor-networking.md](development/refactor-networking.md) | Networking refactor (completed Dec 2025) |
| [development/todo-code-cleanup-refactor.md](development/todo-code-cleanup-refactor.md) | Code cleanup and naming refactor (completed) |
| [development/todo-dependency-management.md](development/todo-dependency-management.md) | Dependency management refactor TODO |
| [development/todo-gui-layout-refactor.md](development/todo-gui-layout-refactor.md) | GUI layout refactor TODO |
| [development/todo-improvements.md](development/todo-improvements.md) | Future improvements backlog |
| [development/architecture-improvements.md](development/architecture-improvements.md) | Preparatory refactoring proposals |
| [development/todo-3d-scene-reconstruction.md](development/todo-3d-scene-reconstruction.md) | 3D scene reconstruction plan |
| [development/guidance-request-3d-reconstruction.md](development/guidance-request-3d-reconstruction.md) | Guidance request: 3D reconstruction |
| [development/guidance-3d-reconstruction.md](development/guidance-3d-reconstruction.md) | Guidance response: 3D reconstruction |
| [development/guidance-request.md](development/guidance-request.md) | General technical guidance request |

## Execution & operations

| Area | Summary |
|---|---|
| [plans/](plans/README.md) | Implementation plans and task tracking |
| [plans/2026-10-25-koc-v2-implementation.md](plans/2026-10-25-koc-v2-implementation.md) | v2 Rust daemon stack plan (approved; Phase 1 in progress) |
| [plans/2026-10-26-turret-centering-fixes.md](plans/2026-10-26-turret-centering-fixes.md) | Turret centering fixes (complete; user confirmed facing) |
| [plans/2026-10-26-turret-envelope.md](plans/2026-10-26-turret-envelope.md) | ±180° turret cable envelope in the v1 server and motord (complete) |
| [plans/2026-09-28-log-external-hygiene.md](plans/2026-09-28-log-external-hygiene.md) | Plan written for the upstream template repo; not applicable here (parked) |
| [runbooks/](runbooks/README.md) | Operational procedures |
| [runbooks/turret-centering.md](runbooks/turret-centering.md) | Center the turret with the Kinect; re-reference / unlock the cable envelope |
| [runbooks/wiki-lint.md](runbooks/wiki-lint.md) | Wiki health check |
| [development/](development/README.md) | Developer guides, setup, post-mortems |
| [benchmarks/](benchmarks/README.md) | E2E verification scenarios and benchmark runs |

## Related

- [AGENTS.md](../AGENTS.md) — the wiki schema (conventions + ingest/query/lint workflows)
- Discrete work items live in `bd`; run `bd ready` / `bd status`.
