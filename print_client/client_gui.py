"""Client main window (PyQt5)."""

import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QPushButton, QPlainTextEdit,
    QProgressBar, QFileDialog, QGroupBox, QMessageBox, QTextEdit,
)

from common.constants import DEFAULT_PORT
from .file_sender import FileSenderThread

CONFIG_FILE = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "PrintClient", "config.json"
)


def _load_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_config(host: str, port: int):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"host": host, "port": port}, f, indent=2)
    except Exception:
        pass


class ClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("打印客户端")
        self.setMinimumSize(580, 520)
        self._sender: FileSenderThread | None = None

        self._setup_ui()
        self._apply_style()
        self._load_saved_config()

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F0F4F8;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #B0C4DE;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 16px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #2C3E50;
            }
            QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
            QPushButton:pressed {
                background-color: #2471A3;
            }
            QPushButton:disabled {
                background-color: #BDC3C7;
            }
            QLineEdit, QSpinBox {
                border: 1px solid #B0C4DE;
                border-radius: 4px;
                padding: 4px 6px;
                background: white;
            }
            QPlainTextEdit {
                border: 1px solid #B0C4DE;
                border-radius: 4px;
                background: white;
                font-family: Consolas, monospace;
            }
            QTextEdit {
                border: 1px solid #B0C4DE;
                border-radius: 4px;
                background: #FFFDE7;
                font-size: 12px;
            }
            QProgressBar {
                border: 1px solid #B0C4DE;
                border-radius: 4px;
                text-align: center;
                background: white;
            }
            QProgressBar::chunk {
                background-color: #27AE60;
                border-radius: 3px;
            }
        """)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ---- Server Connection ----
        conn_group = QGroupBox("服务器连接")
        conn_layout = QHBoxLayout(conn_group)

        conn_layout.addWidget(QLabel("IP:"))
        self.ip_edit = QLineEdit("192.168.1.112")
        self.ip_edit.setPlaceholderText("服务器 IP 地址")
        self.ip_edit.setFixedWidth(160)
        conn_layout.addWidget(self.ip_edit)

        conn_layout.addWidget(QLabel("端口:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(DEFAULT_PORT)
        self.port_spin.setFixedWidth(80)
        conn_layout.addWidget(self.port_spin)

        conn_layout.addStretch()
        layout.addWidget(conn_group)

        # ---- File Selection ----
        file_group = QGroupBox("选择文件")
        file_layout = QHBoxLayout(file_group)

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("选择要打印的文件...")
        self.file_edit.setReadOnly(True)
        file_layout.addWidget(self.file_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # ---- Action Buttons ----
        action_layout = QHBoxLayout()

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedHeight(36)
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._send)
        action_layout.addWidget(self.send_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.clicked.connect(self._cancel)
        action_layout.addWidget(self.cancel_btn)

        action_layout.addStretch()

        self.status_label = QLabel("")
        action_layout.addWidget(self.status_label)

        layout.addLayout(action_layout)

        # ---- Progress ----
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(22)
        layout.addWidget(self.progress)

        # ---- Log ----
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setFixedHeight(100)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

        # ---- Usage Instructions ----
        help_group = QGroupBox("使用说明")
        help_layout = QVBoxLayout(help_group)
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setFixedHeight(80)
        help_text.setHtml("""
<b>使用步骤：</b><br>
1. 确认服务端（公共电脑）已启动 <b>PrintServer.exe</b> 并点击了「启动服务」<br>
2. 输入服务端的 <b>IP 地址</b>（可在服务端界面查看）和<b>端口</b>（默认 9090）<br>
3. 点击「浏览」选择要打印的文件，再点击「发送」<br>
4. 文件发送完成后，服务端会自动打印，无需手动操作<br>
<b>支持格式：</b>PDF、DOCX、XLSX、图片等  |  两台电脑需在同一 WiFi 下
        """)
        help_layout.addWidget(help_text)
        layout.addWidget(help_group)

        # Supported types hint
        hint = QLabel("支持: PDF, DOCX, XLSX, DOC, XLS, TXT, CSV, PNG, JPG, BMP, TIFF, GIF")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

    def _load_saved_config(self):
        cfg = _load_config()
        if cfg.get("host"):
            self.ip_edit.setText(cfg["host"])
        if cfg.get("port"):
            self.port_spin.setValue(cfg["port"])

    def _browse(self):
        filters = (
            "支持的文件 (*.pdf *.docx *.xlsx *.doc *.xls *.txt *.csv "
            "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.gif);;"
            "所有文件 (*)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filters)
        if path:
            self.file_edit.setText(path)

    def _send(self):
        filepath = self.file_edit.text().strip()
        if not filepath:
            QMessageBox.warning(self, "提示", "请先选择文件")
            return

        host = self.ip_edit.text().strip()
        port = self.port_spin.value()
        _save_config(host, port)

        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.log_view.clear()
        self.log_view.appendPlainText(f"目标: {host}:{port}")

        self._sender = FileSenderThread(host, port, filepath, self)
        self._sender.progress.connect(self._on_progress)
        self._sender.log.connect(self._on_log)
        self._sender.done.connect(self._on_done)
        self._sender.start()

    def _cancel(self):
        if self._sender:
            self._sender.cancel()
            self._sender = None
        self._reset_ui()

    def _on_progress(self, sent: int, total: int):
        if total > 0:
            pct = int(sent / total * 100)
            self.progress.setValue(pct)
            self.progress.setFormat(f"{pct}% ({self._fmt_size(sent)} / {self._fmt_size(total)})")

    def _on_log(self, msg: str):
        self.log_view.appendPlainText(msg)

    def _on_done(self, success: bool):
        self._sender = None
        self._reset_ui()
        if success:
            self.progress.setValue(100)
            self.progress.setFormat("完成!")

    def _reset_ui(self):
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
