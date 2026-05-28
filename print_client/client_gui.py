"""Client main window (PyQt5)."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QPushButton, QPlainTextEdit,
    QProgressBar, QFileDialog, QGroupBox, QMessageBox,
)

from common.constants import DEFAULT_PORT
from .file_sender import FileSenderThread


class ClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("打印客户端")
        self.setMinimumSize(550, 400)
        self._sender: FileSenderThread | None = None

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        # ---- Server Connection ----
        conn_group = QGroupBox("服务器连接")
        conn_layout = QHBoxLayout(conn_group)

        conn_layout.addWidget(QLabel("IP:"))
        self.ip_edit = QLineEdit("192.168.")
        self.ip_edit.setFixedWidth(140)
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
        self.send_btn.setFixedHeight(32)
        self.send_btn.clicked.connect(self._send)
        action_layout.addWidget(self.send_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.clicked.connect(self._cancel)
        action_layout.addWidget(self.cancel_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        # ---- Progress ----
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # ---- Log ----
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

        # Supported types hint
        hint = QLabel("支持: PDF, DOCX, XLSX, DOC, XLS, TXT, CSV, PNG, JPG, BMP, TIFF, GIF")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

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

        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.log_view.clear()

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
            QMessageBox.information(self, "完成", "文件已发送成功，服务端正在打印。")

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
