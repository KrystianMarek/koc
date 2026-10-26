# AGENTS.md

Guidance for any agent working in this repository. `CLAUDE.md` is a symlink
to this file; edit `AGENTS.md`.

## Project

**K.O.C (Kinect on Caterpillar)**: a remote-controlled tracked robot built
from ~20-year-old LEGO Mindstorms parts. A Raspberry Pi 3 with a BrickPi+
drives two tracks and a turret that carries an Xbox 360 Kinect. Start with
[doc/overview.md](doc/overview.md); the hardware facts live in
[doc/architecture/robot-hardware.md](doc/architecture/robot-hardware.md).

| Part | Where | Stack |
|---|---|---|
| v1 server (runs on the robot) | `server.py`, `app/server/` | Python **3.5** (Raspbian stretch), BrickPi.py, freenect, ZeroMQ + pickle |
| v1 client (dev machine) | `gui.py`, `app/client/` | Python 3, PyQt5 |
| v2 daemons (in progress) | `robot/` (`brickpi`, `rpc`, `motord`, `robotctl`) | Rust, std + libc only, built on the robot |
| Probes and tests | `testing/` | run on the robot or from the dev machine; see each file's docstring |
| Wiki | `doc/` | Markdown, agent-maintained |

The robot is `pi@192.168.10.187` (passwordless SSH), code in
`~/rpi_lego_robot`, Python env `~/.virtualenvs/pi_robot3`.

## Hard rules

- **Turret envelope: the turret never turns more than 180° either way from
  camera-forward**, which is also where its cables are neutral. Both motor
  writers enforce this from `~/.koc/turret.json` on the robot: the v1 server
  through `app/server/turret_guard.py` and motord through
  `robot/motord/src/guard.rs` (same rules; change both together). Every new
  code path that drives the turret goes through one of these guards. When a
  guard reports **locked**, follow
  [doc/runbooks/turret-centering.md](doc/runbooks/turret-centering.md) and
  re-reference only after the user confirms where the turret faces.
- **Plans before code.** Save the implementation plan to
  `doc/plans/YYYY-MM-DD-<feature>.md` and get the user's approval before
  writing implementation code.
- **Guidance responses are user-authored.** Agents may draft guidance
  requests in `doc/guidance/`.
- **Ask before outward or irreversible robot actions**: reboots, package
  installs, unwinding the turret cables, anything that cannot be undone from
  software.

## Robot operations

Read [doc/development/robot-deployment.md](doc/development/robot-deployment.md)
before running anything on the robot (deploy, start/stop, probe commands),
and [doc/development/agent-lessons.md](doc/development/agent-lessons.md)
before turret, probe or daemon work. The gotchas that bite most:

- **One UART owner.** The v1 server and motord both drive `/dev/ttyS0`; stop
  one before starting the other. Kinect measurements need the v1 server.
- **Self-matching `pkill`.** Start the server as `$P server.py` (with
  `P=/home/pi/.virtualenvs/pi_robot3/bin/python`) and stop it with
  `pkill -f "python server.p[y]"`, so the pattern never matches the ssh shell.
- **Capture output on the robot**: redirect a probe to a file and `cat` it in
  the same ssh command.
- **Deploy**: `sync.sh` reads `ROBOT_IP` from the git-ignored `.local/env`.
  Without it, copy changed files with `scp` and `rsync --exclude target
  robot/`. `testing/` is never synced; copy probes by hand.
- **Encoders persist** while the BrickPi is powered; a power cycle resets
  them to 0, which locks the turret guard until it is re-referenced.
- **Turret moves**: use `testing/motord_parity_probe.py rel <ticks>`
  (position-stopped, 15° per move) and check the result with the Kinect
  (`testing/kinect_bearing.py`). Positive ticks = turret left (user CCW).
- Leave the robot idle at the end of a session: motors stopped, motord
  stopped, turret near center.

## Development conventions

- **Python on the robot is 3.5**: no f-strings, no `dataclasses`, no
  3.6+ syntax in `app/server/`, `app/common/`, `app/networking/` or any probe
  that runs on the robot. Check with the robot's interpreter.
- **Tests**: `python3 -m unittest testing.test_turret_guard` (stdlib
  unittest); `cargo test` in `robot/`. Run Rust tests on the robot too
  (`PATH=$HOME/.cargo/bin:$PATH cargo test --release`) when the change
  touches the hardware loop.
- **Hardware changes are verified on the robot**: build there, run the
  relevant probe, and record measured numbers in a `doc/sources/` capture.
- **Pre-commit** (`.pre-commit-config.yaml`): whitespace/EOF fixers,
  markdownlint (headings need a blank line before and after), shellcheck.
- **Git**: commit on `main` and push to `origin` (git.gocy.org). The
  `github` remote is parked. Commit subjects use an area prefix:
  `robot:`, `probes:`, `docs:`, `fix:`, combined as `robot+probes:`.

## Documentation wiki

`doc/` is an LLM wiki: agents keep it current instead of re-deriving
knowledge. [doc/index.md](doc/index.md) catalogs every page; read it first
when answering a question, and cite the pages you used.

| Content | Place | Name |
|---|---|---|
| Big picture, goals, status | `doc/overview.md`, `doc/goals.md`, `doc/status.md` | fixed |
| Immutable raw captures (runs, incidents, research) | `doc/sources/` | `YYYY-MM-DD-<topic>.md` |
| Component and concept pages | `doc/architecture/` | `<component>.md` |
| Decisions | `doc/decisions/` | `ADR-NNNN-<title>.md` |
| Developer guides, deployment, post-mortems | `doc/development/` | descriptive |
| Plans | `doc/plans/` | `YYYY-MM-DD-<feature>.md` |
| Procedures | `doc/runbooks/` | `<procedure>.md` |
| Open trade-offs | `doc/considerations/` | `<topic>.md` |
| Expert consultations / untriaged requests | `doc/guidance/`, `doc/inbox/` | see their README |

- **Ingest**: when something is learned (a measurement, a defect, a
  decision), file the raw capture in `doc/sources/`, update the topical pages
  and `doc/status.md`, register new pages in `doc/index.md` and the folder
  README, and append to `doc/log.md` with the prefix
  `## [YYYY-MM-DD] <ingest|decision|progress|lint> | <title>`.
- **Lessons**: when an agent mistake costs time or risks hardware, add the
  rule and its evidence to
  [doc/development/agent-lessons.md](doc/development/agent-lessons.md), and
  put the operational step in the runbook or page where an agent meets it.
- **Cross-link**: every page has an inbound link and is reachable from
  `doc/index.md`. Sources are never rewritten; newer pages supersede them.
- **Lint**: [doc/runbooks/wiki-lint.md](doc/runbooks/wiki-lint.md).

## Issue tracking with `bd`

Work items live in [`bd`](https://github.com/gastownhall/beads) (Dolt
database in `.beads/`, ID prefix `koc-`); the wiki holds the narrative.
Reference ticket IDs from wiki pages and doc paths from tickets.

```bash
bd ready                                   # unblocked work
bd show <id>                               # details + comments
bd create "Title" --id koc-<area>-<task> --type task --priority 2 --description "..."
bd dep add <child> <epic> --type parent-child   # --id and --parent cannot be combined
bd update <id> --claim
bd comments add <id> "Handoff: state / blockers / next step"
bd close <id> --reason "..."
bd dolt push                               # after every bd write; no arguments
```

- Use semantic IDs: `koc-<epic>[-<task>]`, e.g. `koc-v2-motord-driver`.
- Close a ticket only when its work is done, or after filing new tickets
  that carry the deferred work with full context.
- bd writes modify the tracked `.beads/interactions.jsonl`; include it in
  the commit before `git pull --rebase`.
- `bd prime` and the `.claude/settings.json` hooks need the Dolt server:
  `bd dolt start`.

## Ending a session

Work is complete when it is pushed:

1. File tickets for remaining work; add a handoff comment to each active
   ticket.
2. Run the checks for what changed (tests, pre-commit).
3. `git pull --rebase && bd dolt push && git push`, then `git status` shows
   up to date with `origin`.

## `external/`: read-only reference clones

Upstream repositories cloned for reading live in `external/`, listed in
[external/readme.md](external/readme.md). Read them and link to them;
keep them unmodified, out of the build, and uncommitted. Each clone gets an
analysis page `doc/sources/YYYY-MM-DD-<name>-analysis.md`.

## Shell commands

Use non-interactive forms: `cp -f`, `mv -f`, `rm -f`,
`ssh -o BatchMode=yes`, `scp -o BatchMode=yes`, `apt-get -y`.

<!-- BEADS-INTEGRATION:BEGIN -->
<!-- Managed by bd (beads). Do not hand-edit between these markers. -->
<!-- BEADS-INTEGRATION:END -->
