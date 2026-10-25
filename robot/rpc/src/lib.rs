//! Minimal NDJSON JSON-RPC 2.0 over Unix domain sockets.
//!
//! Zero-dependency by design: the robot is an armv7 Raspbian stretch box
//! with 1 GB RAM, so motord builds with std + libc only. The JSON surface
//! needed is tiny (fixed method set, flat params), so a hand-rolled parser
//! is proportionate here. If the message set grows complex types, swap in
//! serde_json — the wire format is unchanged.

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixListener;
use std::path::Path;
use std::sync::Arc;

// ---------------------------------------------------------------- JSON ----

#[derive(Debug, Clone, PartialEq)]
pub enum Json {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<Json>),
    Obj(HashMap<String, Json>),
}

impl Json {
    pub fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Obj(m) => m.get(key),
            _ => None,
        }
    }

    pub fn as_i64(&self) -> Option<i64> {
        match self {
            Json::Num(n) if n.fract() == 0.0 => Some(*n as i64),
            _ => None,
        }
    }

    pub fn obj(pairs: &[(&str, Json)]) -> Json {
        Json::Obj(pairs.iter().map(|(k, v)| (k.to_string(), v.clone())).collect())
    }

    pub fn num(n: i64) -> Json {
        Json::Num(n as f64)
    }

    pub fn to_string(&self) -> String {
        let mut s = String::new();
        self.write(&mut s);
        s
    }

    fn write(&self, s: &mut String) {
        match self {
            Json::Null => s.push_str("null"),
            Json::Bool(b) => s.push_str(if *b { "true" } else { "false" }),
            Json::Num(n) => {
                if n.fract() == 0.0 && n.abs() < 9e15 {
                    s.push_str(&format!("{}", *n as i64));
                } else {
                    s.push_str(&format!("{}", n));
                }
            }
            Json::Str(v) => write_str(v, s),
            Json::Arr(items) => {
                s.push('[');
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        s.push(',');
                    }
                    item.write(s);
                }
                s.push(']');
            }
            Json::Obj(map) => {
                s.push('{');
                for (i, (k, v)) in map.iter().enumerate() {
                    if i > 0 {
                        s.push(',');
                    }
                    write_str(k, s);
                    s.push(':');
                    v.write(s);
                }
                s.push('}');
            }
        }
    }
}

fn write_str(v: &str, s: &mut String) {
    s.push('"');
    for c in v.chars() {
        match c {
            '"' => s.push_str("\\\""),
            '\\' => s.push_str("\\\\"),
            '\n' => s.push_str("\\n"),
            '\r' => s.push_str("\\r"),
            '\t' => s.push_str("\\t"),
            c if (c as u32) < 0x20 => s.push_str(&format!("\\u{:04x}", c as u32)),
            c => s.push(c),
        }
    }
    s.push('"');
}

pub fn parse(input: &str) -> Result<Json, String> {
    let b = input.as_bytes();
    let mut i = 0usize;
    let v = parse_value(b, &mut i)?;
    skip_ws(b, &mut i);
    if i != b.len() {
        return Err("trailing characters".into());
    }
    Ok(v)
}

fn skip_ws(b: &[u8], i: &mut usize) {
    while *i < b.len() && matches!(b[*i], b' ' | b'\t' | b'\n' | b'\r') {
        *i += 1;
    }
}

fn parse_value(b: &[u8], i: &mut usize) -> Result<Json, String> {
    skip_ws(b, i);
    if *i >= b.len() {
        return Err("unexpected end".into());
    }
    match b[*i] {
        b'{' => {
            *i += 1;
            let mut map = HashMap::new();
            skip_ws(b, i);
            if b.get(*i) == Some(&b'}') {
                *i += 1;
                return Ok(Json::Obj(map));
            }
            loop {
                skip_ws(b, i);
                let key = match parse_value(b, i)? {
                    Json::Str(s) => s,
                    _ => return Err("object key must be string".into()),
                };
                skip_ws(b, i);
                if b.get(*i) != Some(&b':') {
                    return Err("expected ':'".into());
                }
                *i += 1;
                let val = parse_value(b, i)?;
                map.insert(key, val);
                skip_ws(b, i);
                match b.get(*i) {
                    Some(&b',') => *i += 1,
                    Some(&b'}') => {
                        *i += 1;
                        return Ok(Json::Obj(map));
                    }
                    _ => return Err("expected ',' or '}'".into()),
                }
            }
        }
        b'[' => {
            *i += 1;
            let mut items = Vec::new();
            skip_ws(b, i);
            if b.get(*i) == Some(&b']') {
                *i += 1;
                return Ok(Json::Arr(items));
            }
            loop {
                items.push(parse_value(b, i)?);
                skip_ws(b, i);
                match b.get(*i) {
                    Some(&b',') => *i += 1,
                    Some(&b']') => {
                        *i += 1;
                        return Ok(Json::Arr(items));
                    }
                    _ => return Err("expected ',' or ']'".into()),
                }
            }
        }
        b'"' => {
            *i += 1;
            let mut s = String::new();
            loop {
                match b.get(*i) {
                    None => return Err("unterminated string".into()),
                    Some(&b'"') => {
                        *i += 1;
                        return Ok(Json::Str(s));
                    }
                    Some(&b'\\') => {
                        *i += 1;
                        match b.get(*i) {
                            Some(&b'"') => s.push('"'),
                            Some(&b'\\') => s.push('\\'),
                            Some(&b'/') => s.push('/'),
                            Some(&b'n') => s.push('\n'),
                            Some(&b'r') => s.push('\r'),
                            Some(&b't') => s.push('\t'),
                            Some(&b'u') => {
                                let hex = std::str::from_utf8(&b[*i + 1..*i + 5])
                                    .map_err(|_| "bad unicode escape".to_string())?;
                                let cp = u32::from_str_radix(hex, 16)
                                    .map_err(|_| "bad unicode escape".to_string())?;
                                s.push(char::from_u32(cp).unwrap_or('\u{FFFD}'));
                                *i += 4;
                            }
                            _ => return Err("bad escape".into()),
                        }
                        *i += 1;
                    }
                    Some(_) => {
                        let start = *i;
                        while *i < b.len() && b[*i] != b'"' && b[*i] != b'\\' {
                            *i += 1;
                        }
                        s.push_str(std::str::from_utf8(&b[start..*i]).map_err(|_| "bad utf8".to_string())?);
                    }
                }
            }
        }
        b't' if b[*i..].starts_with(b"true") => {
            *i += 4;
            Ok(Json::Bool(true))
        }
        b'f' if b[*i..].starts_with(b"false") => {
            *i += 5;
            Ok(Json::Bool(false))
        }
        b'n' if b[*i..].starts_with(b"null") => {
            *i += 4;
            Ok(Json::Null)
        }
        _ => {
            let start = *i;
            if b[*i] == b'-' || b[*i] == b'+' {
                *i += 1;
            }
            while *i < b.len() && (b[*i].is_ascii_digit() || matches!(b[*i], b'.' | b'e' | b'E' | b'-' | b'+')) {
                *i += 1;
            }
            let s = std::str::from_utf8(&b[start..*i]).map_err(|_| "bad number".to_string())?;
            s.parse::<f64>().map(Json::Num).map_err(|_| "bad number".to_string())
        }
    }
}

// ------------------------------------------------------------ JSON-RPC ----

pub struct Request {
    pub id: Json,
    pub method: String,
    pub params: Json,
}

pub enum Outcome {
    Reply(Json),
    Error(i32, String),
}

/// Parse one NDJSON line into a Request. Non-object lines error.
pub fn parse_request(line: &str) -> Result<Request, String> {
    let v = parse(line)?;
    let method = match v.get("method") {
        Some(Json::Str(s)) => s.clone(),
        _ => return Err("missing method".into()),
    };
    let id = v.get("id").cloned().unwrap_or(Json::Null);
    let params = v.get("params").cloned().unwrap_or(Json::obj(&[]));
    Ok(Request { id, method, params })
}

pub fn reply(id: &Json, result: Json) -> String {
    Json::obj(&[("jsonrpc", Json::Str("2.0".into())), ("id", id.clone()), ("result", result)]).to_string()
}

pub fn error(id: &Json, code: i32, message: &str) -> String {
    Json::obj(&[
        ("jsonrpc", Json::Str("2.0".into())),
        ("id", id.clone()),
        ("error", Json::obj(&[("code", Json::num(code as i64)), ("message", Json::Str(message.into()))])),
    ])
    .to_string()
}

// ----------------------------------------------------------------- UDS ----

/// Serve a JSON-RPC handler over a Unix socket, one thread per connection.
/// The handler receives (method, params) and returns an Outcome.
pub fn serve<P, F>(path: P, handler: F) -> std::io::Result<()>
where
    P: AsRef<Path>,
    F: Fn(&str, &Json) -> Outcome + Send + Sync + 'static,
{
    let _ = std::fs::remove_file(path.as_ref());
    let listener = UnixListener::bind(path)?;
    let handler = Arc::new(handler);
    for stream in listener.incoming() {
        let Ok(stream) = stream else { continue };
        let handler = Arc::clone(&handler);
        std::thread::spawn(move || {
            let mut reader = BufReader::new(match stream.try_clone() {
                Ok(s) => s,
                Err(_) => return,
            });
            let mut writer = stream;
            let mut line = String::new();
            loop {
                line.clear();
                match reader.read_line(&mut line) {
                    Ok(0) | Err(_) => return,
                    Ok(_) => {}
                }
                let trimmed = line.trim_end();
                if trimmed.is_empty() {
                    continue;
                }
                let out = match parse_request(trimmed) {
                    Ok(req) => match handler(&req.method, &req.params) {
                        Outcome::Reply(r) => reply(&req.id, r),
                        Outcome::Error(c, m) => error(&req.id, c, &m),
                    },
                    Err(e) => error(&Json::Null, -32600, &format!("invalid request: {}", e)),
                };
                if writer.write_all(out.as_bytes()).is_err() || writer.write_all(b"\n").is_err() {
                    return;
                }
            }
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_roundtrip() {
        let v = parse(r#"{"a": 1, "b": [-2, "x\n"], "c": {"d": true}}"#).unwrap();
        assert_eq!(v.get("a").unwrap().as_i64(), Some(1));
        // Object key order is not significant; compare structurally.
        let out = parse(&v.to_string()).unwrap();
        assert_eq!(out, v);
    }

    #[test]
    fn rpc_envelope() {
        let req = parse_request(r#"{"jsonrpc":"2.0","id":7,"method":"status","params":{}}"#).unwrap();
        assert_eq!(req.method, "status");
        assert_eq!(req.id.as_i64(), Some(7));
        assert!(reply(&req.id, Json::num(1)).contains(r#""id":7"#));
    }
}
