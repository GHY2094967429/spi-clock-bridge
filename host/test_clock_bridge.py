import unittest
from clock_bridge import crc8, request_packet, decode_response, Bridge

class HostTests(unittest.TestCase):
    def test_crc_standard_check(self):
        self.assertEqual(crc8(b"123456789"), 0xF4)

    def test_roundtrip_and_errors(self):
        req = request_packet(7, 2, 0x123, 0)
        self.assertEqual(req[:7], bytes.fromhex("A5 5A 07 02 01 23 00"))
        response = bytes.fromhex("5A A5 07 00 02 01 23 96")
        response += bytes((crc8(response),))
        self.assertEqual(decode_response(response, 7, 2, 0x123), 0x96)
        with self.assertRaises(ValueError):
            decode_response(response[:-1] + bytes((response[-1] ^ 1,)), 7, 2, 0x123)
        with self.assertRaises(ValueError):
            decode_response(response, 8, 2, 0x123)
        error = bytearray(response)
        error[3] = 5
        error[-1] = crc8(error[:-1])
        with self.assertRaisesRegex(RuntimeError, "readback mismatch"):
            decode_response(error, 7, 2, 0x123)

    def test_bounds(self):
        for address in (-1, 0x2000):
            with self.assertRaises(ValueError):
                request_packet(0, 1, address, 0)
        with self.assertRaises(ValueError):
            request_packet(0, 1, 0, 256)

    def test_stream_resynchronization(self):
        good = bytes.fromhex("5A A5 00 00 02 01 23 45")
        good += bytes((crc8(good),))
        bad = good[:-1] + bytes((good[-1] ^ 1,))
        class Port:
            def __init__(self):
                self.data = bytearray(b"noise" + bad + b"x" + good)
                self.written = b""
            def read(self, count):
                if not self.data:
                    return b""
                result = bytes(self.data[:count])
                del self.data[:count]
                return result
            def write(self, data):
                self.written += data
        port = Port()
        bridge = Bridge(port)
        self.assertEqual(bridge.transact(2, 0x123), 0x45)
        self.assertEqual(bridge.sequence, 1)
        self.assertEqual(port.written, request_packet(0, 2, 0x123))

if __name__ == "__main__":
    unittest.main()
