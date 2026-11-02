"""Qt worker and local byte-level demonstration device for bridge protocol v2."""
import time

from PySide6.QtCore import QObject, Signal, Slot

from clock_bridge import Bridge, crc8
from official_config import hex_number, load_csv


class DemoPort:
    """Software register model, NOT a hardware/PLL simulation or board test."""
    def __init__(self):
        self.registers = {0xA + n: value for n, value in enumerate((6, 7, 6, 6, 7))}
        self.buffer = bytearray()
        self.closed = False

    def write(self, packet):
        if self.closed:
            raise OSError("演示连接已关闭")
        if len(packet) != 8 or packet[:2] != b"\xa5\x5a" or crc8(packet[:-1]) != packet[-1]:
            raise ValueError("演示模型仅接收有效的 v2 请求")
        _, _, seq, command, high, low, data, _ = packet
        address = (high << 8) | low
        status, value = 0, data
        if address > 0x1FFF:
            status = 4
        elif command in (1, 4):
            self.registers[address] = data
        elif command == 2:
            value = self.registers.get(address, 0)
        elif command == 3:
            # Software demo claims no lock GPIO level. Init bits are model values.
            value = (0x07, 0, 0, 0, 0, 0x20)[address] if address < 6 else 0
        else:
            status = 2
        reply = bytes((0x5A, 0xA5, seq, status, command, high, low, value))
        self.buffer.extend(reply + bytes((crc8(reply),)))
        return len(packet)

    def read(self, count):
        value = bytes(self.buffer[:count])
        del self.buffer[:count]
        return value

    def close(self):
        self.closed = True


class TracePort:
    def __init__(self, port, trace):
        self.port, self.trace = port, trace
        self.received = bytearray()

    def write(self, data):
        written = self.port.write(data)
        self.trace("TX", bytes(data[:written]))
        if written != len(data):
            raise OSError("串口未完整发送请求；写入不会自动重试")
        return written

    def read(self, count):
        data = self.port.read(count)
        self.received.extend(data)
        return data

    def flush_trace(self):
        if self.received:
            self.trace("RX", bytes(self.received))
            self.received.clear()


class SerialWorker(QObject):
    connected = Signal(bool, str)
    completed = Signal(object, object, str)
    trace = Signal(str, bytes)

    def __init__(self, port_factory=None):
        super().__init__()
        self.port = self.bridge = self.traced = None
        self.port_factory = port_factory

    @Slot(object)
    def open_port(self, options):
        try:
            if options["demo"]:
                self.port = DemoPort()
            else:
                import serial
                factory = self.port_factory or serial.Serial
                self.port = factory(options["port"], options["baud"], timeout=0.03,
                                    write_timeout=1, bytesize=8, parity="N", stopbits=1,
                                    xonxoff=False, rtscts=False, dsrdtr=False)
                self.port.reset_input_buffer()
            self.traced = TracePort(self.port, self.trace.emit)
            self.bridge = Bridge(self.traced, timeout=options["timeout"])
            self.connected.emit(True, "离线演示模型" if options["demo"] else options["port"])
        except Exception as error:
            self._close()
            self.connected.emit(False, str(error))

    def _close(self):
        if self.port is not None:
            try:
                self.port.close()
            except Exception:
                pass
        self.port = self.bridge = self.traced = None

    @Slot()
    def close_port(self):
        self._close()
        self.connected.emit(False, "已断开")

    @Slot(object)
    def execute(self, job):
        started = time.monotonic()
        result, error = None, ""
        try:
            if self.bridge is None:
                raise RuntimeError("串口尚未连接")
            if job["kind"] == "status":
                result = [self._transact(3, offset, 0) for offset in range(6)]
            elif job["kind"] == "batch_restart":
                # HMC7044 register 0x0001 bit1 controls divider/FSM restart.
                # Do not overwrite the other mode bits with a fixed literal.
                base = self._transact(2, 1, 0) & ~0x02
                self._transact(1, 1, base)
                self._transact(1, 1, base | 0x02)
                time.sleep(0.001)
                result = self._transact(1, 1, base)
            else:
                result = self._transact(job["command"], job["address"], job.get("data", 0))
        except Exception as caught:
            error = ("响应超时 (timeout)：" if isinstance(caught, TimeoutError) else "") + str(caught)
            # Timeouts leave the connection available for a deliberate next command.
            # OS I/O errors mean this device is no longer a usable connection.
            if isinstance(caught, OSError) and not isinstance(caught, TimeoutError):
                self._close()
                self.connected.emit(False, error)
        finally:
            if self.traced:
                self.traced.flush_trace()
        self.completed.emit(dict(job, elapsed_ms=round((time.monotonic() - started) * 1000, 1)),
                            result, error)

    def _transact(self, command, address, data):
        try:
            return self.bridge.transact(command, address, data)
        finally:
            self.traced.flush_trace()
