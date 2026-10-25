#!/usr/bin/env python3
"""Generate golden BrickPi UART frames for the Rust protocol tests.

Mirrors AddBits/GetBits and the build sequences from
external/BrickPi/Software/BrickPi_Python/BrickPi.py EXACTLY (this is the
oracle implementation). Run:  python3 gen_goldens.py  ->  prints hex lines
to paste into tests/golden.rs.

Layout facts (verified against BrickPi.py):
- TX frame: [dest][checksum][count][payload]; checksum=(dest+count+sum) % 256
- VALUES payload: [MSG_TYPE=3] then bits (LSB-first, starting after byte 0):
  per motor: 1-bit encoder-offset flag (if set: 5-bit BitsNeeded + value*2|dir)
  per motor: 10 bits ((|speed|&0xFF)<<2 | dir<<1 | enable)
- SENSOR_TYPE payload: [2][type_p0][type_p1] then, for I2C-typed ports
  (US_CONT is reconfigured to I2C per Jan's fix), from byte 3:
  8-bit I2C speed, 3-bit (devices-1), per device: 7-bit (addr>>1),
  2-bit settings, and if BIT_I2C_SAME: 4-bit write count, 4-bit read count,
  write-count x 8-bit data. tx_bytes = ceil(bits/8) + 3.
"""
MASK_D0_M, MASK_D0_S = 0x01, 0x08
TYPE_SENSOR_LIGHT_ON = MASK_D0_M | MASK_D0_S  # 0x09
TYPE_SENSOR_ULTRASONIC_CONT = 33
TYPE_SENSOR_I2C = 41
US_I2C_SPEED, US_I2C_IDX = 10, 0
LEGO_US_I2C_ADDR, LEGO_US_I2C_DATA_REG = 0x02, 0x42
BIT_I2C_MID, BIT_I2C_SAME = 0x01, 0x02


class Packer:
    def __init__(self, prefix):
        self.buf = bytearray(prefix)
        self.bit_offset = len(prefix) * 8

    def add_bits(self, bits, value):
        for i in range(bits):
            if self.bit_offset // 8 >= len(self.buf):
                self.buf.append(0)
            if value & 0x01:
                self.buf[self.bit_offset // 8] |= 0x01 << (self.bit_offset % 8)
            value //= 2
            self.bit_offset += 1

    def get_bits(self, bits):
        result = 0
        for i in range(bits, 0, -1):
            result *= 2
            result |= (self.buf[(self.bit_offset + i - 1) // 8] >> ((self.bit_offset + i - 1) % 8)) & 0x01
        self.bit_offset += bits
        return result


def bits_needed(value):
    for i in range(32):
        if not value:
            return i
        value //= 2
    return 31


def tx_frame(dest, payload):
    return bytes([dest, (dest + len(payload) + sum(payload)) % 256, len(payload)] + list(payload))


def values_payload(speeds, offsets=(0, 0)):
    pk = Packer([3])
    for off in offsets:
        if off:
            pk.add_bits(1, 1)
            v, d = abs(off), (1 if off < 0 else 0)
            need = bits_needed(v)
            pk.add_bits(5, need)
            pk.add_bits(need + 1, v * 2 | d)
        else:
            pk.add_bits(1, 0)
    for s in speeds:
        d, m = (1, -s) if s < 0 else (0, s)
        pk.add_bits(10, (((min(m, 255) & 0xFF) << 2) | (d << 1) | 0x01))
    return bytes(pk.buf)


def sensor_setup_payload(port_types):
    """port_types: per chip port: int type byte or ('US',) for the US reconfig."""
    pk = Packer([2, 0, 0])
    for ii, t in enumerate(port_types):
        if t == 'US':
            pk.buf[1 + ii] = TYPE_SENSOR_I2C
            pk.add_bits(8, US_I2C_SPEED)
            pk.add_bits(3, 0)  # devices-1
            pk.add_bits(7, LEGO_US_I2C_ADDR >> 1)
            pk.add_bits(2, BIT_I2C_MID | BIT_I2C_SAME)
            pk.add_bits(4, 1)  # write count
            pk.add_bits(4, 1)  # read count
            pk.add_bits(8, LEGO_US_I2C_DATA_REG)
        else:
            pk.buf[1 + ii] = t
    return bytes(pk.buf)


def h(b):
    return 'vec!' + repr(list(b)).replace('(', '[').replace(')', ']')


if __name__ == '__main__':
    rows = [
        ("CHIP0_SETUP (color light-on + none)", tx_frame(1, sensor_setup_payload([TYPE_SENSOR_LIGHT_ON, 0]))),
        ("CHIP1_SETUP (none + US reconfig)", tx_frame(2, sensor_setup_payload([0, 'US']))),
        ("CHIP0_VALUES speeds +100/-100", tx_frame(1, values_payload([100, -100]))),
        ("CHIP1_VALUES speeds 0/0", tx_frame(2, values_payload([0, 0]))),
        ("ESTOP", tx_frame(1, [4])),
        ("TIMEOUT 300ms", tx_frame(1, [5, 300 & 0xFF, (300 >> 8) & 0xFF, (300 >> 16) & 0xFF, (300 >> 24) & 0xFF])),
    ]
    for name, frame in rows:
        print(f"{name}: {list(frame)}")

    # A canned VALUES response for chip 0 (encoders +1234/-2345, color 776, none 0).
    # Firmware order: ALL 5-bit counts first, THEN all value fields.
    # 1234 -> word 2468 (12 bits); -2345 -> word 4691 (13 bits).
    pk = Packer([3])
    pk.add_bits(5, 12)
    pk.add_bits(5, 13)
    pk.add_bits(12, 2468)
    pk.add_bits(13, 4691)
    pk.add_bits(10, 776)
    pk.add_bits(10, 0)
    rx_payload = bytes(pk.buf)
    rx_frame = bytes([(len(rx_payload) + sum(rx_payload)) % 256, len(rx_payload)] + list(rx_payload))
    print(f"CHIP0_VALUES_RX encoders 1234/-2345 color 776: {list(rx_frame)}")
