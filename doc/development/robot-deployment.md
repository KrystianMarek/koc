# Robot Deployment & Software State

State of the software on the robot (192.168.10.187) as of 2026-10-24. Raw
evidence: [state capture](../sources/2026-10-24-robot-state-capture.md).

## Deployment topology

- **Code**: `~/rpi_lego_robot/` on the robot — a plain rsync copy, *not* a git
  repo. Local `sync.sh` rsyncs there (excluding `.git`, `.venv`, `doc`,
  `testing`, `pictures`, heavy submodule parts). Content currently matches
  local `main` with zero drift.
- **Environments**: `~/.virtualenvs/pi_robot3` (Python 3.5.3) is the server
  env — freenect, pyzmq 17.1.2, numpy 1.15.2, psutil, netifaces, PyYAML all
  verified importable. `pi_robot` is legacy Python 2.7. `~/brickpi/` holds the
  old 2018-era code. The uv-based `scripts/setup-*.sh` will not run on stretch;
  the existing venvs are the working path.
- **Process**: started manually — `nohup python server.py`, logs to
  `/tmp/koc_server.log`. No systemd unit, no crontab: a reboot leaves the
  robot idle until someone SSHes in.
- **Client side**: local `.venv` (Python 3.14) with pyzmq/numpy/Pillow/
  netifaces/PyYAML for the headless probes in `testing/`. PyQt5 not installed
  locally yet (GUI client untested from here).

## Known issues (open)

| Issue | Impact | Tracker |
|---|---|---|
| Kinect capture unthrottled + `KinectProcess` forks after parent ZMQ setup (inherited fds confirmed via `ss`) | Server wedges after minutes: telemetry stops silently, Kinect child pegs CPU (139%) and floods the aggregator (5.7 GB/33 min) | `bd` `robot-kinect-wedge` |
| `sync.sh` targets `~/koc` (basename of local dir) but robot uses `~/rpi_lego_robot`; also doesn't exclude `.beads/`, `.claude/`, `external/` | Next sync would create a duplicate tree on the robot / push junk | `bd` `robot-sync-target` |
| Kinect behind two USB hubs | libfreenect resync storms ("Invalid magic" log spam), likely contributes to the wedge | part of `robot-kinect-wedge` |
| `app/Networking` PascalCase vs lowercase imports | Broke local headless probe; would break any fresh case-sensitive deploy (the robot's copy is already correct) | **fixed locally** (git mv staged, uncommitted) |
| Pickle over ZMQ | RCE if either endpoint is untrusted; fine on a trusted LAN | consideration |
| No automated tests / CI, no lint config | Pure logic (depth math, command translation) unverified | — |

## Operating the robot from here

```bash
# start (survives ssh disconnect thanks to setsid+nohup)
ssh pi@192.168.10.187 'cd ~/rpi_lego_robot && setsid nohup \
  ~/.virtualenvs/pi_robot3/bin/python server.py > /tmp/koc_server.log 2>&1 < /dev/null &'

# headless end-to-end checks from the dev machine
.venv/bin/python testing/kinect_stream_probe.py [ip]     # handshake + telemetry + frame
.venv/bin/python testing/turret_rotate_probe.py [ip] [speed] [seconds]  # stream + encoder verify
```

Watch out: `pkill -f "server.py"` self-matches the invoking ssh shell — use an
anchored pattern (`pkill -f "^/home/pi/...python server.py"`).

## References

- [Robot hardware](../architecture/robot-hardware.md) — port map, measured dynamics
- [Networking](../networking.md) — port/protocol map
- [Project structure](project-structure.md) if present
