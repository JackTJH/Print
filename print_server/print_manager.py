"""Print manager: dispatches print jobs asynchronously via plain Python threads."""

import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, QTimer


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"}
PDF_EXT = ".pdf"


def _do_print(filepath: str) -> bool:
    path = Path(filepath)
    ext = path.suffix.lower()

    if not path.exists():
        return False

    if ext in IMAGE_EXTS:
        return _print_image(path)

    if ext == PDF_EXT:
        return _print_pdf(path)

    return _print_office(path)


def _print_image(path: Path) -> bool:
    try:
        subprocess.run(["mspaint", "/p", str(path)],
                       capture_output=True, timeout=30)
        return True
    except Exception:
        return False


def _print_pdf(path: Path) -> bool:
    """Print PDF: open in Edge, simulate Ctrl+P + Enter via SendInput."""
    import ctypes
    from ctypes import wintypes

    # Open the PDF in default handler (Edge)
    try:
        os.startfile(str(path))
    except Exception:
        return False

    time.sleep(3)  # Wait for Edge to open and load the PDF

    # Simulate Ctrl+P to open print dialog
    # Then Enter to confirm print
    VK_CONTROL = 0x11
    VK_P = 0x50
    VK_RETURN = 0x0D
    KEYEVENTF_KEYUP = 0x0002

    user32 = ctypes.windll.user32

    def press(key):
        user32.keybd_event(key, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)

    # Ctrl+P
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.1)
    press(VK_P)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(1.5)  # Wait for print dialog

    # Enter to confirm
    press(VK_RETURN)
    time.sleep(3)  # Wait for print to complete

    return True


def _print_office(path: Path) -> bool:
    """Print Word/Excel documents via ShellExecute."""
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
        os.startfile(str(path))
    except Exception:
        pass
    return False


class PrintManager(QObject):
    print_result = pyqtSignal(str, bool)

    def __init__(self, print_queue: queue.Queue, parent=None):
        super().__init__(parent)
        self._queue = print_queue
        self._busy = False
        self._done = False
        self._result = ("", False)
        self._workers: list[threading.Thread] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_queue)
        self._timer.start(500)

    def _poll_queue(self):
        if self._busy and self._done:
            name, success = self._result
            self.print_result.emit(name, success)
            self._done = False
            self._busy = False
            self._workers = [t for t in self._workers if t.is_alive()]

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
        self._result = (name, success)
        self._done = True
