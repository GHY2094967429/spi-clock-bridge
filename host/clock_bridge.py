"""HMC7044 bridge v2 CLI. Requires pyserial only when opening a serial port."""
import argparse
import json
import time

STATUS_ERRORS = {1: "CRC mismatch", 2: "unsupported command", 3: "operation timeout",
                 4: "invalid address", 5: "write/readback mismatch"}

def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (0x07 if crc & 0x80 else 0)) & 0xFF
    return crc

def request_packet(sequence, command, address=0, data=0):
    if not 0 <= address <= 0x1FFF:
        raise ValueError("address must be in 0x0000..0x1FFF")
    if not 0 <= data <= 0xFF:
        raise ValueError("data must be in 0x00..0xFF")
    packet = bytes((0xA5, 0x5A, sequence & 255, command, address >> 8, address & 255, data))
    return packet + bytes((crc8(packet),))

def decode_response(packet, sequence, command, address):
    if len(packet) != 9 or packet[:2] != b"\x5a\xa5":
        raise ValueError("invalid response frame")
    if crc8(packet[:-1]) != packet[-1]:
        raise ValueError("response CRC mismatch")
    if packet[2] != sequence or packet[4:7] != bytes((command, address >> 8, address & 255)):
        raise ValueError("response sequence/command/address mismatch")
    if packet[3]:
        raise RuntimeError(f"device error {packet[3]}: {STATUS_ERRORS.get(packet[3], 'unknown')}; data=0x{packet[7]:02X}")
    return packet[7]

class Bridge:
    def __init__(self, port, timeout=1.0, legacy=False):
        self.port, self.timeout, self.legacy = port, timeout, legacy
        self.sequence = 0

    def transact(self, command, address=0, data=0):
        framed = request_packet(self.sequence, command, address, data)
        packet = bytes((command, address >> 8, address & 255, data)) if self.legacy else framed
        self.port.write(packet)
        deadline = time.monotonic() + self.timeout
        buffer = bytearray()
        while time.monotonic() < deadline:
            incoming = self.port.read(1)
            if not incoming:
                continue
            buffer.extend(incoming)
            if self.legacy:
                if len(buffer) == 4:
                    if buffer[:3] != packet[:3]:
                        raise ValueError("legacy response mismatch")
                    # Legacy has no unambiguous error field: 0xEE may also be valid data.
                    return buffer[3]
            else:
                while len(buffer) >= 2 and buffer[:2] != b"\x5a\xa5":
                    del buffer[0]
                if len(buffer) == 9:
                    if crc8(buffer[:-1]) != buffer[-1]:
                        del buffer[0]
                        continue
                    if buffer[2] != self.sequence:
                        buffer.clear()
                        continue
                    sequence = self.sequence
                    self.sequence = (self.sequence + 1) & 255
                    return decode_response(buffer, sequence, command, address)
        # Advance the sequence so a late reply cannot satisfy the next transaction.
        self.sequence = (self.sequence + 1) & 255
        raise TimeoutError("no matching response; writes are never retried automatically")

def number(text):
    return int(text, 0)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="e.g. COM5")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--legacy", action="store_true")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("read", "write", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("address", type=number)
        if name != "read":
            cmd.add_argument("data", type=number)
    sub.add_parser("status")
    args = parser.parse_args()
    try:
        import serial
    except ImportError:
        parser.error("install pyserial: python -m pip install pyserial")
    try:
        with serial.Serial(args.port, args.baud, timeout=0.05, write_timeout=1) as port:
            port.reset_input_buffer()
            bridge = Bridge(port, legacy=args.legacy)
            if args.action == "status":
                values = [bridge.transact(3, offset) for offset in range(6)]
                flags = values[0]
                report = {
                    "clock_locked": bool(flags & 1), "config_written": bool(flags & 2),
                    "verification_done": bool(flags & 4), "verification_error": bool(flags & 8),
                    "hmc_lock_gpio": bool(flags & 16), "spi_busy": bool(flags & 32),
                    "fifo_overflow": bool(flags & 64), "uart_error_or_gap_timeout": bool(flags & 128),
                    "first_failed_address": f"0x{((values[1] << 8) | values[2]):04X}",
                    "expected": f"0x{values[3]:02X}", "actual": f"0x{values[4]:02X}",
                    "protocol_version": f"0x{values[5]:02X}",
                }
                print(json.dumps(report, indent=2))
            else:
                command = {"read": 2, "write": 1, "verify": 4}[args.action]
                value = bridge.transact(command, args.address, getattr(args, "data", 0))
                print(f"0x{args.address:04X}: 0x{value:02X}")
    except (ValueError, RuntimeError, TimeoutError, serial.SerialException) as error:
        parser.exit(1, f"Error: {error}\n")

if __name__ == "__main__":
    main()
