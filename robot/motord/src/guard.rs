//! Turret cable envelope guard. The same rules live in
//! app/server/turret_guard.py; change both together.
//!
//! The turret's cables are neutral at camera-forward and the turret must
//! never turn more than 180 degrees either way from it. State on the robot,
//! in ~/.koc/turret.json: {"center": <ticks>, "half_range": <ticks>, "last": <ticks>}
//!
//! Fail-closed: a missing or invalid file, or a first encoder reading that
//! does not match "last" (the BrickPi lost power and reset its encoders, or
//! the turret was turned by hand), locks the turret until it is re-referenced
//! with testing/turret_envelope.py.

use rpc::Json;
use std::fmt;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

/// Stop this far short of the limit. Measured 2026-10-26: at pwm 250 the v1
/// server (10 Hz loop) overshot the stop point by 313 ticks; worst case one
/// full cycle plus coast is ~500 ticks. motord (60 Hz) overshot by 12 at 16%.
pub const STOP_MARGIN: i64 = 800;
pub const DISCONTINUITY: i64 = 400; // first reading vs "last" beyond this -> locked
pub const PERSIST_MIN_DELTA: i64 = 20;
pub const PERSIST_PERIOD: Duration = Duration::from_millis(250);

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Envelope {
    pub center: i64,
    pub half_range: i64,
    pub last: i64,
}

impl Envelope {
    pub fn parse(text: &str) -> Option<Envelope> {
        let v = rpc::parse(text.trim()).ok()?;
        let field = |k: &str| v.get(k).and_then(Json::as_i64);
        let e = Envelope { center: field("center")?, half_range: field("half_range")?, last: field("last")? };
        if e.half_range <= STOP_MARGIN {
            return None;
        }
        Some(e)
    }

    pub fn to_file_text(&self) -> String {
        format!("{{\"center\": {}, \"half_range\": {}, \"last\": {}}}\n", self.center, self.half_range, self.last)
    }

    /// (low, high) encoder positions where outward motion stops.
    pub fn limits(&self) -> (i64, i64) {
        (self.center - self.half_range + STOP_MARGIN, self.center + self.half_range - STOP_MARGIN)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Block {
    NotReady,
    Stale,
    Locked,
    LeftLimit { encoder: i64, limit: i64 },
    RightLimit { encoder: i64, limit: i64 },
}

impl Block {
    /// Blocks a client should hear about; NotReady/Stale clear on the next good read.
    pub fn is_hard(&self) -> bool {
        !matches!(self, Block::NotReady | Block::Stale)
    }
}

impl fmt::Display for Block {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Block::NotReady => write!(f, "no encoder reading yet"),
            Block::Stale => write!(f, "last encoder reading failed"),
            Block::Locked => write!(f, "locked"),
            Block::LeftLimit { encoder, limit } => write!(f, "left limit: C={} >= {}", encoder, limit),
            Block::RightLimit { encoder, limit } => write!(f, "right limit: C={} <= {}", encoder, limit),
        }
    }
}

/// Positive speed = encoder-positive (turret left). Stopping is always
/// allowed; motion back toward the center is allowed at the limit.
pub fn allowed(env: Option<&Envelope>, encoder: i64, speed: i64) -> Result<i64, Block> {
    if speed == 0 {
        return Ok(0);
    }
    let Some(env) = env else { return Err(Block::Locked) };
    let (low, high) = env.limits();
    if speed > 0 && encoder >= high {
        return Err(Block::LeftLimit { encoder, limit: high });
    }
    if speed < 0 && encoder <= low {
        return Err(Block::RightLimit { encoder, limit: low });
    }
    Ok(speed)
}

pub fn default_path() -> PathBuf {
    let home = std::env::var_os("HOME").unwrap_or_else(|| "/home/pi".into());
    PathBuf::from(home).join(".koc").join("turret.json")
}

pub fn save(path: &Path, env: &Envelope) -> std::io::Result<()> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let mut tmp = path.as_os_str().to_owned();
    tmp.push(".tmp");
    std::fs::write(&tmp, env.to_file_text())?;
    std::fs::rename(&tmp, path)
}

/// One per motor writer: feed every encoder exchange to observe() or
/// mark_stale(), filter every turret speed through limit().
pub struct Guard {
    pub path: PathBuf,
    env: Option<Envelope>,
    reason: Option<String>,
    started: bool,
    fresh: bool,
    last_written: i64,
    last_write_t: Option<Instant>,
}

impl Guard {
    pub fn load(path: PathBuf) -> Guard {
        let env = std::fs::read_to_string(&path).ok().and_then(|t| Envelope::parse(&t));
        let reason = if env.is_none() { Some(format!("no valid state file {}", path.display())) } else { None };
        Guard { path, env, reason, started: false, fresh: false, last_written: 0, last_write_t: None }
    }

    pub fn locked(&self) -> bool {
        self.env.is_none()
    }

    pub fn reason(&self) -> Option<&str> {
        self.reason.as_deref()
    }

    /// A good encoder reading. Returns the envelope to persist, if due.
    pub fn observe(&mut self, encoder: i64, now: Instant) -> Option<Envelope> {
        self.fresh = true;
        if !self.started {
            self.started = true;
            if let Some(env) = self.env {
                if (encoder - env.last).abs() > DISCONTINUITY {
                    self.reason = Some(format!(
                        "encoder C={} but last saved {}: power cycle or hand move - re-reference the turret",
                        encoder, env.last
                    ));
                    self.env = None;
                }
            }
            match self.env {
                None => eprintln!("motord: turret LOCKED: {}", self.reason.as_deref().unwrap_or("")),
                Some(env) => {
                    self.last_written = env.last;
                    self.last_write_t = Some(now);
                    println!("motord: turret envelope ok: C={}, limits {:?}", encoder, env.limits());
                }
            }
            return None;
        }
        let env = self.env.as_mut()?;
        let due = self.last_write_t.map_or(true, |t| now.duration_since(t) >= PERSIST_PERIOD);
        if (encoder - self.last_written).abs() >= PERSIST_MIN_DELTA && due {
            env.last = encoder;
            self.last_written = encoder;
            self.last_write_t = Some(now);
            return Some(*env);
        }
        None
    }

    pub fn mark_stale(&mut self) {
        self.fresh = false;
    }

    /// The speed to write for a requested turret speed at `encoder`.
    pub fn limit(&self, encoder: i64, speed: i64) -> Result<i64, Block> {
        if speed == 0 {
            return Ok(0);
        }
        if !self.started {
            return Err(Block::NotReady);
        }
        if !self.fresh {
            return Err(Block::Stale);
        }
        allowed(self.env.as_ref(), encoder, speed)
    }

    pub fn to_json(&self) -> Json {
        let mut pairs = vec![
            ("locked", Json::Bool(self.locked())),
            ("reason", self.reason.as_ref().map_or(Json::Null, |r| Json::Str(r.clone()))),
            ("path", Json::Str(self.path.display().to_string())),
        ];
        if let Some(env) = self.env {
            let (low, high) = env.limits();
            pairs.push(("center", Json::num(env.center)));
            pairs.push(("half_range", Json::num(env.half_range)));
            pairs.push(("low", Json::num(low)));
            pairs.push(("high", Json::num(high)));
        }
        Json::obj(&pairs)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const ENV: Envelope = Envelope { center: 1000, half_range: 2000, last: 1000 };

    fn temp_path(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("motord-guard-{}-{}", std::process::id(), name));
        let _ = std::fs::remove_dir_all(&dir);
        dir.join("koc").join("turret.json")
    }

    #[test]
    fn locked_blocks_motion_but_not_stop() {
        assert_eq!(allowed(None, 0, 50), Err(Block::Locked));
        assert_eq!(allowed(None, 0, 0), Ok(0));
    }

    #[test]
    fn outward_at_limits_blocked_inward_allowed() {
        let (low, high) = ENV.limits();
        assert_eq!((low, high), (1000 - 2000 + STOP_MARGIN, 1000 + 2000 - STOP_MARGIN));
        assert_eq!(allowed(Some(&ENV), 1000, 50), Ok(50));
        assert!(allowed(Some(&ENV), high, 50).is_err());
        assert_eq!(allowed(Some(&ENV), high, -50), Ok(-50));
        assert!(allowed(Some(&ENV), low, -50).is_err());
        assert_eq!(allowed(Some(&ENV), low, 50), Ok(50));
        assert_eq!(allowed(Some(&ENV), high - 1, 50), Ok(50));
    }

    #[test]
    fn parse_matches_python_format() {
        let e = Envelope::parse("{\"center\": 5, \"half_range\": 21000, \"last\": 7}\n").unwrap();
        assert_eq!(e, Envelope { center: 5, half_range: 21000, last: 7 });
        assert_eq!(Envelope::parse(&e.to_file_text()), Some(e));
        assert_eq!(Envelope::parse("{not json"), None);
        assert_eq!(Envelope::parse("{\"center\": 5, \"last\": 7}"), None);
        assert_eq!(Envelope::parse("{\"center\": 5, \"half_range\": 800, \"last\": 7}"), None);
    }

    #[test]
    fn missing_file_locks() {
        let mut g = Guard::load(temp_path("missing"));
        g.observe(0, Instant::now());
        assert!(g.locked());
        assert_eq!(g.limit(0, 40), Err(Block::Locked));
        assert_eq!(g.limit(0, 0), Ok(0));
    }

    #[test]
    fn no_motion_before_first_reading_or_after_failed_read() {
        let path = temp_path("ready");
        save(&path, &Envelope { center: 0, half_range: 5000, last: 0 }).unwrap();
        let mut g = Guard::load(path);
        assert_eq!(g.limit(0, 40), Err(Block::NotReady));
        g.observe(0, Instant::now());
        assert_eq!(g.limit(0, 40), Ok(40));
        g.mark_stale();
        assert_eq!(g.limit(0, 40), Err(Block::Stale));
        assert!(!Block::Stale.is_hard());
    }

    #[test]
    fn discontinuity_locks() {
        let path = temp_path("jump");
        save(&path, &Envelope { center: 42298, half_range: 21000, last: 42298 }).unwrap();
        let mut g = Guard::load(path);
        g.observe(0, Instant::now()); // BrickPi power cycle resets encoders to 0
        assert!(g.locked());
        assert!(g.reason().unwrap().contains("re-reference"));
        assert_eq!(g.limit(0, 40), Err(Block::Locked));
    }

    #[test]
    fn continuous_start_allows_and_persists() {
        let path = temp_path("persist");
        save(&path, &Envelope { center: 42298, half_range: 21000, last: 42298 }).unwrap();
        let mut g = Guard::load(path.clone());
        let t0 = Instant::now();
        assert_eq!(g.observe(42300, t0), None);
        assert!(!g.locked());
        assert_eq!(g.limit(42300, 40), Ok(40));
        assert_eq!(g.observe(42400, t0 + Duration::from_millis(100)), None); // too soon
        let due = g.observe(42410, t0 + Duration::from_millis(300)).unwrap();
        assert_eq!(due.last, 42410);
        save(&path, &due).unwrap();
        assert_eq!(Envelope::parse(&std::fs::read_to_string(&path).unwrap()).unwrap().last, 42410);
        assert_eq!(g.observe(42415, t0 + Duration::from_millis(700)), None); // below min delta
    }
}
