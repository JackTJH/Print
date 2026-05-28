"""Print manager: dispatches print jobs asynchronously."""

import os
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

        if not path.exists():
            self.result.emit(name, False)
            return

        try:
            os.startfile(str(path), "print")
            self.result.emit(name, True)
        except Exception as e:
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
