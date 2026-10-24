# Robot State Capture — 2026-10-24

Raw observations from the first hardware session against the live robot
(`192.168.10.187`, user `pi`, passwordless SSH from the dev machine).
Condensed transcripts; the synthesized pages are
[robot-hardware](../architecture/robot-hardware.md) and
[robot-deployment](../development/robot-deployment.md).

## System survey (SSH)

```text
hostname    raspberrypi3
os          Raspbian GNU/Linux 9 (stretch), kernel 4.19.66-v7+ (2019), armv7l
python      3.5.3 (/usr/bin/python3)
uptime      up 3:09 (rebooted 2026-10-24 ~18:09), load 1.47 during kinect storm / 0.00 idle
memory      925 MiB total, ~775 MiB available
disk        / at 50% (6.9G/15G)
temp        53.2°C idle
usb         045e:02ae Xbox NUI Camera / 02b0 NUI Motor / 02ad NUI Audio (Kinect, all 3 ifs)
            03e7:2150 Intel Movidius Myriad (NCS stick present)
            0409:005a NEC hub, 05e3:0608 Genesys hub  (Kinect is behind hubs)
config.txt  dtoverlay=brickpi, dtparam=brickpi_battery=okay, init_uart_clock=32000000
            dtparam=i2c_arm=on, dtparam=spi=on, enable_uart=1
groups(pi)  ... gpio i2c spi ...
services    sshd :22, samba :445/:139, VNC :5900, shellinabox :4200, cups :631
            no koc services, no crontab, no custom systemd units
tools       i2cdetect NOT installed
```

## Deployment survey

```text
~/rpi_lego_robot/   the deployment (plain rsync copy, NOT a git repo)
                    layout matches local main; zero code drift (timestamps only)
~/brickpi/          old 2018-era code (koc_server.py, koc_gui.py, koc_q5_gui.py)
venvs               pi_robot3  py3.5.3 server env: freenect, pyzmq 17.1.2, numpy 1.15.2,
                               psutil, netifaces, PyYAML — all imports OK
                    pi_robot   py2.7.13 legacy: BrickPi, freenect, numpy 1.15.1
local sync.sh       rsync -> pi@$ROBOT_IP:/home/pi/<basename-of-local-dir>
                    local dir is "koc" but robot dir is "rpi_lego_robot" -> mismatch
```

## Kinect stream probe (first run, after server start)

```
handshake ok: HeartbeatResponse (seq 1)
telemetry: seq=1 voltage=8.854V temp=52.616C
  motors: left 0/0 right 0/0 turret 0/0 (speed/desired)
  system: cpu=0.3%, ram=17.9%
  sensors: ultrasound=255, color=789
kinect seq=0: video (480, 640, 3) uint8, depth (480, 640) uint16 (raw min 558 / max 2047)
frame content: rgb mean=103.2 std=77.1 (rich image); depth 100% valid px
```

Battery 8.854 V proves BrickPiWrapper started and reads I2C. Raw depth values are
disparity (0–2047, >1023 invalid).

## Turret probe — single command (the "0.2 s twitch")

Sent ONE `TurretRight(80)`, probe then idled 2 s, then `TurretReset`:

```
baseline turret encoder: 0
encoder: baseline=0 during=[-123 .. 0] (span 123) final=-122
net rotation: -122 ticks
frame difference (mean abs): 16.5
```

Physical observation (user): rotation took ~0.2 s, not 2 s. Cause: deadman —
`BrickPiWrapper` re-sends zero speeds after `COMMAND_QUEUE_GRACE=3` command-less
cycles (~0.3 s). A single command is only a twitch.

## Turret probe — streamed commands (fixed probe)

Streamed `TurretRight(80)` at ~10 Hz for 2 s, then `TurretReset`:

```
baseline turret encoder: -122        <- encoder PERSISTED across server restart
streamed 19 TurretRight packets (~9.5 Hz)
encoder: baseline=-122 during=[-1147 .. -122] (span 1025) final=-1147
net rotation: -1025 ticks            <- ~510 ticks/s ~ 85 rpm (360 ticks/rev motor shaft)
frame difference (mean abs): 46.0
```

## Server wedge (found between probe runs)

The first server instance stopped publishing after ~15 min (no errors logged):

```text
ps     pid 1986 server 6.6% cpu; pid 2037 (kinect child) 139% cpu
ss     kinect->aggregator :5558 bytes_acked=5,697,956,329 (5.7 GB in ~33 min)
       360,448 bytes stranded unread in aggregator's TCP recv buffer
       aggregator BrickPi :5557 last wrapper send 17.8 min before check
log    flooded with libfreenect "[Stream 70] Invalid magic / resyncing" (C stderr)
```

Diagnosis: KinectProcess forks AFTER the parent's ZMQ sockets/context exist
(child visibly owns inherited fds on :5557 in `ss` output) — undefined ZMQ
behavior; plus the unthrottled capture loop saturates CPU/USB; Kinect sits
behind two USB hubs aggravating packet loss. Server restart restored normal
operation. (Bugs filed in `bd`: `koc-hw-kinect-wedge`, `koc-hw-sync-target`.)
