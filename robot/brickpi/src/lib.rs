//! BrickPi+ UART protocol, ported 1:1 from `external/BrickPi/Software/
//! BrickPi_Python/BrickPi.py` (the oracle) and `BrickPi_C/Drivers/BrickPi.h`.
//!
//! Wire framing (verified from BrickPiTx/BrickPiRx):
//!   TX: [dest][checksum][count][payload...]  checksum = (dest+count+Σpayload) % 256
//!   RX: [checksum][count][payload...]        checksum = (count+Σpayload) % 256
//!
//! Bit packing (AddBits/GetBits): LSB-first, into the payload starting at a
//! given byte offset; `bit_pos` advances one bit per written bit.
//!
//! Chip/port mapping: ATmega at UART address 1 owns motors A(0),B(1) and
//! sensor ports 1(0),2(1); address 2 owns motors C(2),D(3) and sensors 3(2),4(3).

pub const MSG_TYPE_CHANGE_ADDR: u8 = 1;
pub const MSG_TYPE_SENSOR_TYPE: u8 = 2;
pub const MSG_TYPE_VALUES: u8 = 3;
pub const MSG_TYPE_E_STOP: u8 = 4;
pub const MSG_TYPE_TIMEOUT_SETTINGS: u8 = 5;

pub const TYPE_SENSOR_LIGHT_ON: u8 = 0x09;
pub const TYPE_SENSOR_ULTRASONIC_CONT: u8 = 33;
pub const TYPE_SENSOR_I2C: u8 = 41;

// Jan's US fix: the firmware's hardcoded US I2C speed corrupts the MSB, so
// the US sensor is configured as a manual I2C device instead.
pub const US_I2C_SPEED: u8 = 10;
pub const US_I2C_IDX: usize = 0;
pub const LEGO_US_I2C_ADDR: u8 = 0x02;
pub const LEGO_US_I2C_DATA_REG: u8 = 0x42;
pub const BIT_I2C_MID: u8 = 0x01;
pub const BIT_I2C_SAME: u8 = 0x02;

pub const ADDR_CHIP0: u8 = 1;
pub const ADDR_CHIP1: u8 = 2;

/// LSB-first bit packer over a payload vector, mirroring AddBits/GetBits.
pub struct BitPacker {
    pub buf: Vec<u8>,
    bit_pos: usize, // absolute bit index into buf
}

impl BitPacker {
    /// Start packing at byte `byte_offset` (the first bytes are the fixed header).
    pub fn new(prefix: Vec<u8>) -> Self {
        BitPacker { bit_pos: prefix.len() * 8, buf: prefix }
    }

    pub fn write_bits(&mut self, value: u32, bits: usize) {
        for i in 0..bits {
            let byte = self.bit_pos / 8;
            // Zero-extend on every bit (python packs into a pre-zeroed array;
            // trailing zero bytes are part of the frame).
            if byte >= self.buf.len() {
                self.buf.resize(byte + 1, 0);
            }
            if (value >> i) & 1 == 1 {
                self.buf[byte] |= 1 << (self.bit_pos % 8);
            }
            self.bit_pos += 1;
        }
    }

    pub fn read_bits(&mut self, bits: usize) -> u32 {
        let mut result = 0u32;
        for i in 0..bits {
            let byte = self.bit_pos / 8;
            if byte >= self.buf.len() {
                self.bit_pos += 1;
                continue;
            }
            result |= (((self.buf[byte] >> (self.bit_pos % 8)) & 1) as u32) << i;
            self.bit_pos += 1;
        }
        result
    }
}

fn bits_needed(value: u32) -> usize {
    (32 - value.leading_zeros()) as usize
}

/// Build a TX frame: [dest][checksum][count][payload...]
pub fn build_tx(dest: u8, payload: &[u8]) -> Vec<u8> {
    let mut frame = Vec::with_capacity(payload.len() + 3);
    frame.push(dest);
    frame.push((dest as u32 + payload.len() as u32 + payload.iter().map(|b| *b as u32).sum::<u32>()) as u8);
    frame.push(payload.len() as u8);
    frame.extend_from_slice(payload);
    frame
}

/// Parse an RX frame: [checksum][count][payload...]. Returns the payload.
pub fn parse_rx(frame: &[u8]) -> Result<&[u8], &'static str> {
    if frame.len() < 2 {
        return Err("short frame");
    }
    let count = frame[1] as usize;
    if frame.len() < count + 2 {
        return Err("truncated frame");
    }
    let payload = &frame[2..count + 2];
    let sum = count as u32 + payload.iter().map(|b| *b as u32).sum::<u32>();
    if (sum & 0xFF) as u8 != frame[0] {
        return Err("checksum mismatch");
    }
    Ok(payload)
}

/// Port configuration for one ATmega (its two sensor ports).
#[derive(Clone, Copy, PartialEq)]
pub enum SensorPort {
    /// 10-bit raw analog-style read (light/color/raw sensors), explicit type byte.
    Raw10(u8),
    /// NXT ultrasonic in continuous mode - configured via the I2C workaround,
    /// decoded as 1-bit device mask + 1 data byte. 255 = no echo.
    UltrasonicCont,
    /// No sensor attached (still consumes 10 bits in the RX stream).
    None,
}

fn us_i2c_config() -> (u8, u8, u8, u8) {
    // (speed, addr>>1, settings, out_byte) with write=1, read=1
    (US_I2C_SPEED, LEGO_US_I2C_ADDR >> 1, BIT_I2C_MID | BIT_I2C_SAME, LEGO_US_I2C_DATA_REG)
}

/// Build the MSG_TYPE_SENSOR_TYPE payload for one chip, mirroring
/// BrickPiSetupSensors: the type bytes, then the US-sensor I2C reconfig bits.
/// Port order: the chip's port 0 first, then port 1.
pub fn sensor_setup_payload(ports: [SensorPort; 2]) -> Vec<u8> {
    let mut pk = BitPacker::new(vec![MSG_TYPE_SENSOR_TYPE, 0, 0]);
    for (ii, port) in ports.iter().enumerate() {
        match port {
            SensorPort::Raw10(t) => pk.buf[1 + ii] = *t,
            SensorPort::UltrasonicCont => {
                pk.buf[1 + ii] = TYPE_SENSOR_I2C; // the Jan fix
                let (speed, addr, settings, out) = us_i2c_config();
                pk.write_bits(speed as u32, 8);
                pk.write_bits(0, 3); // devices-1 = 0
                pk.write_bits(addr as u32, 7);
                pk.write_bits(settings as u32, 2);
                pk.write_bits(1, 4); // write count
                pk.write_bits(1, 4); // read count
                pk.write_bits(out as u32, 8);
            }
            SensorPort::None => pk.buf[1 + ii] = 0,
        }
    }
    pk.buf
}

/// Build the MSG_TYPE_VALUES payload for one chip.
/// `speeds`: signed -255..255 per the chip's two motors (0 = float-disable...
/// note: speed 0 with enable=1 = active brake per firmware; enable bit set).
/// `encoder_offsets`: optional offsets (normally 0 after the first exchange).
pub fn values_payload(speeds: [i16; 2], encoder_offsets: [i32; 2]) -> Vec<u8> {
    let mut pk = BitPacker::new(vec![MSG_TYPE_VALUES]);
    for &off in encoder_offsets.iter() {
        if off != 0 {
            pk.write_bits(1, 1);
            let abs = off.unsigned_abs();
            let dir = (off < 0) as u32;
            let need = bits_needed(abs);
            pk.write_bits(need as u32, 5);
            pk.write_bits((abs << 1) | dir, need + 1);
        } else {
            pk.write_bits(0, 1);
        }
    }
    for &s in speeds.iter() {
        let dir = (s < 0) as u32;
        let mag = s.unsigned_abs().min(255) as u32;
        pk.write_bits(((mag & 0xFF) << 2) | (dir << 1) | 0x1, 10); // enable=1
    }
    pk.buf
}

/// The E_STOP payload: float motors immediately.
pub fn estop_payload() -> Vec<u8> {
    vec![MSG_TYPE_E_STOP]
}

/// The TIMEOUT_SETTINGS payload. `timeout_ms`: float motors after this long
/// without a valid VALUES exchange (0 disables; BrickPi.h: milliseconds).
pub fn timeout_payload(timeout_ms: u32) -> Vec<u8> {
    vec![
        MSG_TYPE_TIMEOUT_SETTINGS,
        (timeout_ms & 0xFF) as u8,
        ((timeout_ms >> 8) & 0xFF) as u8,
        ((timeout_ms >> 16) & 0xFF) as u8,
        ((timeout_ms >> 24) & 0xFF) as u8,
    ]
}

/// Decoded VALUES response for one chip.
#[derive(Debug, Clone, PartialEq)]
pub struct ChipValues {
    pub encoders: [i32; 2],
    /// Raw sensor values per the chip's two ports (see SensorPort variants).
    pub sensors: [i32; 2],
}

/// Decode a VALUES response payload for one chip given its port types.
///
/// Wire order (verified against BrickPiM firmware EncodeValues and
/// BrickPi.py's parse): ALL 5-bit count fields first, THEN all value fields.
pub fn decode_values(payload: &[u8], ports: [SensorPort; 2]) -> Result<ChipValues, &'static str> {
    if payload.is_empty() || payload[0] != MSG_TYPE_VALUES {
        return Err("not a VALUES response");
    }
    let mut pk = BitPacker { buf: payload.to_vec(), bit_pos: 8 };
    let counts = [pk.read_bits(5) as usize, pk.read_bits(5) as usize];
    let mut encoders = [0i32; 2];
    for (ii, e) in encoders.iter_mut().enumerate() {
        let val = pk.read_bits(counts[ii]);
        *e = if val & 1 == 1 { -((val >> 1) as i32) } else { (val >> 1) as i32 };
    }
    let mut sensors = [0i32; 2];
    for (ii, port) in ports.iter().enumerate() {
        sensors[ii] = match port {
            SensorPort::UltrasonicCont => {
                let mask = pk.read_bits(1); // devices = 1
                if mask & 1 == 1 {
                    pk.read_bits(8) as i32
                } else {
                    -1
                }
            }
            _ => pk.read_bits(10) as i32, // Raw10 and None both consume 10 bits
        };
    }
    Ok(ChipValues { encoders, sensors })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checksum_roundtrip() {
        // checksum = dest + count + sum(payload) = 1 + 4 + 14 = 19
        let frame = build_tx(1, &[3, 2, 9, 0]);
        assert_eq!(frame, vec![1, 19, 4, 3, 2, 9, 0]);
    }

    #[test]
    fn rx_roundtrip() {
        // checksum = count + sum(payload) = 3 + 10 = 13
        let frame = vec![13, 3, 3, 4, 3];
        assert_eq!(parse_rx(&frame).unwrap(), &[3, 4, 3]);
        assert!(parse_rx(&[0, 3, 3, 4, 3]).is_err());
    }

    #[test]
    fn values_payload_minimal() {
        // chip 0, speeds 0/0, no offsets: flags(2) + words(20) = 22 bits -> 4 bytes.
        // Speed word for 0 with enable=1 is 1, so bytes: 1<<2=4 and 1<<4=16.
        let p = values_payload([0, 0], [0, 0]);
        assert_eq!(p[0], 3);
        assert_eq!(p.len(), 4);
        assert_eq!(&p[1..], &[4, 16, 0]);
    }

    #[test]
    fn values_payload_speed_bits() {
        // speed -255 on port A: dir=1, mag=255 -> word = (255<<2)|(1<<1)|1 = 1023.
        // BrickPi.py packs ALL offset flags first, then ALL speed words.
        let p = values_payload([-255, 0], [0, 0]);
        let mut bits = Vec::new();
        for byte in &p[1..] {
            for i in 0..8 {
                bits.push((byte >> i) & 1);
            }
        }
        bits.truncate(22);
        assert_eq!(bits[0], 0); // offset flag A
        assert_eq!(bits[1], 0); // offset flag B
        let word_a: u32 = bits[2..12].iter().enumerate().map(|(i, b)| (*b as u32) << i).sum();
        assert_eq!(word_a, 1023);
        let word_b: u32 = bits[12..22].iter().enumerate().map(|(i, b)| (*b as u32) << i).sum();
        assert_eq!(word_b, 1); // speed 0, enable 1
    }

    #[test]
    fn encoder_decode() {
        // Firmware order: ALL counts first, THEN all values.
        // encoders: +100 -> word 200 (8 bits); -100 -> word 201 (8 bits)
        let mut pk = BitPacker::new(vec![MSG_TYPE_VALUES]);
        pk.write_bits(8, 5);
        pk.write_bits(8, 5);
        pk.write_bits(200, 8);
        pk.write_bits(201, 8);
        pk.write_bits(0, 10);
        pk.write_bits(0, 10);
        let v = decode_values(&pk.buf, [SensorPort::None, SensorPort::None]).unwrap();
        assert_eq!(v.encoders, [100, -100]);
    }

    #[test]
    fn encoder_zero_and_negative_decode() {
        // Real-world case (parity probe): A=-7500 (count 14, word 15001), B=0
        // (count 0, no value bits), color 767, none 0.
        let mut pk = BitPacker::new(vec![MSG_TYPE_VALUES]);
        pk.write_bits(14, 5);
        pk.write_bits(0, 5);
        pk.write_bits(15001, 14);
        pk.write_bits(767, 10);
        pk.write_bits(0, 10);
        let v = decode_values(
            &pk.buf,
            [SensorPort::Raw10(TYPE_SENSOR_LIGHT_ON), SensorPort::None],
        )
        .unwrap();
        assert_eq!(v.encoders, [-7500, 0]);
        assert_eq!(v.sensors[0], 767);
    }
}
