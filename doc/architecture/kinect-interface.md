# Kinect (Xbox 360) Interface

## Purpose

How v1 captures video/depth from the Kinect, what the driver stack is, its
legacy status, and what a low-level v2 capture daemon should use.

## Context

The Kinect 360 (USB: Camera `045e:02ae`, Motor `02b0`, Audio `02ad`) is mounted
on the turret. v1 captures 480×640 RGB + 480×640 uint16 depth (raw
*disparity*, 0–2047). Audio and the tilt motor are enumerated but unused
(tilt stubbed to 0 in `kinect_process.py`).

## The v1 stack

- **libfreenect** (OpenKinect) — the only open driver for Kinect v1. Built
  from the `dependencies/libfreenect` submodule with
  `cmake -DBUILD_PYTHON3=ON`; the resulting `freenect.so` CPython extension
  lands in site-packages (`freenect 0.0.0` in the robot's venv).
- **`kinect_process.py`** uses only the *sync* convenience API:
  `sync_get_video(index)` / `sync_get_depth(index)` in an **unthrottled**
  loop, compressing each frame with zlib and PUSH-ing it — the source of the
  5.7 GB/33 min flood and the wedge (`koc-hw-kinect-wedge`).
- Internally the sync API spawns a thread running the callback-driven C API
  (`freenect_process_events`, per-frame callbacks into double buffers) and
  hands out the latest frame — so v1 already pays the threading cost without
  controlling it.

## The C API surface a v2 `camerad` would use

(verified in `external/libfreenect/include/libfreenect.h`)

- `freenect_init` / `freenect_open_device` (+ `num_devices`)
- `freenect_set_depth_mode` / `set_video_mode` (frame_mode list: resolutions,
  buffered formats — depth can be raw 11-bit, mm, or registered; video RGB/YbYbIr)
- `freenect_set_depth_buffer` / `set_video_buffer` + `set_depth_callback` /
  `set_video_callback` → **push model, no polling**
- `freenect_start_depth` / `start_video` / `stop_*`
- `freenect_process_events[_timeout]` — the event loop (or its own thread)
- `freenect_set_tilt_degs` / `get_tilt_state` / `set_led` — the motor/Audio
  interfaces, currently unused by K.O.C

## Maintenance status (legacy — plan for it)

| Item | Status |
|---|---|
| `OpenKinect/libfreenect` | last commit **2024-01**; no releases since 0.7.x era; essentially maintenance-only |
| Kinect v1 hardware | discontinued 2015; sensor needs USB 2.0 + external power; ours hangs behind **two hubs** (resync storms) |
| `libfreenect2` | Kinect *v2* only — not applicable |
| Rust bindings | `libfreenect-sys` + `libfreenect-rs` (xanium4332, 2015) exist but are pre-2018-edition; usable as a starting point, expect modernization |

Conclusion: the driver is frozen but functional; the *hardware* is the
flight risk (age, hub topology, power). V2 should abstract capture behind an
interface so the Kinect can be swapped for a modern depth camera (e.g. an
Orbbec/RealSense class sensor) without touching `motord`/clients.

## V2 strategy (low-level)

- **`camerad` in Rust with FFI to libfreenect**: callback-driven API +
  explicit `process_events_timeout` loop; **throttle to a fixed fps**
  (10–15) and latest-frame-wins semantics — fixes `koc-hw-kinect-wedge`.
- Start from `external/libfreenect-rs` + `libfreenect-sys` (re-gen `-sys`
  with current `bindgen`, modernize the safe layer) or bind our own minimal
  subset (~15 functions above) — smaller than it looks.
- **Publish features, not frames** where possible: the control path needs
  turret-relative geometry, not raw 600 KB frames; frames go only to the
  client stream (compressed, rate-limited).
- **USB hygiene**: dedicated port (no hubs), `libusb` udev rules already in
  `dependencies/66-kinect.rules`.
- Keep the raw-disparity → meters conversion in `FrameProcessor`
  (`raw_depth_to_meters`) as the parity reference for v2's depth math.

## References

- `external/libfreenect/include/libfreenect.h` — C API
- `external/libfreenect-rs/src/lib.rs` — safe wrapper sketch (2015)
- [Robot hardware](robot-hardware.md) · [2026-10-24 capture](../sources/2026-10-24-hardware-libs-capture.md)
- Bug: `koc-hw-kinect-wedge`
