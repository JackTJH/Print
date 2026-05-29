"""Print manager: dispatches print jobs asynchronously."""

import os
import subprocess
import threading
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"}


def _do_print(filepath: str) -> bool:
    """Run in background thread to avoid any Qt threading issues."""
    path = Path(filepath)
    ext = path.suffix.lower()

    if not path.exists():
        return False

    # Images: mspaint /p (silent print)
    if ext in IMAGE_EXTS:
        try:
            subprocess.run(["mspaint", "/p", str(path)],
                           capture_output=True, timeout=30)
            return True
        except Exception:
            return False

    # Documents: try multiple print strategies
    # Strategy 1: os.startfile "print"
    try:
        os.startfile(str(path), "print")
        return True
    except Exception:
        pass

    # Strategy 2: cmd start /print
    try:
        subprocess.run(["cmd", "/c", "start", "", "/print", str(path)],
                       capture_output=True, timeout=30, shell=False)
        return True
    except Exception:
        pass

    # Strategy 3: PowerShell
    try:
        subprocess.run([
            "powershell", "-Command",
            f"Start-Process -FilePath '{str(path)}' -Verb Print"
        ], capture_output=True, timeout=30, shell=False)
        return True
    except Exception:
        pass

    # Strategy 4: just open the file
    try:
        os.startfile(str(path))
    except Exception:
        pass
    return False


class PrintManager(QObject):
    """Handles printing. All slot calls should arrive on main thread via Qt.QueuedConnection."""

    print_result = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[str] = []
        self._busy = False
        self._workers: list[threading.Thread] = []  # Keep refs so threads aren't GC'd

        # Poll queue every 500ms on the main thread
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_queue)
        self._timer.start(500)

    @pyqtSlot(str, str, str, str)
    def enqueue(self, filename: str, size: str, filetype: str, filepath: str):
        """Called from main thread via Qt.QueuedConnection from handler."""
        self._queue.append(filepath)

    def _poll_queue(self):
        """Timer callback — always runs on main thread."""
        if self._busy or not self._queue:
            return
        self._busy = True
        filepath = self._queue.pop(0)
        name = Path(filepath).name
        # Run actual print in a plain Python thread (no Qt objects)
        t = threading.Thread(target=self._run_print, args=(filepath, name), daemon=True)
        self._workers.append(t)
        t.start()

    def _run_print(self, filepath: str, name: str):
        """Runs in background thread."""
        success = _do_print(filepath)
        # Use signal to report result back to main thread
        self.print_result.emit(name, success)
        # Unblock via timer on main thread
        QTimer.singleShot(100, self._on_done)

    def _on_done(self):
        self._busy = False
        # Clean up finished threads
        self._workers = [t for t in self._workers if t.is_alive()]
