# Agent Lessons

Rules learned the hard way while agents worked on the live robot. Each one
cost time, data or hardware risk once. Read this before turret, probe or
daemon work; add a lesson here (with its evidence link) whenever a mistake
repeats or risks hardware, and put the operational rule in the runbook or
page where an agent will meet it.

## Turret and cables

| Rule | Evidence |
|---|---|
| The turret stays within 180° either way of camera-forward. Every turret writer goes through `app/server/turret_guard.py` or `robot/motord/src/guard.rs`. | [cable incident](../sources/2026-10-25-turret-cable-incident.md): 187° of accumulated rotation across tests wound the cable. |
| Position a turret by encoder position, re-reading it every ~20 ms and recomputing the direction; a timed burst is a velocity, not a position. | [centering run](../sources/2026-10-26-turret-centering-run.md): two time-boxed moves overshot by 1185 and 1247 ticks, then drove the wrong way. |
| Keep the intent refresh in its own 10 Hz thread, separate from position reads. | [cable incident](../sources/2026-10-25-turret-cable-incident.md): a slow snapshot starved the refresh past the 400 ms expiry; the crawl looked like a cable stall and a weak battery. |
| Before blaming hardware for a stall, prove the probe can command full speed (constant-pwm run, refresh cadence logged). | The 2026-10-25 "cable stalls" were probe artifacts ([centering run](../sources/2026-10-26-turret-centering-run.md)). |
| Find camera-forward with the Kinect bearing on a front obstacle, not by encoder arithmetic. The ratio is ~116.7 ticks/° by one estimate and 125 by another. | Target 297+45000 missed by ~25° ([centering run](../sources/2026-10-26-turret-centering-run.md)). |
| Approach a turret target from the same side every time. | Gear backlash ≈ 252 ticks ≈ 2° ([log 2026-10-25](../log.md)). |
| In the v1 server, stop by position, not by stopping the stream: queued commands keep the motor running. | A 10 Hz stream backed up the 100-deep queue and caused a 1641-tick miss ([swing90 run](../sources/2026-10-25-swing90-run.md)). |
| Encoders persist while the BrickPi is powered and reset to 0 on a power cycle; never assume a value after a restart. | [state capture](../sources/2026-10-24-robot-state-capture.md); the turret guard locks on a mismatch. |

## Daemons and protocol

| Rule | Evidence |
|---|---|
| Hold a shared lock only to copy data in or out; never across UART I/O or a sleep. | motord `snapshot` starved 8–46 s under motion ([brickpi interface](../architecture/brickpi-interface.md)). |
| A socket file is not a live daemon: test with a real connect and remove a stale file. | motord's signal exit leaves `/tmp/motord.sock` (`koc-v2-motord-sockclean`). |
| One process owns `/dev/ttyS0`: stop the v1 server before motord and the reverse. | Two writers corrupt each other's frames ([robot deployment](robot-deployment.md)). |
| When a reading looks physically impossible, hand-decode the raw frame before believing it. | An "encoder jump" was a decode-order bug: VALUES packs all count fields first ([log 2026-10-25](../log.md)). |
| Long-uptime failures: check open file descriptors (`ls /proc/<pid>/fd \| wc -l`). | `get_voltage()` leaked one SMBus fd per call and killed telemetry after 15–20 min ([robot hardware](../architecture/robot-hardware.md)). |

## Shell on the robot

| Rule | Evidence |
|---|---|
| Start the server as `$P server.py` and stop it with `pkill -f "python server.p[y]"`; the literal `python server.py` must never appear in the same command as the pattern. | `pkill -f` matched the ssh shell itself; commands died with rc 255 ([centering run](../sources/2026-10-26-turret-centering-run.md)). |
| Redirect probe output to a file on the robot and `cat` it in the same ssh call. | Backgrounded ssh jobs lost their output. |
| On a v1 restart, also kill `multiprocessing.spawn` children. | Orphaned Kinect children kept the camera and port 5558 ([log 2026-10-25](../log.md)). |

## Measurement

| Rule | Evidence |
|---|---|
| Read the sonar at rest; 255 means no echo in its cone, not a dead sensor. | Written off on 2026-10-25, reads 61 cm on 2026-10-26 (`koc-hw-sonar-dead` closed). |
| Find an obstacle in the Kinect image by segmenting at the sonar range; distrust a run that touches the frame edge. | Nearest-10 % pixel averaging jumped to the frame edges ([centering run](../sources/2026-10-26-turret-centering-run.md)). |
| Check the image handedness with a small known turret step before trusting a bearing sign. | The image is not mirrored: x > 320 means the turret points left of the target. |
| After motion, wait ~16 s before a Kinect measurement. | USB "Stream 70" storms respawn the capture child ([kinect interface](../architecture/kinect-interface.md)). |
| Recheck units on every derived rate. | "1.16 ticks/s per PWM unit" was a units error; the real figure is 6–8 ([robot hardware](../architecture/robot-hardware.md)). |

## Related

- [Turret centering runbook](../runbooks/turret-centering.md)
- [Robot deployment](robot-deployment.md) · [Robot hardware](../architecture/robot-hardware.md)
- [AGENTS.md](../../AGENTS.md)
