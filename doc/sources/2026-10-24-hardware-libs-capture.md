# Hardware Libraries Capture — BrickPi & Kinect — 2026-10-24

Raw evidence for [brickpi-interface](../architecture/brickpi-interface.md) and
[kinect-interface](../architecture/kinect-interface.md): upstream repo status,
protocol facts, and v1 usage. Repos cloned read-only into `external/`
(manifest: `external/readme.md`).

## Upstream repo status (clone dates = 2026-10-24, all `--depth 1`)

| Repo | HEAD | Last commit | Note |
|---|---|---|---|
| `DexterInd/BrickPi` | `0f4b64c` | 2021-08-16 | mega-repo: Software/{BrickPi_Python, BrickPi_C, BrickPi_Scratch}, Firmware_BrickPi, Hardware Design |
| `DexterInd/BrickPi_Python` | `ff5706c` | 2017-01-19 | stale separate lib |
| `DexterInd/BrickPi_C` | `a314daf` | 2017-01-19 | README-only stub |
| `OpenKinect/libfreenect` | `09a1f09` | 2024-01-06 | Kinect v1 driver, maintenance-only |
| `xanium4332/libfreenect-sys` | `21bdc41` | 2015-10-10 | raw Rust bindings |
| `xanium4332/libfreenect-rs` | `a5c0eb9` | 2015-10-10 | safe Rust wrapper (same author) |
| `rust-embedded/rust-i2cdev` | `39f419b` | 2026-02-11 | actively maintained |
| `serialport/serialport-rs` | `cb9822a` | 2026-09-08 | actively maintained |

Submodule pins in this repo (`dependencies/`): BrickPi `132ff6e`, libfreenect
`f63bb6a` — **not initialized locally or on the robot** (empty dirs); the
robot's `BrickPi` comes from site-packages installed by the old
`install_dependencies.sh`.

## BrickPi protocol facts (from `external/BrickPi/Software/…`)

- `BrickPi_Python/BrickPi.py:44-47` — `ser.port='/dev/ttyAMA0'`,
  `ser.baudrate = 500000` → **UART**, not I2C. `import serial` (pyserial),
  plus `ir_receiver_check` that refuses to run with lirc-rpi enabled.
- `BrickPi.py:127` — `Address = [1, 2]`: two ATmega3250 destinations.
- `BrickPi.py:107-111` / `BrickPi.h` `MSG_TYPE_*`: 1 CHANGE_ADDR,
  2 SENSOR_TYPE, 3 VALUES (motors out, encoders+sensors in),
  4 E_STOP (float motors immediately), 5 TIMEOUT_SETTINGS (32-bit firmware
  deadman).
- `BrickPi.py:690-716` (`BrickPiTx`) — TX frame: `[dest][checksum][count][payload]`,
  `checksum=(dest+count+Σpayload) mod 256`. `BrickPiRx` (730-791) — RX frame:
  `[checksum][count][payload]`, `checksum=(count+Σpayload) mod 256`.
- `BrickPi.h:298-331` — `BrickPiChangeAddress`, `BrickPiSetTimeout`
  (timeout sent to **both** chips; v1 never sets it — `BrickPi.Timeout = 0`).
- `BrickPi.py:88-101` — US-sensor I2C workaround: `US_I2C_SPEED=10`,
  `LEGO_US_I2C_ADDR=0x02`, data reg `0x42`; `TYPE_SENSOR_ULTRASONIC_CONT`
  remapped to manual I2C to dodge the firmware MSB corruption (±128 errors).
- `BrickPi.h:64-66` — motor modes PWM/SPEED/POSITION; `MotorSpeed` signed
  −255…255. `BrickPi.py:196-198` — `MotorEnable`, `Encoder`, `Sensor`,
  `SensorType` arrays on the global `BrickPi` struct.

## v1 usage facts

- `app/server/brick_pi_wrapper.py:8-12` — imports `smbus2` (**unused**) and
  only constants + `BrickPiSetup/BrickPiSetupSensors/BrickPiUpdateValues`
  from `BrickPi`.
- `install_dependencies.sh:57-62` — `sed -i 's/ttyAMA0/ttyS0/g'` on
  `BrickPi.py` (RPi3 mini-UART), then `pip install
  dependencies/BrickPi/Software/BrickPi_Python/`; matches
  `init_uart_clock=32000000` + `enable_uart=1` in `/boot/config.txt`.
- `install_dependencies.sh:65-77` — libfreenect from submodule source,
  `cmake -DBUILD_PYTHON3=ON -DBUILD_CV=ON`, symlink `freenect.so` into
  site-packages (robot venv shows `freenect 0.0.0`).
- `app/server/kinect_process.py` — sync API only: `sync_get_video` /
  `sync_get_depth` in an unthrottled loop; tilt functions commented out
  (return 0).

## libfreenect API surface relevant to v2 (`include/libfreenect.h`)

`freenect_process_events[_timeout]` :260/272 · `num_devices` :282 ·
`open_device` :344 · `open_device_by_camera_serial` :357 ·
`set_depth_buffer` :436 · `set_video_buffer` :448 · `start/stop_depth/video`
:457-484 · `set_tilt_degs` :527 · `set_led` :548 · video/depth mode lists
:568-662. Callbacks + buffer ownership give a push model; the sync API v1
uses is a thread + double-buffer wrapper over these.

## libfreenect-rs sketch (`src/lib.rs`, 873 lines)

Maps `LogLevel`/`Resolution` over `libfreenect_sys`; error enum
`LibraryReturnCode/NullPtr/FrameFormatMismatch`; pre-2018 edition idioms
(`Rc<RefCell>` for callbacks) — viable starting point, needs modernization
and a fresh `-sys` regen with current bindgen.
