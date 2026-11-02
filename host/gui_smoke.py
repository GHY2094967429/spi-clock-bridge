"""Event-loop smoke check used to verify a packaged executable without hardware."""
import json
from pathlib import Path
import time

from PySide6.QtCore import QObject, QTimer, Slot


class SmokeCheck(QObject):
    def __init__(self, app, window, output, config_path=None):
        super().__init__(window)
        self.app, self.window, self.output = app, window, Path(output)
        self.phase, self.deadline = 0, time.monotonic() + (100 if config_path else 12)
        self.config_path, self.config = config_path, None
        self.config_tx = []
        window.worker.trace.connect(self.capture_config_trace)
        self.report = {"mode": "software_demo", "hardware_tested": False, "passed": False}
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self.advance)
        self.timer.start()
        window.thread.finished.connect(self.finish)
        self.exit_code = 1

    @Slot()
    def advance(self):
        w = self.window
        try:
            if time.monotonic() > self.deadline:
                raise TimeoutError("packaged application smoke check timed out")
            if self.phase == 0:
                w.mode.setCurrentIndex(1)
                w.toggle_connection()
                self.phase = 1
            elif self.phase == 1 and w.online and not w.busy:
                assert w.success_count == 1 and "0x20" in w.status_detail.text(), "status query failed"
                w.data.setText("0xA5")
                w.register_job(4)
                self.phase = 2
            elif self.phase == 2 and not w.busy:
                assert w.result.text() == "0xA5", "write/readback verification failed"
                w.register_job(2)
                self.phase = 3
            elif self.phase == 3 and not w.busy:
                assert w.result.text() == "0xA5", "read failed"
                w.sample_rows()
                w.start_batch()
                self.phase = 4
            elif self.phase == 4 and not w.batch_active:
                assert w.batch_index == 3 and w.failure_count == 0, "batch operation failed"
                assert [w.table.item(i, 2).text() for i in range(3)] == ["0x5A", "0xA5", "0x00"], "batch order failed"
                self.report.update(passed=True, checks=["status", "write_verify", "read", "batch_order"],
                                   successful_jobs=w.success_count, failed_jobs=w.failure_count)
                if not self.config_path:
                    self.shutdown(0)
                else:
                    self.config = w.load_configuration_file(self.config_path)
                    assert w.batch_action.currentIndex() == 1
                    self.config_tx.clear()
                    self.phase = 5
                    w.start_batch()
            elif self.phase == 5 and not w.batch_active:
                expected = [(step.address, step.data) for step in self.config.steps if step.kind == "write"]
                actual = [(p[4] << 8 | p[5], p[6]) for p in self.config_tx if p[3] == 1]
                assert actual == expected, "imported write order/value mismatch"
                assert w.failure_count == 0 and w.batch_index == len(self.config.steps)
                assert all(w.worker.port.registers[a] == v for a, v in dict(expected).items())
                self.report.update(successful_jobs=w.success_count, failed_jobs=w.failure_count,
                                   configuration={"filename": self.config.filename, "sha256": self.config.sha256,
                                                  "writes": self.config.write_count, "duplicates": self.config.duplicate_count,
                                                  "ordered_writes_match": True, "model_readback_match": True})
                self.shutdown(0)
        except Exception as error:
            self.report["passed"] = False
            self.report["error"] = str(error)
            self.shutdown(1)

    @Slot(str, bytes)
    def capture_config_trace(self, direction, data):
        if self.phase == 5 and direction == "TX":
            self.config_tx.append(bytes(data))

    def shutdown(self, code):
        self.timer.stop()
        self.exit_code = code
        try:
            self.output.parent.mkdir(parents=True, exist_ok=True)
            self.output.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            self.window.close()

    @Slot()
    def finish(self):
        self.app.exit(self.exit_code)
