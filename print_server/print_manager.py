"""Print manager: dispatches print jobs via Windows ShellExecute."""

import os
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

from common.constants import DIRECT_PRINT_TYPES, IMAGE_TYPES


class PrintManager(QObject):
    """Handles printing received files. Lives on the main thread."""

    print_result = pyqtSignal(str, bool)  # filename, success
    log = pyqtSignal(str, str, str)       # time, client, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[str] = []
        self._busy = False

    @pyqtSlot(str, str, str, str)
    def enqueue(self, filename: str, size: str, filetype: str, filepath: str):
        """Enqueue a file for printing."""
        self._queue.append(filepath)
        self._process_next()

    def _process_next(self):
        if self._busy or not self._queue:
            return
        self._busy = True
        filepath = self._queue.pop(0)
        name = Path(filepath).name
        success = self._print_file(filepath)
        self.print_result.emit(name, success)
        # Small delay before next print to avoid overwhelming the spooler
        QTimer.singleShot(500, self._on_print_done)

    def _on_print_done(self):
        self._busy = False
        self._process_next()

    def _print_file(self, filepath: str) -> bool:
        """Print a single file. Returns True if dispatched successfully."""
        path = Path(filepath)
        ext = path.suffix.lower()

        if not path.exists():
            return False

        try:
            if ext in IMAGE_TYPES:
                self._validate_image(path)

            import win32api
            result = win32api.ShellExecuteW(
                None, "print", str(path), None, None, 0
            )
            if result <= 32:
                # ShellExecute error
                error_msgs = {
                    2: "文件未找到", 3: "路径未找到", 5: "拒绝访问",
                    8: "内存不足", 31: "没有关联的应用程序",
                }
                msg = error_msgs.get(result, f"错误码 {result}")
                self.log.emit("", path.name, f"打印失败: {msg}")
                return False
            return True
        except ImportError:
            # Fallback: os.startfile
            os.startfile(str(path), "print")
            return True
        except Exception as e:
            self.log.emit("", path.name, f"打印异常: {e}")
            return False

    def _validate_image(self, path: Path):
        """Validate image integrity using Pillow."""
        try:
            from PIL import Image
            img = Image.open(path)
            img.verify()
        except Exception:
            pass  # Non-critical if Pillow not available
