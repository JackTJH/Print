"""Server main window (PyQt5)."""

import os
import socket
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QPushButton, QTableView,
    QHeaderView, QGroupBox, QMessageBox, QAbstractItemView,
)

from common.constants import DEFAULT_PORT, RECEIVED_DIR
from .logger import LogModel, FileHistoryModel
from .tcp_server import TcpServerThread
from .print_manager import PrintManager


class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TCP 打印上位机")
        self.setMinimumSize(800, 550)
        self._server: TcpServerThread | None = None

        # Models
        self.log_model = LogModel(self)
        self.file_model = FileHistoryModel(self)

        # Print manager
        self._print_mgr = PrintManager(self)
        self._print_mgr.print_result.connect(self.file_model.update_status)
        self._print_mgr.print_result.connect(self._on_print_result)

        self._setup_ui()
        self._auto_detect_ip()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        # ---- Server Settings ----
        settings_group = QGroupBox("服务设置")
        settings_layout = QHBoxLayout(settings_group)

        settings_layout.addWidget(QLabel("监听 IP:"))
        self.ip_edit = QLineEdit("0.0.0.0")
        self.ip_edit.setFixedWidth(160)
        settings_layout.addWidget(self.ip_edit)

        settings_layout.addWidget(QLabel("端口:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(DEFAULT_PORT)
        self.port_spin.setFixedWidth(100)
        settings_layout.addWidget(self.port_spin)

        self.start_btn = QPushButton("启动服务")
        self.start_btn.clicked.connect(self._start_server)
        settings_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止服务")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_server)
        settings_layout.addWidget(self.stop_btn)

        self.status_label = QLabel("● 未启动")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        settings_layout.addWidget(self.status_label)

        settings_layout.addStretch()
        layout.addWidget(settings_group)

        # ---- Connection Log ----
        log_group = QGroupBox("连接日志")
        log_layout = QVBoxLayout(log_group)
        self.log_table = QTableView()
        self.log_table.setModel(self.log_model)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.verticalHeader().setVisible(False)
        hdr = self.log_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        log_layout.addWidget(self.log_table)
        layout.addWidget(log_group)

        # ---- Received Files ----
        file_group = QGroupBox("已接收文件")
        file_layout = QVBoxLayout(file_group)
        self.file_table = QTableView()
        self.file_table.setModel(self.file_model)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.verticalHeader().setVisible(False)
        fhdr = self.file_table.horizontalHeader()
        fhdr.setSectionResizeMode(0, QHeaderView.Stretch)
        fhdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        fhdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        fhdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        file_layout.addWidget(self.file_table)
        layout.addWidget(file_group)

        # ---- Bottom Buttons ----
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._clear_log)
        btn_layout.addWidget(clear_btn)

        open_dir_btn = QPushButton("打开接收目录")
        open_dir_btn.clicked.connect(self._open_received_dir)
        btn_layout.addWidget(open_dir_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _auto_detect_ip(self):
        """Detect the most likely LAN IP and display it."""
        try:
            ips = []
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if not ip.startswith("127."):
                    ips.append(ip)
            if ips:
                # Prefer 192.168.x.x addresses
                for ip in ips:
                    if ip.startswith("192.168.") or ip.startswith("10."):
                        self.ip_edit.setText(ip)
                        return
                self.ip_edit.setText(ips[0])
        except Exception:
            pass

    def _start_server(self):
        host = self.ip_edit.text().strip()
        port = self.port_spin.value()

        if self._server is not None:
            return

        self._server = TcpServerThread(
            host, port,
            self.log_model, self.file_model, self._print_mgr,
            self,
        )

        # Wire signals
        self._server.error.connect(self._on_server_error)

        self._server.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.ip_edit.setEnabled(False)
        self.port_spin.setEnabled(False)
        self.status_label.setText("● 运行中")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")

    def _stop_server(self):
        if self._server is None:
            return
        self._server.stop()
        self._server = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.ip_edit.setEnabled(True)
        self.port_spin.setEnabled(True)
        self.status_label.setText("● 未启动")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def _on_server_error(self, msg: str):
        QMessageBox.warning(self, "服务错误", msg)

    def _on_print_result(self, filename: str, success: bool):
        status = "打印完成" if success else "打印失败"
        self.log_model.add_entry("", "系统", f"{status}: {filename}")

    def _clear_log(self):
        self.log_model.clear()
        self.file_model.clear()

    def _open_received_dir(self):
        os.makedirs(RECEIVED_DIR, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(RECEIVED_DIR)
        else:
            subprocess.run(["xdg-open", RECEIVED_DIR])

    def closeEvent(self, event):
        if self._server is not None:
            self._server.stop()
        event.accept()
