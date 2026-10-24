# Wiki Index

Master catalog of every page in this development-focused LLM Wiki. Read this
first when answering a query, then drill into the relevant pages. Update it on
every ingest (see [AGENTS.md → Project as an LLM Wiki](../AGENTS.md#project-as-an-llm-wiki)).

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
| [guidance/](guidance/README.md) | External expert consultations (requests + responses) |
| [inbox/](inbox/README.md) | Untriaged incoming feature requests |

## Knowledge & decisions

| Area | Summary |
|---|---|
| [architecture/](architecture/README.md) | System design, component / concept pages |
| [architecture/robot-hardware.md](architecture/robot-hardware.md) | Physical robot: port map, Kinect/NCS, measured dynamics |
| [architecture/brickpi-interface.md](architecture/brickpi-interface.md) | BrickPi+ UART protocol + v2 driver strategy |
| [architecture/kinect-interface.md](architecture/kinect-interface.md) | Kinect v1 / libfreenect stack + v2 capture strategy |
| [decisions/](decisions/README.md) | Architecture Decision Records (ADRs) |
| [considerations/](considerations/README.md) | Open trade-offs, risks, unresolved questions |
| [vision/](vision/README.md) | Exploratory product ideas and future concepts |
| [vision/v2-microduck-stack.md](vision/v2-microduck-stack.md) | V2 direction: microduck-aligned Rust daemon stack on existing hardware |
| [development/robot-deployment.md](development/robot-deployment.md) | Software state on the robot + known issues |
| [development/2026-10-24-koc-v1-code-assessment.md](development/2026-10-24-koc-v1-code-assessment.md) | V1 codebase assessment — v2 baseline |

## Execution & operations

| Area | Summary |
|---|---|
| [plans/](plans/README.md) | Implementation plans and task tracking |
| [runbooks/](runbooks/README.md) | Operational procedures (incl. [wiki-lint](runbooks/wiki-lint.md)) |
| [development/](development/README.md) | Developer guides, setup, post-mortems |
| [benchmarks/](benchmarks/README.md) | E2E verification scenarios and benchmark runs |

## Related

- [AGENTS.md](../AGENTS.md) — the wiki schema (conventions + ingest/query/lint workflows)
- Discrete work items live in `bd`; run `bd ready` / `bd status`.
