//! robotctl - the one CLI that must work on a broken robot.
//!
//! Usage: robotctl [socket] <method> [json_params]
//!   robotctl snapshot
//!   robotctl status
//!   robotctl estop
//!   robotctl drive '{"left":-30,"right":-30}'

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let (socket, rest) = if args.len() > 1 && args[1].ends_with(".sock") {
        (args[1].clone(), &args[2..])
    } else {
        ("/tmp/motord.sock".to_string(), &args[1..])
    };
    let method = rest.get(0).cloned().unwrap_or_else(|| "status".into());
    let params = rest.get(1).cloned().unwrap_or_else(|| "{}".into());

    let mut stream = match UnixStream::connect(&socket) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("robotctl: cannot connect to {}: {} (is motord running?)", socket, e);
            std::process::exit(2);
        }
    };
    let line = format!(
        r#"{{"jsonrpc":"2.0","id":1,"method":"{}","params":{}}}"#,
        method, params
    );
    if stream.write_all(line.as_bytes()).is_err() || stream.write_all(b"\n").is_err() {
        eprintln!("robotctl: write failed");
        std::process::exit(2);
    }
    let mut reader = BufReader::new(stream);
    let mut response = String::new();
    match reader.read_line(&mut response) {
        Ok(0) | Err(_) => {
            eprintln!("robotctl: no response");
            std::process::exit(2);
        }
        Ok(_) => println!("{}", response.trim_end()),
    }
}
