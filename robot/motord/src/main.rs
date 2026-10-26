//! motord - the BrickPi+ UART daemon.
//!
//! Owns /dev/ttyS0 exclusively. Runs a ~60 Hz VALUES exchange per ATmega,
//! exposes JSON-RPC 2.0 over a UDS socket. Clients send INTENTS (drive,
//! turret) that expire; the firmware deadman (TIMEOUT_SETTINGS) floats the
//! motors if motord itself dies. Sensors: PORT_1 color (10-bit raw), PORT_4
//! sonar (I2C workaround; 255 = no echo).
//!
//! Usage: motord [socket_path] [serial_dev] [loop_hz]

use brickpi::{
    build_tx, decode_values, estop_payload, parse_rx, sensor_setup_payload, timeout_payload,
    values_payload, SensorPort, ADDR_CHIP0, ADDR_CHIP1, TYPE_SENSOR_LIGHT_ON,
};
use rpc::{serve, Json, Outcome};
use std::sync::atomic::{AtomicBool, AtomicI32, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

const SERIAL_BAUD_FLAG: u32 = 0x1005; // Linux B500000 (libc lacks it on some targets)
const INTENT_EXPIRY_MS: u64 = 400; // v1 parity: commands streamed at ~10 Hz
const FIRMWARE_DEADMAN_MS: u32 = 300; // BrickPi.h: milliseconds
const RX_TIMEOUT_MS: i32 = 8; // per-exchange budget

struct Intents {
    left_pct: i64,
    right_pct: i64,
    turret_pct: i64,
    updated: Instant,
}

#[derive(Default, Clone, Copy)]
struct Cache {
    encoders: [i32; 4], // A, B, C, D
    color_raw: i32,
    sonar_raw: i32,
    loops: u64,
    errors: u64,
}

struct State {
    intents: Mutex<Intents>,
    estop: AtomicBool,
    cache: Mutex<Cache>,
    started: Instant,
}

static SERIAL_FD: AtomicI32 = AtomicI32::new(-1);

const ESTOP_CHIP0: [u8; 4] = [1, 6, 1, 4]; // build_tx(1, [4])
const ESTOP_CHIP1: [u8; 4] = [2, 7, 1, 4];

extern "C" fn on_signal(_sig: i32) {
    // Async-signal-safe: write(2) only. Float the motors on SIGINT/SIGTERM.
    let fd = SERIAL_FD.load(Ordering::Relaxed);
    if fd >= 0 {
        unsafe {
            libc::write(fd, ESTOP_CHIP0.as_ptr() as *const libc::c_void, 4);
            libc::write(fd, ESTOP_CHIP1.as_ptr() as *const libc::c_void, 4);
        }
    }
    unsafe { libc::_exit(0) };
}

fn open_serial(dev: &str) -> i32 {
    let path = std::ffi::CString::new(dev).expect("dev path");
    let fd = unsafe {
        libc::open(path.as_ptr(), libc::O_RDWR | libc::O_NOCTTY | libc::O_NONBLOCK)
    };
    if fd < 0 {
        panic!("cannot open {}", dev);
    }
    let mut termios: libc::termios = unsafe { std::mem::zeroed() };
    if unsafe { libc::tcgetattr(fd, &mut termios) } != 0 {
        panic!("tcgetattr failed");
    }
    unsafe {
        libc::cfmakeraw(&mut termios);
        libc::cfsetispeed(&mut termios, SERIAL_BAUD_FLAG as libc::speed_t);
        libc::cfsetospeed(&mut termios, SERIAL_BAUD_FLAG as libc::speed_t);
        termios.c_cflag |= libc::CLOCAL | libc::CREAD;
        termios.c_cflag &= !libc::CRTSCTS;
        termios.c_cc[libc::VMIN] = 0;
        termios.c_cc[libc::VTIME] = 0;
        libc::tcsetattr(fd, libc::TCSANOW, &termios);
        libc::tcflush(fd, libc::TCIOFLUSH);
    }
    fd
}

fn write_frame(fd: i32, frame: &[u8]) -> bool {
    let n = unsafe { libc::write(fd, frame.as_ptr() as *const libc::c_void, frame.len()) };
    n == frame.len() as isize
}

/// Read exactly `want` bytes within the remaining budget. Returns read count.
fn read_exact(fd: i32, buf: &mut [u8], want: usize, deadline: Instant) -> usize {
    let mut got = 0usize;
    let mut pollfd = libc::pollfd { fd, events: libc::POLLIN, revents: 0 };
    while got < want {
        let now = Instant::now();
        if now >= deadline {
            break;
        }
        let ms = deadline.duration_since(now).as_millis().max(1) as i32;
        let ready = unsafe { libc::poll(&mut pollfd, 1, ms.min(RX_TIMEOUT_MS)) };
        if ready <= 0 {
            break;
        }
        let n = unsafe { libc::read(fd, buf[got..].as_mut_ptr() as *mut libc::c_void, want - got) };
        if n <= 0 {
            break;
        }
        got += n as usize;
    }
    got
}

/// One VALUES exchange: build, write, read the response, decode.
/// `enc_slot`: the cache index of the chip's first encoder (0 for chip 0, 2 for chip 1).
fn exchange(fd: i32, dest: u8, speeds: [i16; 2], ports: [SensorPort; 2], enc_slot: usize, cache: &mut Cache) -> bool {
    let frame = build_tx(dest, &values_payload(speeds, [0, 0]));
    if !write_frame(fd, &frame) {
        cache.errors += 1;
        return false;
    }
    let deadline = Instant::now() + Duration::from_millis(RX_TIMEOUT_MS as u64);
    let mut head = [0u8; 2];
    if read_exact(fd, &mut head, 2, deadline) < 2 {
        cache.errors += 1;
        return false;
    }
    let count = head[1] as usize;
    let mut rest = vec![0u8; count];
    let mut got = read_exact(fd, &mut rest, count, deadline);
    while got < count {
        // Keep reading; a short body is a checksum failure at worst.
        let more = read_exact(fd, &mut rest[got..], count - got, deadline);
        if more == 0 {
            break;
        }
        got += more;
    }
    let mut full = Vec::with_capacity(2 + count);
    full.extend_from_slice(&head);
    full.extend_from_slice(&rest);
    match parse_rx(&full) {
        Ok(payload) => match decode_values(payload, ports) {
            Ok(v) => {
                cache.encoders[enc_slot] = v.encoders[0];
                cache.encoders[enc_slot + 1] = v.encoders[1];
                if ports[0] != SensorPort::None {
                    cache.color_raw = v.sensors[0];
                }
                if ports[1] == SensorPort::UltrasonicCont {
                    cache.sonar_raw = v.sensors[1];
                }
                true
            }
            Err(_) => {
                cache.errors += 1;
                false
            }
        },
        Err(_) => {
            cache.errors += 1;
            false
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let socket_path = args.get(1).cloned().unwrap_or_else(|| "/tmp/motord.sock".into());
    let serial_dev = args.get(2).cloned().unwrap_or_else(|| "/dev/ttyS0".into());
    let loop_hz: u64 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(60);

    let fd = open_serial(&serial_dev);
    SERIAL_FD.store(fd, Ordering::Relaxed);

    unsafe {
        libc::signal(libc::SIGINT, on_signal as libc::sighandler_t);
        libc::signal(libc::SIGTERM, on_signal as libc::sighandler_t);
        libc::signal(libc::SIGPIPE, libc::SIG_IGN);
    }
    std::panic::set_hook(Box::new(|_| {
        // Float the motors before an unwinding panic takes us down.
        let fd = SERIAL_FD.load(Ordering::Relaxed);
        if fd >= 0 {
            unsafe {
                libc::write(fd, ESTOP_CHIP0.as_ptr() as *const libc::c_void, 4);
                libc::write(fd, ESTOP_CHIP1.as_ptr() as *const libc::c_void, 4);
            }
        }
    }));

    let state = std::sync::Arc::new(State {
        intents: Mutex::new(Intents { left_pct: 0, right_pct: 0, turret_pct: 0, updated: Instant::now() }),
        estop: AtomicBool::new(false),
        cache: Mutex::new(Cache::default()),
        started: Instant::now(),
    });

    // --- startup handshake: sensor setup + firmware deadman ---
    {
        let mut cache = state.cache.lock().unwrap();
        let chip0 = sensor_setup_payload([SensorPort::Raw10(TYPE_SENSOR_LIGHT_ON), SensorPort::None]);
        let chip1 = sensor_setup_payload([SensorPort::None, SensorPort::UltrasonicCont]);
        write_frame(fd, &build_tx(ADDR_CHIP0, &chip0));
        write_frame(fd, &build_tx(ADDR_CHIP1, &chip1));
        std::thread::sleep(Duration::from_millis(50));
        let _ = read_all(fd);
        let t = timeout_payload(FIRMWARE_DEADMAN_MS);
        write_frame(fd, &build_tx(ADDR_CHIP0, &t));
        write_frame(fd, &build_tx(ADDR_CHIP1, &t));
        std::thread::sleep(Duration::from_millis(20));
        let _ = read_all(fd);
        cache.errors = 0; // handshake noise doesn't count
    }
    println!("motord: serial {} ok, deadman {} ms, socket {}", serial_dev, FIRMWARE_DEADMAN_MS, socket_path);

    // --- the 60 Hz loop ---
    {
        let state = std::sync::Arc::clone(&state);
        std::thread::spawn(move || {
            let period = Duration::from_millis(1000 / loop_hz);
            loop {
                let t0 = Instant::now();
                let estop = state.estop.load(Ordering::Relaxed);
                let (left, right, turret, fresh) = {
                    let mut i = state.intents.lock().unwrap();
                    let fresh = !estop && t0.duration_since(i.updated).as_millis() < INTENT_EXPIRY_MS as u128;
                    if !fresh {
                        i.left_pct = 0;
                        i.right_pct = 0;
                        i.turret_pct = 0;
                    }
                    (i.left_pct, i.right_pct, i.turret_pct, fresh)
                };
                let scale = |pct: i64| -> i16 { ((pct * 255) / 100).clamp(-255, 255) as i16 };
                // Exchange into a local copy: holding the shared lock across the
                // UART I/O and the period sleep starved snapshot() for seconds.
                let mut cache = {
                    *state.cache.lock().unwrap()
                };
                if estop {
                    write_frame(fd, &build_tx(ADDR_CHIP0, &estop_payload()));
                    write_frame(fd, &build_tx(ADDR_CHIP1, &estop_payload()));
                    std::thread::sleep(Duration::from_millis(20));
                    let _ = read_all(fd);
                } else {
                    // Chip 0: motors A (left track), B (unused). Chip 1: C (turret), D (right track).
                    exchange(fd, ADDR_CHIP0, [scale(left), 0], [SensorPort::Raw10(TYPE_SENSOR_LIGHT_ON), SensorPort::None], 0, &mut cache);
                    exchange(fd, ADDR_CHIP1, [scale(turret), scale(right)], [SensorPort::None, SensorPort::UltrasonicCont], 2, &mut cache);
                }
                cache.loops += 1;
                *state.cache.lock().unwrap() = cache;
                let elapsed = t0.elapsed();
                if elapsed < period {
                    std::thread::sleep(period - elapsed);
                }
            }
        });
    }

    // --- the UDS JSON-RPC server ---
    let s = std::sync::Arc::clone(&state);
    let _ = serve(socket_path, move |method, params| {
        match method {
            "drive" => {
                if s.estop.load(Ordering::Relaxed) {
                    return Outcome::Error(-1, "estop latched - call clear_estop first".into());
                }
                let left = params.get("left").and_then(Json::as_i64).unwrap_or(0).clamp(-100, 100);
                let right = params.get("right").and_then(Json::as_i64).unwrap_or(0).clamp(-100, 100);
                let mut i = s.intents.lock().unwrap();
                i.left_pct = left;
                i.right_pct = right;
                i.updated = Instant::now();
                Outcome::Reply(Json::obj(&[("ok", Json::Bool(true))]))
            }
            "turret" => {
                let pct = params.get("pct").and_then(Json::as_i64).unwrap_or(0).clamp(-100, 100);
                let mut i = s.intents.lock().unwrap();
                i.turret_pct = pct;
                i.updated = Instant::now();
                Outcome::Reply(Json::obj(&[("ok", Json::Bool(true))]))
            }
            "estop" => {
                s.estop.store(true, Ordering::Relaxed);
                Outcome::Reply(Json::obj(&[("ok", Json::Bool(true))]))
            }
            "clear_estop" => {
                s.estop.store(false, Ordering::Relaxed);
                Outcome::Reply(Json::obj(&[("ok", Json::Bool(true))]))
            }
            "snapshot" => {
                let c = s.cache.lock().unwrap();
                Outcome::Reply(Json::obj(&[
                    ("encoders", Json::obj(&[
                        ("A", Json::num(c.encoders[0] as i64)),
                        ("B", Json::num(c.encoders[1] as i64)),
                        ("C", Json::num(c.encoders[2] as i64)),
                        ("D", Json::num(c.encoders[3] as i64)),
                    ])),
                    ("color_raw", Json::num(c.color_raw as i64)),
                    ("sonar_raw", Json::num(c.sonar_raw as i64)),
                    ("loops", Json::num(c.loops as i64)),
                    ("errors", Json::num(c.errors as i64)),
                    ("estop_latched", Json::Bool(s.estop.load(Ordering::Relaxed))),
                ]))
            }
            "debug_raw" => {
                // One zero-speed exchange per chip; return the raw RX frames (hex).
                let mut out = Vec::new();
                for (dest, ports, slot) in [
                    (ADDR_CHIP0,
                     [SensorPort::Raw10(TYPE_SENSOR_LIGHT_ON), SensorPort::None], 0usize),
                    (ADDR_CHIP1,
                     [SensorPort::None, SensorPort::UltrasonicCont], 2usize),
                ] {
                    let frame = build_tx(dest, &values_payload([0, 0], [0, 0]));
                    if !write_frame(fd, &frame) {
                        out.push(Json::Str(format!("{:x}:write-failed", dest)));
                        continue;
                    }
                    let deadline = Instant::now() + Duration::from_millis(50);
                    let mut raw = Vec::new();
                    let mut head = [0u8; 2];
                    if read_exact(fd, &mut head, 2, deadline) == 2 {
                        raw.extend_from_slice(&head);
                        let count = head[1] as usize;
                        let mut rest = vec![0u8; count];
                        let mut got = read_exact(fd, &mut rest, count, deadline);
                        while got < count {
                            let more = read_exact(fd, &mut rest[got..], count - got, deadline);
                            if more == 0 { break; }
                            got += more;
                        }
                        raw.extend_from_slice(&rest);
                    }
                    let _ = slot;
                    out.push(Json::Str(raw.iter().map(|b| format!("{:02x}", b)).collect::<Vec<_>>().join("")));
                }
                Outcome::Reply(Json::obj(&[("raw", Json::Arr(out))]))
            }
            "status" => Outcome::Reply(Json::obj(&[
                ("daemon", Json::Str("motord".into())),
                ("version", Json::Str(env!("CARGO_PKG_VERSION").into())),
                ("uptime_s", Json::num(s.started.elapsed().as_secs() as i64)),
            ])),
            _ => Outcome::Error(-32601, "unknown method".into()),
        }
    });
}

fn read_all(fd: i32) -> usize {
    let mut buf = [0u8; 256];
    let n = unsafe { libc::read(fd, buf.as_mut_ptr() as *mut libc::c_void, buf.len()) };
    if n > 0 { n as usize } else { 0 }
}
