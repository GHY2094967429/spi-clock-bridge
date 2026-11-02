"""Clock Bridge Studio — Qt 6 desktop front end for the FPGA bridge v2."""
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from gui_backend import SerialWorker, hex_number, load_csv
from official_config import ConfigStep, load_configuration


STYLE = """
QWidget { font-family: 'Microsoft YaHei UI', 'Segoe UI'; font-size: 13px; color: #24344c; }
QMainWindow, QWidget#canvas { background: #eef3f9; }
QFrame#hero { background: #122843; border-radius: 12px; }
QLabel#title { color: white; font-size: 24px; font-weight: 700; }
QLabel#subtitle { color: #a9c5e3; font-size: 12px; }
QLabel#badge { color: #c9e6ff; background: #23496c; padding: 7px 12px; border-radius: 13px; }
QFrame#card { background: white; border: 1px solid #dce5f0; border-radius: 10px; }
QLabel#section { font-size: 15px; font-weight: 700; color: #16304d; }
QLabel#muted { color: #64768c; }
QLabel#notice { color: #896020; background: #fff4dc; padding: 10px; border-radius: 6px; }
QLabel#result { color: #1569b5; font-size: 42px; font-family: Consolas; font-weight: 700; }
QPushButton { background: #f5f8fc; border: 1px solid #cfdae8; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background: #e7effa; border-color: #7da8db; }
QPushButton#primary { background: #1769d2; border-color: #1769d2; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #1159b7; }
QPushButton:disabled { color: #9aa9ba; background: #f0f3f7; border-color: #e0e6ed; }
QPushButton#primary:disabled { color: #9aa9ba; background: #e0e6ed; border-color: #e0e6ed; }
QLineEdit, QComboBox, QDoubleSpinBox { background: white; border: 1px solid #cbd8e8; border-radius: 5px; padding: 7px; min-height: 18px; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #1769d2; }
QTabWidget::pane { background: white; border: 1px solid #dce5f0; border-radius: 8px; }
QTabBar::tab { padding: 11px 20px; background: #e4ebf5; margin-right: 3px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: white; color: #1769d2; font-weight: 700; }
QTableWidget { border: 1px solid #e0e7f0; background: white; alternate-background-color: #f6f9fd; gridline-color: #e9eff6; selection-background-color: #dbeafa; selection-color: #183750; }
QHeaderView::section { background: #eef3f9; border: none; padding: 9px; color: #58708d; font-weight: 600; }
QPlainTextEdit { border: 1px solid #dce5f0; border-radius: 6px; background: #f8fafd; font-family: Consolas, 'Microsoft YaHei UI'; font-size: 12px; }
QProgressBar { border: 1px solid #dce5f0; border-radius: 4px; text-align: center; background: #edf2f9; min-height: 17px; }
QProgressBar::chunk { background: #4f95ec; border-radius: 3px; }
QStatusBar { background: #e6edf6; color: #526a84; }
QSplitter::handle { background: transparent; width: 12px; height: 12px; }
"""

FLAG_LABELS = (
    "FPGA 时钟 locked", "初始化写入完成", "关键寄存器校验结束", "自动校验失败（保持）",
    "HMC GPIO 电平", "SPI 正在忙", "队列曾溢出（保持）", "UART 曾异常（保持）",
)


def app_icon():
    pix = QPixmap(64, 64)
    pix.fill(QColor("#122843"))
    painter = QPainter(pix)
    painter.setPen(QPen(QColor("#68bdff"), 5))
    for x, y in ((9, 39), (25, 23), (41, 39)):
        painter.drawLine(x, y, x + 14, y)
    painter.drawLine(23, 39, 23, 23)
    painter.drawLine(39, 23, 39, 39)
    painter.end()
    return QIcon(pix)


def label(text, name=None, wrap=False):
    value = QLabel(text)
    if name:
        value.setObjectName(name)
    value.setWordWrap(wrap)
    return value


def button(text, callback, primary=False):
    value = QPushButton(text)
    if primary:
        value.setObjectName("primary")
    value.clicked.connect(callback)
    return value


def card(title):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)
    layout.addWidget(label(title, "section"))
    return frame, layout


class MainWindow(QMainWindow):
    request_open = Signal(object)
    request_close = Signal()
    request_job = Signal(object)

    def __init__(self, worker=None):
        super().__init__()
        self.setWindowTitle("Clock Bridge Studio · 可嵌入式时钟配置调试平台")
        self.setWindowIcon(app_icon())
        self.resize(1230, 900)
        self.setMinimumSize(1000, 760)
        self.online = self.busy = self.connecting = self.closing = False
        self.batch_active = self.batch_cancel = False
        self.batch_rows, self.batch_index, self.batch_command = [], 0, 4
        self.batch_steps = []
        self.batch_delay_row = None
        self.batch_delay_timer = QTimer(self)
        self.batch_delay_timer.setSingleShot(True)
        self.batch_delay_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.batch_delay_timer.timeout.connect(self.complete_batch_delay)
        self.success_count = self.failure_count = 0
        self._build_ui()
        self.thread = QThread(self)
        self.worker = worker or SerialWorker()
        self.worker.moveToThread(self.thread)
        self.request_open.connect(self.worker.open_port)
        self.request_close.connect(self.worker.close_port)
        self.request_job.connect(self.worker.execute)
        self.worker.connected.connect(self.on_connected)
        self.worker.completed.connect(self.on_completed)
        self.worker.trace.connect(self.on_trace)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_stopped)
        self.thread.start()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(2000)
        self.poll_timer.timeout.connect(self.poll_status)
        self.poll_timer.start()
        self.refresh_ports()
        self.update_controls()
        self.log("INFO", "就绪。选择真实串口，或选择离线演示。默认使用 v2 CRC 协议。")

    def _build_ui(self):
        canvas = QWidget()
        canvas.setObjectName("canvas")
        self.setCentralWidget(canvas)
        root = QVBoxLayout(canvas)
        root.setContentsMargins(20, 18, 20, 12)
        root.setSpacing(14)
        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 19, 22, 19)
        titles = QVBoxLayout()
        titles.addWidget(label("CLOCK BRIDGE  /  时钟配置工作台", "title"))
        titles.addWidget(label("UART → FPGA → SPI / SDIO     ·     HMC7044     ·     Qt 6", "subtitle"))
        hero_layout.addLayout(titles)
        hero_layout.addStretch()
        self.connection_badge = label("●  未连接", "badge")
        hero_layout.addWidget(self.connection_badge)
        root.addWidget(hero)
        self.banner = label("", "notice", True)
        self.banner.setVisible(False)
        root.addWidget(self.banner)

        body = QHBoxLayout()
        body.setSpacing(14)
        sidebar = QWidget()
        sidebar.setFixedWidth(300)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(14)
        connection, layout = card("01  设备连接")
        self.mode = QComboBox()
        self.mode.addItems(("真实串口", "离线演示（软件模型）"))
        self.mode.currentIndexChanged.connect(self.mode_changed)
        layout.addWidget(self.mode)
        port_row = QHBoxLayout()
        self.port = QComboBox()
        self.port.setEditable(True)
        self.port.setMinimumWidth(110)
        self.refresh = button("刷新", self.refresh_ports)
        port_row.addWidget(self.port, 1)
        port_row.addWidget(self.refresh)
        layout.addLayout(port_row)
        baud_row = QHBoxLayout()
        baud_row.addWidget(label("波特率"))
        self.baud = QComboBox()
        self.baud.addItems(("115200", "57600", "230400", "9600"))
        self.baud.setToolTip("必须与 FPGA UART 参数一致；当前 bit 默认 115200")
        baud_row.addWidget(self.baud, 1)
        layout.addLayout(baud_row)
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(label("响应超时"))
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(0.2, 10)
        self.timeout.setSingleStep(0.2)
        self.timeout.setValue(1.0)
        self.timeout.setSuffix(" s")
        timeout_row.addWidget(self.timeout, 1)
        layout.addLayout(timeout_row)
        layout.addWidget(label("8N1 · 无流控 · v2 CRC-8\n波特率须与 FPGA 一致", "muted", True))
        self.connect_button = button("连接设备", self.toggle_connection, True)
        layout.addWidget(self.connect_button)
        side.addWidget(connection)

        status, layout = card("02  桥接状态")
        self.flags = []
        for title in FLAG_LABELS:
            row = QHBoxLayout()
            row.addWidget(label(title))
            value = label("—")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(value)
            layout.addLayout(row)
            self.flags.append(value)
        self.status_detail = label("尚无状态数据", "muted", True)
        layout.addWidget(self.status_detail)
        self.status_button = button("查询状态", self.query_status)
        layout.addWidget(self.status_button)
        self.auto_poll = QCheckBox("每 2 秒查询（空闲时）")
        layout.addWidget(self.auto_poll)
        layout.addWidget(label("GPIO 仅表示输入电平，需确认板上连线与 GPO 功能。", "muted", True))
        side.addWidget(status)
        side.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(sidebar)
        scroll.setFixedWidth(316)
        body.addWidget(scroll)

        right = QSplitter(Qt.Orientation.Vertical)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._register_tab(), "寄存器调试")
        self.tabs.addTab(self._batch_tab(), "批量配置")
        right.addWidget(self.tabs)
        logs, layout = card("通信日志")
        log_toolbar = QHBoxLayout()
        self.stats = label("成功 0  /  失败 0", "muted")
        log_toolbar.addWidget(self.stats)
        log_toolbar.addStretch()
        log_toolbar.addWidget(button("导出日志", self.export_log))
        log_toolbar.addWidget(button("清空", lambda: self.log_view.clear()))
        layout.addLayout(log_toolbar)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setMinimumHeight(90)
        layout.addWidget(self.log_view)
        right.addWidget(logs)
        right.setSizes([440, 220])
        body.addWidget(right, 1)
        root.addLayout(body, 1)
        self.statusBar().showMessage("所有地址与数据输入均为十六进制  ·  写命令不会自动重试")

    def _register_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 22, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(label("在线寄存器访问", "section"))
        layout.addWidget(label("13 位地址 / 8 位数据。读取不会写入，写后校验执行 CMD 04。", "muted", True))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.addWidget(label("寄存器地址  HEX"), 0, 0)
        grid.addWidget(label("写入数据  HEX"), 0, 1)
        self.address = QLineEdit("0x0008")
        self.data = QLineEdit("0x5A")
        self.address.setMaxLength(6)
        self.data.setMaxLength(4)
        self.address.setPlaceholderText("0000 — 1FFF")
        self.data.setPlaceholderText("00 — FF")
        grid.addWidget(self.address, 1, 0)
        grid.addWidget(self.data, 1, 1)
        layout.addLayout(grid)
        actions = QHBoxLayout()
        self.read_button = button("读取寄存器", lambda: self.register_job(2))
        self.write_button = button("写入寄存器", lambda: self.register_job(1))
        self.verify_button = button("写入并回读校验", lambda: self.register_job(4), True)
        for action in (self.read_button, self.write_button, self.verify_button):
            actions.addWidget(action)
        layout.addLayout(actions)
        result_row = QHBoxLayout()
        result_text = QVBoxLayout()
        result_text.addWidget(label("最近一次寄存器结果", "muted"))
        self.result = label("—", "result")
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result_text.addWidget(self.result)
        self.result_detail = label("等待操作", "muted", True)
        result_text.addWidget(self.result_detail)
        result_row.addLayout(result_text)
        result_row.addStretch()
        self.bits = label("— — — —  — — — —", "muted")
        self.bits.setStyleSheet("font-family: Consolas; font-size: 18px;")
        result_row.addWidget(self.bits)
        layout.addLayout(result_row)
        layout.addWidget(label("首轮连通性测试可使用 0x0008 暂存器。\n写后校验适用于稳定可读写寄存器；自清零或动态位可能导致不一致。", "muted", True))
        layout.addStretch()
        return page

    def _batch_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        row = QHBoxLayout()
        self.import_button = button("导入官方配置 / CSV", self.import_csv)
        self.sample_button = button("加载演示表", self.sample_rows)
        row.addWidget(self.import_button)
        row.addWidget(self.sample_button)
        row.addStretch()
        row.addWidget(button("导出结果", self.export_csv))
        layout.addLayout(row)
        layout.addWidget(label("官方 GUI 的 Save Config 导出 .py 可直接导入；完整校验后预览，点击开始才下发。", "muted", True))
        self.batch_source = label("尚未导入配置。保留文件顺序与重复地址；不执行配置文件中的 Python 代码。", "muted", True)
        layout.addWidget(self.batch_source)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("地址 HEX / 操作", "设定值 HEX / 时间", "返回值", "执行结果", "来源行"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)
        options = QHBoxLayout()
        self.batch_action = QComboBox()
        self.batch_action.addItems(("逐条写入并校验", "仅写入", "仅读取（不写入）"))
        options.addWidget(self.batch_action)
        options.addWidget(label("遇到失败立即停止", "muted"))
        options.addStretch()
        self.start_button = button("开始执行", self.start_batch, True)
        self.cancel_button = button("停止", self.cancel_batch)
        options.addWidget(self.start_button)
        options.addWidget(self.cancel_button)
        layout.addLayout(options)
        self.restart_after = QCheckBox("写入完成后发送 Restart 请求（0x0001 bit1，可能暂时中断输出时钟）")
        self.restart_after.setChecked(False)
        layout.addWidget(self.restart_after)
        layout.addWidget(label("官方 PY 默认仅写入。触发位/自清零位不宜逐条比较；配置需匹配板卡参考源和 VCXO，调整时钟前先暂停相关业务。", "muted", True))
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("尚未执行")
        layout.addWidget(self.progress)
        return page

    def log(self, kind, message):
        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_view.appendPlainText(f"{stamp}  {kind:<5} {message}")

    @Slot(str, bytes)
    def on_trace(self, direction, data):
        self.log(direction, data.hex(" ").upper())

    def refresh_ports(self):
        from serial.tools import list_ports
        previous = self.port.currentText().split(" · ")[0]
        self.port.clear()
        for port in list_ports.comports():
            self.port.addItem(f"{port.device} · {port.description}", port.device)
        index = self.port.findData(previous)
        if index >= 0:
            self.port.setCurrentIndex(index)
        elif previous:
            self.port.setEditText(previous)

    def mode_changed(self):
        demo = bool(self.mode.currentIndex())
        if demo:
            self.banner.setText("离线演示模式：仅使用本地软件寄存器模型，不代表 FPGA 仿真或上板测试结果。")
        else:
            self.banner.setText("")
        self.banner.setVisible(demo)
        self.clear_status()
        self.update_controls()

    def clear_status(self):
        for field in self.flags:
            field.setText("—")
            field.setStyleSheet("")
        self.status_detail.setText("尚无状态数据")
        self.result.setText("—")
        self.result_detail.setText("等待操作")
        self.bits.setText("— — — —  — — — —")

    def toggle_connection(self):
        if self.online:
            self.connecting = True
            self.request_close.emit()
        else:
            name = self.port.currentText().split(" · ")[0].strip()
            if not self.mode.currentIndex() and not name:
                self.log("ERROR", "请先选择或输入串口，例如 COM5")
                return
            self.connecting = True
            self.clear_status()
            self.request_open.emit({"demo": bool(self.mode.currentIndex()), "port": name,
                                    "baud": int(self.baud.currentText()), "timeout": self.timeout.value()})
        self.update_controls()

    @Slot(bool, str)
    def on_connected(self, state, detail):
        self.online, self.connecting = state, False
        mode = "演示" if self.mode.currentIndex() else "串口"
        self.connection_badge.setText(f"●  {mode}已连接" if state else "●  未连接")
        self.log("INFO" if state or detail == "已断开" else "ERROR", detail)
        if not state:
            self.clear_status()
            self.batch_cancel = True
            if self.batch_active and not self.busy:
                self.finish_batch("连接已断开")
        self.update_controls()
        if state:
            self.query_status()
        if self.closing and not self.busy:
            if state:
                self.request_close.emit()
            else:
                self.thread.quit()

    def update_controls(self):
        available = self.online and not self.busy and not self.batch_active and not self.closing
        idle = not self.busy and not self.batch_active and not self.connecting and not self.closing
        disconnected = not self.online and not self.connecting and not self.closing
        for item in (self.mode, self.baud, self.timeout):
            item.setEnabled(disconnected)
        for item in (self.port, self.refresh):
            item.setEnabled(disconnected and self.mode.currentIndex() == 0)
        self.connect_button.setEnabled(idle)
        self.connect_button.setText("连接中…" if self.connecting else ("断开连接" if self.online else "连接设备"))
        for item in (self.read_button, self.write_button, self.verify_button, self.status_button):
            item.setEnabled(available)
        for item in (self.address, self.data, self.import_button, self.sample_button, self.batch_action, self.restart_after):
            item.setEnabled(not self.batch_active and not self.closing)
        self.start_button.setEnabled(available and bool(self.batch_rows))
        self.cancel_button.setEnabled(self.batch_active and not self.batch_cancel)

    def submit(self, job):
        if not self.online or self.busy or self.closing:
            return False
        self.busy = True
        self.update_controls()
        self.request_job.emit(job)
        return True

    def register_job(self, command):
        if self.batch_active:
            return
        try:
            address = hex_number(self.address.text(), 0x1FFF)
            data = hex_number(self.data.text(), 0xFF) if command != 2 else 0
        except ValueError as error:
            self.log("ERROR", str(error))
            return
        self.result.setText("…")
        self.bits.setText("等待回复")
        self.result_detail.setText(f"0x{address:04X} · 处理中")
        self.submit({"kind": "register", "command": command, "address": address, "data": data})

    def query_status(self):
        if not self.batch_active:
            self.submit({"kind": "status"})

    def poll_status(self):
        if self.auto_poll.isChecked() and self.online and not self.busy and not self.batch_active:
            self.query_status()

    @Slot(object, object, str)
    def on_completed(self, job, result, error):
        self.busy = False
        is_delay = job.get("operation") == "delay"
        if error:
            self.failure_count += 1
            self.log("ERROR", error)
            if "timeout" in error.lower():
                self.log("INFO", "本次操作超时；设备是否已执行写入未知，不会自动重试。")
        elif not is_delay:
            self.success_count += 1
        self.stats.setText(f"成功 {self.success_count}  /  失败 {self.failure_count}")
        if job["kind"] == "status":
            if error:
                for field in self.flags:
                    field.setText("未知")
                    field.setStyleSheet("color: #9a6a20;")
                self.status_detail.setText("本次查询失败；状态未知")
            else:
                self.show_status(result)
        elif job["kind"] == "register":
            command_name = {1: "写入完成", 2: "读取完成", 4: "回读一致"}[job["command"]]
            self.result.setText("失败" if error else f"0x{result:02X}")
            self.result_detail.setText(f"0x{job['address']:04X} · " + (error if error else f"{command_name} · {job['elapsed_ms']} ms"))
            self.bits.setText("—" if error else f"{result:08b}"[:4] + " " + f"{result:08b}"[4:])
            if not error:
                self.log("OK", f"{command_name}  0x{job['address']:04X} → 0x{result:02X}")
        elif job["kind"] == "batch":
            row = job["row"]
            self.table.item(row, 2).setText("—" if error or is_delay else f"0x{result:02X}")
            self.table.item(row, 3).setText(error if error else "延时完成" if is_delay else {1: "写入完成", 2: "读取完成", 4: "回读一致"}[job["command"]])
            self.table.item(row, 3).setForeground(QColor("#b84038" if error else "#167454"))
            self.batch_index = row + 1
            self.progress.setValue(self.batch_index)
            if error or self.batch_cancel or not self.online or self.closing:
                self.finish_batch("失败停止" if error else "已停止")
            elif self.batch_index == len(self.batch_rows):
                if self.restart_after.isChecked() and self.batch_command != 2:
                    self.progress.setFormat("寄存器下发完成，正在发送 Restart…")
                    self.log("INFO", "发送 Restart：读取 0x0001，保留其他控制位，对 bit1 先清零、置位、再清零。")
                    self.submit({"kind": "batch_restart"})
                else:
                    self.finish_batch("已完成")
            else:
                # Schedule between transactions so a Stop click is processed before the next send.
                QTimer.singleShot(20, self.next_batch)
        elif job["kind"] == "batch_restart":
            if not error:
                self.log("OK", "Restart 请求已发送；请核对芯片状态及输出时钟。")
            self.finish_batch("Restart 失败停止" if error else "已停止" if self.batch_cancel else "已完成含 Restart")
        self.update_controls()
        if self.closing:
            self.request_close.emit()

    def show_status(self, values):
        flags = values[0]
        for bit, field in enumerate(self.flags):
            on = bool(flags & (1 << bit))
            if bit == 4:
                field.setText("高" if on else "低")
            elif bit in (3, 6, 7):
                field.setText("异常" if on else "未置位")
            elif bit == 5:
                field.setText("忙" if on else "空闲")
            else:
                field.setText("是" if on else "否")
            color = "#b84038" if on and bit in (3, 6, 7) else "#167454" if on else "#64768c"
            field.setStyleSheet(f"color: {color}; font-weight: 600;")
        stamp = datetime.now().strftime("%H:%M:%S")
        details = f"协议 0x{values[5]:02X} · 更新于 {stamp}"
        if flags & 8:
            details += f"\n首个失败：0x{((values[1] << 8) | values[2]):04X}\n期望 0x{values[3]:02X} / 实际 0x{values[4]:02X}"
        self.status_detail.setText(details)
        self.log("OK", f"状态 0x{flags:02X} · 协议 0x{values[5]:02X}" + ("（软件模型）" if self.mode.currentIndex() else ""))

    def set_rows(self, rows):
        self.set_steps([ConfigStep("write", address, data) for address, data in rows])
        self.restart_after.setChecked(False)
        self.batch_source.setText("手动或演示寄存器表；按输入顺序执行，结果见表格与进度条。")

    def set_steps(self, steps):
        steps = list(steps)
        self.batch_steps = steps
        self.batch_rows = [(step.address, step.data) for step in steps]
        self.table.setRowCount(len(steps))
        for index, step in enumerate(steps):
            address = f"0x{step.address:04X}" if step.kind == "write" else "延时"
            data = f"0x{step.data:02X}" if step.kind == "write" else f"{step.delay_ms} ms"
            for col, text in enumerate((address, data, "—", "待执行", str(step.line) if step.line else "—")):
                item = QTableWidgetItem(text)
                item.setToolTip(step.comment or "无寄存器注释")
                self.table.setItem(index, col, item)
        self.progress.setRange(0, len(steps))
        self.progress.setValue(0)
        self.progress.setFormat(f"已加载 {len(steps)} 个操作")
        self.update_controls()

    def sample_rows(self):
        # Scratch register only; do not silently load the clock's full initialization table.
        self.set_rows([(8, 0x5A), (8, 0xA5), (8, 0)])
        self.log("INFO", "已加载演示表：仅访问 0x0008 暂存器，尚未执行")

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入官方 HMC7044 配置或 CSV", "", "HMC7044 配置 (*.py *.csv);;官方 Save Config (*.py);;寄存器 CSV (*.csv)")
        if not path:
            return
        try:
            self.load_configuration_file(path)
        except (OSError, ValueError, UnicodeError) as error:
            QMessageBox.warning(self, "导入失败", str(error))

    def load_configuration_file(self, path):
        if self.batch_active or self.closing:
            raise ValueError("请等待当前批量操作停止后再导入")
        config = load_configuration(path)  # Validate every statement before replacing the preview.
        self.set_steps(config.steps)
        if Path(path).suffix.lower() == ".py":
            self.batch_action.setCurrentIndex(1)
        self.restart_after.setChecked(False)
        waits = sum(step.kind == "delay" for step in config.steps)
        self.batch_source.setText(f"{config.filename} · {config.format}\n{config.write_count} 次写入，重复地址 {config.duplicate_count} 次，延时 {waits} 次 · SHA256 {config.sha256[:16]}…\n导入仅预览；执行状态见进度条，悬停查看字段注释。")
        self.log("INFO", f"导入 {config.filename}：{config.write_count} 次写入 / {waits} 次延时；SHA256 {config.sha256}；仅预览，尚未执行")
        return config

    def start_batch(self):
        if not self.online or self.busy or self.batch_active or not self.batch_rows:
            return
        self.batch_active, self.batch_cancel, self.batch_index = True, False, 0
        self.batch_delay_row = None
        self.batch_command = (4, 1, 2)[self.batch_action.currentIndex()]
        for row in range(len(self.batch_rows)):
            self.table.item(row, 2).setText("—")
            self.table.item(row, 3).setText("待执行")
            self.table.item(row, 3).setForeground(QColor("#24344c"))
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m")
        self.log("INFO", f"批量开始：{len(self.batch_rows)} 条，{self.batch_action.currentText()}")
        self.next_batch()

    def next_batch(self):
        if not self.batch_active or self.busy or self.batch_delay_row is not None:
            return
        if self.batch_cancel or not self.online or self.closing:
            self.finish_batch("已停止")
            return
        row = self.batch_index
        step = self.batch_steps[row]
        self.table.item(row, 3).setText("执行中…")
        self.table.scrollToItem(self.table.item(row, 0))
        if step.kind == "delay":
            self.batch_delay_row = row
            self.table.item(row, 3).setText("等待延时…")
            self.log("INFO", f"配置第 {step.line} 行：延时 {step.delay_ms} ms")
            self.batch_delay_timer.start(step.delay_ms)
        else:
            self.submit({"kind": "batch", "row": row, "command": self.batch_command, "address": step.address, "data": step.data})

    def complete_batch_delay(self):
        row, self.batch_delay_row = self.batch_delay_row, None
        if row is not None and self.batch_active:
            self.on_completed({"kind": "batch", "operation": "delay", "row": row}, None, "")

    def cancel_batch(self):
        self.batch_cancel = True
        self.log("INFO", "停止已请求：等待当前事务返回或超时后停止；已写入的值不会回滚。")
        if not self.busy:
            self.finish_batch("已停止")
        self.update_controls()

    def finish_batch(self, reason):
        self.batch_delay_timer.stop()
        if self.batch_delay_row is not None:
            self.table.item(self.batch_delay_row, 3).setText("延时未完成")
            self.batch_delay_row = None
        self.batch_active = False
        self.progress.setFormat(f"{reason}  {self.batch_index} / {len(self.batch_rows)}")
        self.log("INFO", f"批量{reason}：已处理 {self.batch_index}/{len(self.batch_rows)} 条")
        self.update_controls()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出批量结果", "register_results.csv", "CSV (*.csv)")
        if path:
            try:
                with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(("address", "data", "actual", "result", "source_line", "comment"))
                    for row in range(self.table.rowCount()):
                        writer.writerow([self.table.item(row, col).text() for col in range(5)] + [self.batch_steps[row].comment])
                self.log("INFO", f"已导出 {Path(path).name}")
            except OSError as error:
                QMessageBox.warning(self, "导出失败", str(error))

    def export_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", "bridge_log.txt", "Text (*.txt)")
        if path:
            try:
                mode = "离线演示（软件模型）" if self.mode.currentIndex() else "真实串口"
                Path(path).write_text(f"Clock Bridge Studio | {mode}\n{datetime.now().isoformat()}\n"
                                      + self.log_view.toPlainText(), encoding="utf-8")
            except OSError as error:
                QMessageBox.warning(self, "导出失败", str(error))

    def closeEvent(self, event):
        if not self.thread.isRunning():
            event.accept()
            return
        event.ignore()
        if not self.closing:
            self.closing = self.batch_cancel = True
            if self.batch_active and not self.busy:
                self.finish_batch("关闭已停止")
            self.poll_timer.stop()
            self.banner.setText("正在关闭连接；等待当前事务结束或超时…")
            self.update_controls()
            if not self.busy:
                self.request_close.emit()

    @Slot()
    def _thread_stopped(self):
        if self.closing:
            self.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="connect to the local software model")
    parser.add_argument("--self-test", metavar="JSON", help="run an offline smoke check and save results; never opens a real port")
    parser.add_argument("--self-test-config", metavar="PY", help="also import and replay this config in the offline self-test")
    args = parser.parse_args()
    if args.self_test_config and not args.self_test:
        parser.error("--self-test-config requires --self-test JSON")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    if args.self_test:
        from gui_smoke import SmokeCheck
        app.setQuitOnLastWindowClosed(False)
        window.smoke_check = SmokeCheck(app, window, args.self_test, args.self_test_config)
    elif args.demo:
        window.mode.setCurrentIndex(1)
        QTimer.singleShot(0, window.toggle_connection)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
