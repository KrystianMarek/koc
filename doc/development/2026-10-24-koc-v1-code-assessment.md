# K.O.C v1 Code Assessment — 2026-10-24

Point-in-time assessment of the v1 codebase (baseline for the v2 rebuild).
Findings from code reading plus the live hardware session
([state capture](../sources/2026-10-24-robot-state-capture.md)).

## What v1 is

Python 3.5 (Raspbian stretch pin), ZeroMQ for all transport
(REQ/REP handshake :5556, PUB/SUB telemetry+video :5559, PUSH/PULL commands
:5560, internal PUSH/PULL :5557/:5558), pickle+zlib serialization, PyQt5
client, threads for BrickPi/handshake/commands and a process for Kinect.

## Strengths worth keeping in v2

- Clean client/server split; client only needs the robot IP; multi-client
  command path (robot binds, clients connect).
- Lazy hardware startup: first client handshake triggers BrickPi+Kinect.
- Central `Config` with env overrides; per-domain requirements files; solid
  `doc/` from the 2026-01 refactor.
- The implicit deadman in `BrickPiWrapper` (zero speeds after ~3 empty cycles)
  is the right safety instinct, even though undocumented (surprised us in the
  [turret test](../sources/2026-10-24-robot-state-capture.md)).

## Issues found

| # | Issue | Where | Status |
|---|---|---|---|
| 1 | Package `app/Networking` (PascalCase) vs lowercase imports everywhere — breaks any case-sensitive fresh deploy (worked on robot only because its copy was already lowercase) | `app/` | **fixed this session** (git mv staged, uncommitted) |
| 2 | `pickle` over the network — RCE on untrusted LAN | `app/common/serialization.py` | open (acceptable v1; v2 must not inherit) |
| 3 | Commands encoded as partial `TelemetryPacket`s — overloads telemetry type as command type; reader must know which fields are meaningful per command | `app/server/command_receiver.py` | open (v2: dedicated command type) |
| 4 | `TelemetryClient.on_telemetry_packet` overwrites the pyqtSignal attribute (`self.telemetry_packet_signal = packet`) — latent landmine | `app/client/telemetry_client.py` | open |
| 5 | Kinect tilt API stubbed out (returns 0, commented code) | `app/server/kinect_process.py` | open (document) |
| 6 | Kinect capture unthrottled + fork inherits parent ZMQ sockets → server wedges silently after minutes (5.7 GB/33 min, 139% CPU, inherited fds visible in `ss`) | `app/server/kinect_process.py` + `server.py` | `bd` `koc-hw-kinect-wedge` |
| 7 | `sync.sh` deploys to wrong dir; missing excludes (.beads/.claude/external) | `sync.sh` | `bd` `koc-hw-sync-target` |
| 8 | No automated tests, no CI, no lint config | repo | open (v2 gates from day one) |
| 9 | Deadman semantics implicit/undocumented (COMMAND_QUEUE_GRACE) | `app/server/brick_pi_wrapper.py` | documented now (hardware page) |
| 10 | Legacy weight: flat `requirements.txt` vs `requirements/{base,client,server}.txt`, deprecated `install_dependencies.sh`, NCS stack | repo | open |

## Verdict

v1 is a sound prototype with good bones (topology, config, safety instinct)
but prototype-grade transport and typing, no update story, and no test floor.
v2 should keep the *architecture lessons* (they match Microduck's independently)
and replace the *mechanics* — see [v2 direction](../vision/v2-microduck-stack.md).

## Related

- [Robot deployment state](robot-deployment.md) · [Robot hardware](../architecture/robot-hardware.md)
- `bd`: `koc-hw-kinect-wedge`, `koc-hw-sync-target`
