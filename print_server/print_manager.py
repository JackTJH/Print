"""Print manager: dispatches print jobs asynchronously via plain Python threads."""

import os
import queue
import subprocess
import threading
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, QTimer


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"}


def _do_print(filepath: str) -> bool:
    """Run in background thread — no Qt objects at all."""
    path = Path(filepath)
    ext = path.suffix.lower()

    if not path.exists():
        return False

    if ext in IMAGE_EXTS:
        try:
            subprocess.run(["mspaint", "/p", str(path)],
                           capture_output=True, timeout=30)
            return True
        except Exception:
            return False

    try:
        os.startfile(str(path), "print")
        return True
    except Exception:
        pass

    try:
        subprocess.run(["cmd", "/c", "start", "", "/print", str(path)],
                       capture_output=True, timeout=30)
        return True
    except Exception:
        pass

    try:
        subprocess.run([
            "powershell", "-Command",
            f"Start-Process -FilePath '{str(path)}' -Verb Print"
        ], capture_output=True, timeout=30)
        return True
    except Exception:
        pass

    try:
        os.startfile(str(path))
    except Exception:
        pass
    return False


class PrintManager(QObject):
    """Polls a thread-safe queue for print jobs. No cross-thread Qt signals needed."""

    print_result = pyqtSignal(str, bool)

    def __init__(self, print_queue: queue.Queue, parent=None):
        super().__init__(parent)
        self._queue = print_queue
        self._busy = False
        self._workers: list[threading.Thread] = []

        # Poll the shared queue every 500ms on the main thread
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_queue)
        self._timer.start(500)

    def _poll_queue(self):
        """Always runs on the main thread via QTimer."""
        # Check if current print job finished
        if self._busy and getattr(self, '_done', False):
            name, success = self._result
            self.print_result.emit(name, success)
            self._done = False
            self._busy = False
            self._workers = [t for t in self._workers if t.is_alive()]

        # Start next job if idle
        if self._busy:
            return
        try:
            filename, size, filetype, filepath = self._queue.get_nowait()
        except queue.Empty:
            return
        self._busy = True
        self._done = False
        t = threading.Thread(target=self._run_print,
                             args=(filepath, filename), daemon=True)
        self._workers.append(t)
        t.start()

    def _run_print(self, filepath: str, name: str):
        success = _do_print(filepath)
        # Store result; poll timer will pick it up on main thread
        self._result = (name, success)
        self._done = True

