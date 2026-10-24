# BrickPi+ Interface

## Purpose

How the Raspberry Pi talks to the BrickPi+ motor/sensor board, what the v1
code actually uses, and what a low-level v2 driver must implement. Facts are
read from the upstream sources cloned in `external/` (see
[raw capture](../sources/2026-10-24-hardware-libs-capture.md)).

## Context

The BrickPi+ is a HAT with **two ATmega3250 microcontrollers** that each own
two LEGO motor ports (A/B/C/D) and two sensor ports (1–4). The Pi talks to
them over **UART, not I2C** — a common misconception that this analysis
corrected (see below).

## The wire protocol (verified from source)

- **Transport**: `/dev/ttyAMA0` at **500000 baud**, 8N1 — patched to `ttyS0`
  on RPi 3 (mini-UART), hence `init_uart_clock=32000000` in `config.txt` and
  the `sed -i 's/ttyAMA0/ttyS0/g'` hack in `install_dependencies.sh`. The
  `dtoverlay=brickpi` device tree also claims the UART and checks the IR
  receiver (`BrickPi.py` refuses to start if `lirc-rpi` is enabled).
- **Framing** — TX: `[dest][checksum][count][payload…]` with
  `checksum = (dest + count + Σpayload) mod 256`; RX: `[checksum][count][payload…]`
  with `checksum = (count + Σpayload) mod 256` (`BrickPi.py::BrickPiTx/Rx`,
  lines 690–791).
- **Destinations**: UART addresses **1 and 2** (`BrickPi.Address = [1, 2]`) —
  one per ATmega; each handles "its" two motors and two sensors.
- **Message types** (`BrickPi.h`):
  | Type | Meaning |
  |---|---|
  | 1 `CHANGE_ADDR` | retarget a chip's UART address |
  | 2 `SENSOR_TYPE` | per-port sensor mode |
  | 3 `VALUES` | set 2 motor speeds, return encoders + sensors (the 10 ms loop message) |
  | 4 `E_STOP` | **float motors immediately** (hardware e-stop) |
  | 5 `TIMEOUT_SETTINGS` | 32-bit firmware deadman — stop motors if no `VALUES` within the window |
- **Motors**: `TYPE_MOTOR_PWM/SPEED/POSITION`; speeds are signed −255…255;
  encoders are cumulative ±ticks (360/motor-shaft-rev; persist while powered).
- **Sensors**: raw (0–31 analog modes incl. `LIGHT_ON = 0x09`), touch,
  ultrasonic (continuous/single-shot), NXT color, `TYPE_SENSOR_I2C` for
  sensor-level I2C devices (the BrickPi firmware clocks I2C to the sensor).
- **Known firmware quirk**: the hardcoded US-sensor I2C speed corrupts the
  MSB (±128 errors); `BrickPi.py` works around it by re-configuring
  `TYPE_SENSOR_ULTRASONIC_CONT` as a manual `TYPE_SENSOR_I2C` device
  (`US_I2C_SPEED = 10`, addr 0x02, data reg 0x42). Our v1 wrapper relies on
  this fix being inside `BrickPi.py`.

## What v1 actually uses

- The **Python library** (`BrickPi.py`, last upstream change 2015) installed
  from `dependencies/BrickPi/Software/BrickPi_Python/` into site-packages; the
  wrapper imports only constants + `BrickPiSetup/SetupSensors/UpdateValues`
  and the global `BrickPi` struct (`app/server/brick_pi_wrapper.py:10-12`).
- `BrickPiWrapper` drives it from a 100 ms thread: set `MotorSpeed`, call
  `BrickPiUpdateValues()` (one `VALUES` exchange per ATmega per cycle), read
  `Encoder`/`Sensor` arrays back.
- `import smbus2` in the wrapper is **vestigial** — no I2C happens on the Pi
  side; the brickpi dtoverlay's i2c nodes are for the board's own buses.
- The software deadman (`COMMAND_QUEUE_GRACE = 3`) exists because v1 never
  sets the **firmware** timeout (`BrickPi.Timeout = 0` default → disabled).

## Maintenance status (legacy)

| Repo | Last commit | State |
|---|---|---|
| `DexterInd/BrickPi` (pin `132ff6e`) | 2021-08 | dormant; contains Python/C libs + firmware |
| `DexterInd/BrickPi_Python` | 2017-01 | separate, stale |
| `DexterInd/BrickPi_C` | 2017-01 | README-only stub |

Dexter Industries was absorbed into Modular Robotics; BrickPi v1/+ is
discontinued hardware (BrickPi3/SPIKit are the successors, different
protocol). No upstream fixes are coming — treat the protocol as frozen.

## V2 strategy (low-level)

- **Rewrite the driver in Rust** (`motord`): `serialport-rs` (maintained,
  2026) at 500000 baud on `/dev/ttyS0`, speaking the framing above. The
  protocol is small: 5 message types, one checksummed frame per ATmega per
  cycle. Reference implementation = `BrickPi.py` + `BrickPi.h` in
  `external/BrickPi/`.
- **Enable the firmware deadman** (`TIMEOUT_SETTINGS`) — hardware-level motor
  stop, removing the need for the wrapper's software grace hack.
- **Keep `E_STOP` wired** to a client command and to `motord` crash handlers
  (Drop/panic hooks).
- **Differential tests**: run v1 `BrickPi.py` and the Rust driver side by side
  on the robot (same motor/sensor commands, compare encoder/sensor reads) —
  the `differential-bootstrap` pattern; v1 becomes the oracle.
- **Port the US-sensor I2C workaround** verbatim.
- Pin `robot-estop`: motors must float on daemon crash (Rust `Drop` +
  watchdog), not just on idle timeout.

## References

- `external/BrickPi/Software/BrickPi_Python/BrickPi.py` (protocol source of truth, py)
- `external/BrickPi/Software/BrickPi_C/Drivers/BrickPi.h` (protocol, C)
- `external/serialport-rs/` (v2 transport crate), `external/rust-i2cdev/` (kept for future I2C peripherals)
- [Robot hardware](robot-hardware.md) · [2026-10-24 capture](../sources/2026-10-24-hardware-libs-capture.md)
