# Hardware Lifecycle and Robot Reachability — 2026-10-28

Raw capture for the decision to pause active development
([ADR-0001](../decisions/ADR-0001-pause-active-development.md)).

## Lifecycle of each part of the robot

| Part | On the robot | Lifecycle fact | Reference |
|---|---|---|---|
| Depth camera | Xbox 360 Kinect (v1) | Microsoft stopped manufacturing Kinect in October 2017 | The Verge, 2017-10-25, "Microsoft kills off Kinect, stops manufacturing it" |
| Kinect driver | libfreenect (community) | No vendor support; the v1 Python bindings and the `freenect` crate are unmaintained (see [hardware libs capture](2026-10-24-hardware-libs-capture.md)) | — |
| Motor board | Dexter Industries BrickPi+ (UART protocol) | Superseded by the BrickPi3 (SPI protocol) in April 2017; BrickPi+ code is not maintained upstream | Dexter Industries, "The New BrickPi3" (2017-04) |
| Motors and sensors | LEGO Mindstorms NXT 2.0 (set 8547), ~20 years old | LEGO discontinued the whole Mindstorms line at the end of 2022 | PCMag, 2022-10-28, "Lego Mindstorms Robotics Kits Are Being Discontinued" |
| Track and frame | LEGO Technic 42055 parts | Mechanical parts; no electronics | — |
| Accelerator | Intel Movidius NCS1 | NCSDK archived in 2019; OpenVINO never supported NCS1 (see [NCS state](2026-10-24-ncs-state.md)) | — |
| Computer | Raspberry Pi 3, 1 GB RAM, one USB 2.0 bus shared by Ethernet and every USB device | Hardware works; the USB bus is the bottleneck behind the Kinect "Stream 70" storms | [robot hardware](../architecture/robot-hardware.md) |
| Operating system | Raspbian 9 "stretch" | Debian 9 long-term support ended in June 2022 | Debian LTS |
| Server runtime | Python 3.5.3 | Python 3.5 reached end of life in September 2020 | python.org |

The v2 Rust daemons (`robot/`) avoid the Python 3.5 pin but still target
the BrickPi+, Kinect and Raspberry Pi 3.

## Robot reachability on 2026-10-28

- `ssh pi@192.168.10.187`: connection timed out.
- `ping 192.168.10.187`: 3 packets sent, 0 received.
- The robot was not reached; its state was not observed this day.

Last observed state (2026-10-26, after the drive re-run): v1 server
running, motord stopped, motors stopped, turret encoder C≈42308
(envelope center 42298), robot 0.55 m (Kinect) from the obstacle ahead.
