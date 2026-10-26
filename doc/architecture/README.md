# System Architecture

Architecture documents for this project — components, data flow, trust model, deployment topology.

## Naming Convention

`<component>.md` — one file per major component or subsystem.

## Index

| Document | Description |
|----------|-------------|
| [robot-hardware.md](robot-hardware.md) | Physical robot: port map (A/D/C, sensors), Kinect + NCS, Measured constants (single source for gearing, odometry, rates), deadman, USB topology |
| [brickpi-interface.md](brickpi-interface.md) | BrickPi+ UART protocol (2× ATmega, framing, E-STOP + firmware deadman), v1 usage, Rust driver strategy |
| [kinect-interface.md](kinect-interface.md) | Kinect v1 / libfreenect stack, C API surface, legacy status, v2 `camerad` strategy |

## Document Template

```markdown
# <Component Name>

## Purpose
What this component does and who uses it.

## Context
Where it sits in the overall system.

## Interfaces
- Inputs, outputs, APIs, events

## Internals
- Key modules, data structures, algorithms

## Dependencies
- Other components, external services

## Operational Notes
- Scaling, failure modes, SLOs

## References
- Related ADRs, plans, runbooks
```

## Related

- Wiki hub: [Overview](../overview.md) · [Index](../index.md)
- [Architecture Decisions](../decisions/README.md)
- [Implementation Plans](../plans/README.md)
- [Development Guides](../development/README.md)
