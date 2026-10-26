# Robot Deployment & Software State

State of the software on the robot (192.168.10.187) as of 2026-10-26. Raw
evidence: [state capture](../sources/2026-10-24-robot-state-capture.md),
[turret centering run](../sources/2026-10-26-turret-centering-run.md).

## Deployment topology

- **Code**: `~/rpi_lego_robot/` on the robot — a plain rsync copy, *not* a git
  repo. Local `sync.sh` rsyncs there, excluding `.git`, `.venv`, `.beads`,
  `.claude`, `.factory`, `.codegraph`, `external`, `testing`, `doc`,
  `pictures` and the heavy NCS submodule parts. Probes in `testing/` are
  therefore copied by hand (`scp testing/<probe>.py pi@…:~/rpi_lego_robot/testing/`).
- **Environments**: `~/.virtualenvs/pi_robot3` (Python 3.5.3) is the server
  env — freenect, pyzmq 17.1.2, numpy 1.15.2, psutil, netifaces, PyYAML all
  verified importable. `pi_robot` is legacy Python 2.7. `~/brickpi/` holds the
  old 2018-era code. The uv-based `scripts/setup-*.sh` will not run on stretch;
  the existing venvs are the working path.
- **v1 process**: started manually (see below), logs to
  `/tmp/koc_server.log`, plus two `multiprocessing` spawn children. No systemd
  unit, no crontab: a reboot leaves the robot idle until someone SSHes in.
- **v2 Rust workspace** (`robot/`: `brickpi`, `rpc`, `motord`, `robotctl`):
  rsynced separately and **built on the robot** with rustup
  (rustc/cargo 1.99.1, armv7) — about 45 s incremental, ~2 min clean. This
  deviates from the plan's cross-compile decision; it has been fast enough.
  Binaries: `~/rpi_lego_robot/robot/target/release/{motord,robotctl}`.
  `motord` is not supervised; probes start and stop it.
- **Client side**: local `.venv` (Python 3.14) with pyzmq/numpy/Pillow/
  netifaces/PyYAML for the headless probes in `testing/`. PyQt5 not installed
  locally yet (GUI client untested from here).

## UART ownership

`motord` and the v1 server both drive `/dev/ttyS0`; run exactly one. Stop the
v1 server (and its spawn children) before starting `motord`, and stop `motord`
before restarting v1. Kinect measurements still need the v1 server (no
`camerad` yet), so Kinect-checked turret work alternates the two.

## Known issues (open)

| Issue | Impact | Tracker |
|---|---|---|
| Kinect behind two USB hubs | "Stream 70" resync storms; ~13–16 s recovery after motion. Capture throttling, spawn isolation and self-heal are deployed; the storms are physical | `bd` `koc-hw-kinect-wedge` |
| `motord` exits on SIGINT/SIGTERM without unlinking `/tmp/motord.sock` | Clients that test for the file see a dead daemon (the probe now checks with a real connect) | `bd` `koc-v2-motord-sockclean` |
| Turret cable wrap ≈ one turn relative to C=297 | No further left (encoder-positive) rotation; unwinding needs a 360° move (user approval) | [centering run](../sources/2026-10-26-turret-centering-run.md) |
| Stale tarballs in `~` on the robot (`NCSDK-1.12.01.01.tar.gz` is a 443 B S3 error XML; `ncappzoo_data.tar.gz` is a stub) | Misleading; a future NCS setup must use the documented mirror instead | cleanup chore |
| Pickle over ZMQ | RCE if either endpoint is untrusted; fine on a trusted LAN | consideration |
| No CI | Rust unit tests (`cargo test`) and pre-commit hooks run locally only | — |

## Operating the robot from here

```bash
# v1 server: start / stop. Start through $P so the literal "python server.py"
# never appears in the same command as the pkill pattern (it would match the
# remote shell itself and kill the command silently).
ssh pi@192.168.10.187 'P=/home/pi/.virtualenvs/pi_robot3/bin/python; cd ~/rpi_lego_robot && (setsid nohup $P server.py > /tmp/koc_server.log 2>&1 < /dev/null &)'
ssh pi@192.168.10.187 'pkill -f "python server.p[y]"; pkill -f "multiprocessing.spa[w]n"'

# v2 deploy + build
rsync -a --exclude target robot/ pi@192.168.10.187:/home/pi/rpi_lego_robot/robot/
ssh pi@192.168.10.187 'cd ~/rpi_lego_robot/robot && PATH=$HOME/.cargo/bin:$PATH cargo build --release'

# on the robot (P as above), v1 server stopped unless noted
$P testing/motord_parity_probe.py motord    # snapshots; starts motord if needed
$P testing/motord_parity_probe.py rel -375  # turret move in ticks: position-stopped, 15° cap
$P testing/kinect_bearing.py 61             # obstacle bearing; needs the v1 server UP; arg = sonar cm

# headless end-to-end checks from the dev machine (v1 server up)
.venv/bin/python testing/kinect_stream_probe.py [ip]
.venv/bin/python testing/turret_rotate_probe.py [ip] [speed] [seconds]
```

Gotchas:

- Redirect probe output to a file on the robot and `cat` it in the same
  command; long ssh commands that background jobs have lost their output.
- Turret: never accumulate more than ±90° without a visual check. The probe
  refuses single moves over 15°. Positive ticks = turret left (user CCW).
- Encoders persist while the BrickPi is powered; never assume 0 after a
  restart.

## References

- [Robot hardware](../architecture/robot-hardware.md) — port map, measured dynamics
- [BrickPi interface](../architecture/brickpi-interface.md) — protocol + motord
- [Networking](../networking.md) — port/protocol map
- [Project structure](project-structure.md)
