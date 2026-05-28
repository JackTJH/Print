"""Print manager: dispatches print jobs via Windows ShellExecute."""

import os
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

from common.constants import DIRECT_PRINT_TYPES, IMAGE_TYPES


class PrintManager(QObject):
    """Handles printing received files. Lives on the main thread."""

    print_result = pyqtSignal(str, bool)
    log = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[str] = []
        self._busy = False

    @pyqtSlot(str, str, str, str)
    def enqueue(self, filename: str, size: str, filetype: str, filepath: str):
        self._queue.append(filepath)
        self._process_next()

    def _process_next(self):
        if self._busy or not self._queue:
            return
        self._busy = True
        filepath = self._queue.pop(0)
        try:
            name = Path(filepath).name
            success = self._print_file(filepath)
            self.print_result.emit(name, success)
        except Exception as e:
            self.log.emit("", Path(filepath).name, f"打印异常: {e}")
        QTimer.singleShot(500, self._on_print_done)

    def _on_print_done(self):
        self._busy = False
        self._process_next()

    def _print_file(self, filepath: str) -> bool:
        path = Path(filepath)
        ext = path.suffix.lower()

        if not path.exists():
            self.log.emit("", path.name, "打印失败: 文件不存在")
            return False

        # Strategy 1: win32api.ShellExecute "print"
        try:
            import win32api
            result = win32api.ShellExecuteW(
                None, "print", str(path), None, None, 0
            )
            if result > 32:
                self.log.emit("", path.name, "已发送打印指令")
                return True
            # ShellExecute failed, log and fall through to fallback
            error_codes = {
                2: "文件未找到", 3: "路径未找到", 5: "拒绝访问",
                8: "内存不足", 26: "共享冲突", 29: "设备忙",
                31: "没有关联的程序", 32: "DLL 未找到",
            }
            err_msg = error_codes.get(result, f"错误码 {result}")
            self.log.emit("", path.name, f"ShellExecute 失败 ({err_msg})，尝试备用方式...")
        except ImportError:
            self.log.emit("", path.name, "pywin32 未安装，使用备用方式...")

        # Strategy 2: os.startfile "print"
        try:
            os.startfile(str(path), "print")
            self.log.emit("", path.name, "已发送打印指令 (startfile)")
            return True
        except Exception as e:
            self.log.emit("", path.name, f"startfile 失败: {e}")

        return False
