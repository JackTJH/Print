"""Print manager: dispatches print jobs asynchronously."""

import os
import subprocess
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"}


class PrintWorker(QThread):
    result = pyqtSignal(str, bool)

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath

    def run(self):
        path = Path(self.filepath)
        name = path.name
        ext = path.suffix.lower()

        if not path.exists():
            self.result.emit(name, False)
            return

        try:
            if ext in IMAGE_EXTS:
                self._print_image(path, name)
            else:
                self._print_document(path, name)
        except Exception:
            self.result.emit(name, False)

    def _print_image(self, path: Path, name: str):
        # mspaint /p 静默打印图片
        subprocess.run(["mspaint", "/p", str(path)],
                       capture_output=True, timeout=30)
        self.result.emit(name, True)

    def _print_document(self, path: Path, name: str):
        # 策略1: os.startfile "print"
        try:
            os.startfile(str(path), "print")
            self.result.emit(name, True)
            return
        except Exception:
            pass

        # 策略2: cmd start /print
        try:
            subprocess.run(["cmd", "/c", "start", "", "/print", str(path)],
                           capture_output=True, timeout=30)
            self.result.emit(name, True)
            return
        except Exception:
            pass

        # 策略3: PowerShell Start-Process -Verb Print
        try:
            subprocess.run([
                "powershell", "-Command",
                f"Start-Process -FilePath '{str(path)}' -Verb Print"
            ], capture_output=True, timeout=30)
            self.result.emit(name, True)
            return
        except Exception:
            pass

        # 策略4: 直接用默认程序打开
        os.startfile(str(path))
        self.result.emit(name, False)


class PrintManager(QObject):
    """Handles printing received files. Lives on the main thread."""

    print_result = pyqtSignal(str, bool)

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
        name = Path(filepath).name
        worker = PrintWorker(filepath, self)
        worker.result.connect(self._on_print_done)
        worker.start()

    def _on_print_done(self, filename: str, success: bool):
        self.print_result.emit(filename, success)
        self._busy = False
        QTimer.singleShot(100, self._process_next)
