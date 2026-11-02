"""Qt event-loop integration tests. No physical serial device is used."""
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from clock_bridge_gui import MainWindow, STYLE
    from gui_backend import DemoPort, SerialWorker, hex_number, load_csv
    from clock_bridge import crc8
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "install host/requirements-gui.txt for Qt integration tests")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.window = None

    def wait_for(self, predicate, seconds=4):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.003)
        self.fail("Qt operation did not finish in time")

    def tearDown(self):
        if self.window:
            self.window.close()
            self.wait_for(lambda: not self.window.thread.isRunning())
            self.window.deleteLater()
            self.app.processEvents()

    def connect_demo(self):
        self.window = MainWindow()
        self.window.mode.setCurrentIndex(1)
        self.window.toggle_connection()
        self.wait_for(lambda: self.window.online and not self.window.busy and self.window.success_count == 1)
        return self.window

    def connect_fake(self, fake):
        self.window = MainWindow(SerialWorker(port_factory=lambda *args, **kwargs: fake))
        self.window.port.setEditText("TEST_PORT")
        self.window.timeout.setValue(0.2)
        self.window.toggle_connection()
        self.wait_for(lambda: self.window.online and not self.window.busy and self.window.success_count == 1)
        return self.window

    def test_demo_write_read_and_status(self):
        window = self.connect_demo()
        self.assertIn("软件", window.banner.text())
        self.assertEqual(window.flags[4].text(), "低")
        self.assertIn("0x20", window.status_detail.text())
        window.data.setText("A5")
        window.register_job(4)
        self.wait_for(lambda: not window.busy)
        self.assertEqual(window.result.text(), "0xA5")
        self.assertIn("回读一致", window.result_detail.text())
        window.register_job(2)
        self.wait_for(lambda: not window.busy)
        self.assertEqual(window.result.text(), "0xA5")
        self.assertIn("TX", window.log_view.toPlainText())
        self.assertIn("RX", window.log_view.toPlainText())
        window.toggle_connection()
        self.wait_for(lambda: not window.online)
        self.assertEqual(window.result.text(), "—")
        self.assertEqual(window.flags[0].text(), "—")

    def test_batch_order_and_stop_between_transactions(self):
        window = self.connect_demo()
        window.sample_rows()
        window.start_batch()
        self.wait_for(lambda: not window.batch_active)
        self.assertEqual([window.table.item(row, 2).text() for row in range(3)], ["0x5A", "0xA5", "0x00"])
        window.set_rows([(8, i) for i in range(40)])
        window.start_batch()
        self.wait_for(lambda: window.batch_index >= 1)
        window.cancel_batch()
        self.wait_for(lambda: not window.batch_active and not window.busy)
        self.assertLess(window.batch_index, 40)
        self.assertEqual(window.table.item(39, 3).text(), "待执行")
        self.assertIn("已停止", window.progress.format())

    def test_timeout_does_not_block_ui_or_retry_write(self):
        class SilentWrite(DemoPort):
            def __init__(self):
                super().__init__()
                self.writes = 0
            def reset_input_buffer(self):
                self.buffer.clear()
            def write(self, data):
                if data[3] == 1:
                    self.writes += 1
                    return len(data)
                return super().write(data)
            def read(self, count):
                if not self.buffer:
                    time.sleep(0.005)
                return super().read(count)
        fake = SilentWrite()
        window = self.connect_fake(fake)
        ticks = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        window.register_job(1)
        self.wait_for(lambda: not window.busy)
        timer.stop()
        self.assertGreater(len(ticks), 5)
        self.assertEqual(fake.writes, 1)
        self.assertEqual(window.failure_count, 1)
        self.assertIn("timeout", window.result_detail.text())
        window.register_job(2)
        self.wait_for(lambda: not window.busy)
        self.assertEqual(window.result.text(), "0x00")

    def test_failed_verification_stops_batch(self):
        class BadReadback(DemoPort):
            def reset_input_buffer(self):
                self.buffer.clear()
            def write(self, packet):
                size = super().write(packet)
                if packet[3] == 4:
                    self.buffer[3], self.buffer[7] = 5, 0xEE
                    self.buffer[-1] = crc8(self.buffer[:-1])
                return size
        window = self.connect_fake(BadReadback())
        window.sample_rows()
        window.start_batch()
        self.wait_for(lambda: not window.batch_active)
        self.assertEqual(window.batch_index, 1)
        self.assertIn("mismatch", window.table.item(0, 3).text())
        self.assertEqual(window.table.item(1, 3).text(), "待执行")

    def test_io_failure_disconnects_and_clears_status(self):
        class RemovedPort(DemoPort):
            def reset_input_buffer(self):
                self.buffer.clear()
            def write(self, packet):
                if packet[3] == 2:
                    raise OSError("device removed")
                return super().write(packet)
        window = self.connect_fake(RemovedPort())
        window.register_job(2)
        self.wait_for(lambda: not window.online and not window.busy)
        self.assertFalse(window.read_button.isEnabled())
        self.assertEqual(window.flags[0].text(), "—")

    def test_csv_all_rows_checked_and_hex_semantics(self):
        self.assertEqual(hex_number("0010", 0x1FFF), 16)
        self.assertEqual(hex_number("FF", 255), 255)
        for invalid in ("", "-1", "0b101", "10000"):
            with self.assertRaises(ValueError):
                hex_number(invalid, 255)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"
            path.write_text("address,data\n0008,5A\n000A,FF\n", encoding="utf-8-sig")
            self.assertEqual(load_csv(path), [(8, 90), (10, 255)])
            path.write_text("address,data\n0008,5A\n2000,FF\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "3"):
                load_csv(path)

    def test_close_waits_for_current_transaction_and_closes_port(self):
        class SlowPort(DemoPort):
            def reset_input_buffer(self):
                self.buffer.clear()
            def write(self, packet):
                if packet[3] == 4:
                    time.sleep(0.1)
                return super().write(packet)
        fake = SlowPort()
        window = self.connect_fake(fake)
        window.register_job(4)
        window.close()
        self.wait_for(lambda: not window.thread.isRunning())
        self.assertTrue(fake.closed)
        self.assertFalse(window.online)


    def test_official_preview_is_atomic_and_defaults_to_write_only(self):
        w=self.connect_demo()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'official.py';p.write_text('dut.write(8,1)\ndut.write(8,2)\n',encoding='utf-8')
            jobs=w.success_count
            w.load_configuration_file(p)
            self.assertEqual(w.success_count,jobs)
            self.assertNotIn(8,w.worker.port.registers)
            self.assertEqual(w.batch_rows,[(8,1),(8,2)])
            self.assertEqual(w.batch_action.currentIndex(),1)
            p.write_text('dut.write(8,3)\nimport os\n',encoding='utf-8')
            with self.assertRaises(ValueError):w.load_configuration_file(p)
            self.assertEqual(w.batch_rows,[(8,1),(8,2)])

    def test_ordered_import_delay_and_restart_preserve_mode_bits(self):
        class Recorder(DemoPort):
            def __init__(self):super().__init__();self.records=[]
            def reset_input_buffer(self):self.buffer.clear()
            def write(self,p):
                if p[3] in (1,4):self.records.append((p[4]<<8|p[5],p[6],time.monotonic()))
                return super().write(p)
        fake=Recorder();w=self.connect_fake(fake)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'official.py';p.write_text('dut.write(1,0x40)\ndut.write(8,1)\ntime.sleep(0.08)\ndut.write(8,2)\n',encoding='utf-8')
            w.load_configuration_file(p);w.restart_after.setChecked(True);w.start_batch()
            self.wait_for(lambda:not w.batch_active)
            self.assertEqual([(a,d) for a,d,t in fake.records],[(1,0x40),(8,1),(8,2),(1,0x40),(1,0x42),(1,0x40)])
            self.assertGreaterEqual(fake.records[2][2]-fake.records[1][2],.075)
            self.assertEqual(fake.registers[1],0x40)
            self.assertEqual(w.table.item(2,3).text(),'延时完成')

    def test_cancel_and_close_during_import_delay(self):
        w=self.connect_demo()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'delay.py';p.write_text('dut.write(8,1)\ntime.sleep(20)\ndut.write(8,2)',encoding='utf-8')
            w.load_configuration_file(p);w.start_batch()
            self.wait_for(lambda:w.batch_delay_row is not None)
            w.cancel_batch()
            self.assertFalse(w.batch_active)
            self.assertFalse(w.batch_delay_timer.isActive())
            self.assertEqual(w.worker.port.registers[8],1)
            w.start_batch();self.wait_for(lambda:w.batch_delay_row is not None)
            w.close();self.wait_for(lambda:not w.thread.isRunning())
            self.assertFalse(w.batch_delay_timer.isActive())


if __name__ == "__main__":
    unittest.main()
