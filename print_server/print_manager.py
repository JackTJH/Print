"""Print manager: dispatches print jobs asynchronously."""

import os
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread


class PrintWorker(QThread):
    """Runs the actual print command in a background thread."""
    result = pyqtSignal(str, bool)  # filename, success

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

        # Try ShellExecute "print" via subprocess (non-blocking)
        try:
            subprocess.run(
                ["cmd", "/c", "start", "", "/min", "print", str(path)],
                capture_output=True, timeout=30, shell=False,
            )
            self.result.emit(name, True)
            return
        except Exception:
            pass

        # Fallback: os.startfile
        try:
            os.startfile(str(path), "print")
            self.result.emit(name, True)
        except Exception:
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
