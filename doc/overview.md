# Overview

The synthesis front page of this wiki — the high-level idea, kept current as the
project evolves. Start here, then follow the links.

## What this is

K.O.C ("Kinect on Caterpillar") is a remote-controlled LEGO robot: a Raspberry
Pi 3 with a BrickPi+ drives caterpillar tracks and a rotating turret (the
Kinect is mounted on it), streams RGB+depth video and telemetry over the
network, and is driven from a desktop client. It also carries a legacy Intel
Movidius NCS.

- **v1 (built, running)**: Python 3.5 server on Raspbian stretch, ZeroMQ +
  pickle transport, PyQt5 client. Deployed on the robot at
  `~/rpi_lego_robot` (see [deployment state](development/robot-deployment.md)).
- **v2 (current focus)**: rebuild the software stack aligned with
  [Microduck](sources/2026-10-24-microduck-analysis.md) — Rust daemons,
  JSON-RPC over Unix sockets, intents-not-motor-writes, throttled capture,
  health-gated updates. Direction: [vision/v2-microduck-stack.md](vision/v2-microduck-stack.md);
  plan: [v2 implementation](plans/2026-10-25-koc-v2-implementation.md). Phase 1
  (`motord`, Rust, in `robot/`) is built and running on the robot — see
  [status](status.md).

Hardware facts live in [architecture/robot-hardware.md](architecture/robot-hardware.md)
(port map, measured turret dynamics, deadman behavior, USB topology).

**Primary language / runtime:** v1 Python 3.5 (robot) / 3.14 (dev); v2 Rust (robot daemons)
**Package manager:** uv (dev machine, `.venv`), pip + virtualenvs on the robot (v1)

## The core idea

This project's `doc/` tree is maintained as a development-focused LLM Wiki — a
persistent, compounding, interlinked knowledge base that agents keep current.
See [AGENTS.md → Project as an LLM Wiki](../AGENTS.md#project-as-an-llm-wiki).

## Related

- [goals.md](goals.md) · [status.md](status.md) · [index.md](index.md)
- [../README.md](../README.md) · [../AGENTS.md](../AGENTS.md)
