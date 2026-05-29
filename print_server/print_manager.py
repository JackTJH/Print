"""Print manager: dispatches print jobs asynchronously via plain Python threads."""

import os
import queue
import subprocess
import threading
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, QTimer


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"}
PDF_EXT = ".pdf"


def _get_default_printer() -> str:
    """Get the default printer name."""
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except Exception:
        return ""


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
    """Print PDF using best available method."""

    # Method 1: win32api "printto" with default printer
    printer = _get_default_printer()
    if printer:
        try:
            import win32api
            result = win32api.ShellExecuteW(
                None, "printto", str(path), f'"{printer}"', None, 0)
            if result > 32:
                return True
        except Exception:
            pass

    # Method 2: Adobe Reader /t (silent print)
    adobe_paths = [
        r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
        r"C:\Program Files (x86)\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
        r"C:\Program Files\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
        r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
    ]
    for ap in adobe_paths:
        if os.path.exists(ap):
            try:
                subprocess.run([ap, "/t", str(path), printer],
                               capture_output=True, timeout=30)
                return True
            except Exception:
                pass

    # Method 3: os.startfile "print" (works if Adobe is default)
    try:
        os.startfile(str(path), "print")
        return True
    except Exception:
        pass

    # Method 4: cmd /c start /print
    try:
        subprocess.run(["cmd", "/c", "start", "", "/print", str(path)],
                       capture_output=True, timeout=30)
        return True
    except Exception:
        pass

    # Method 5: PowerShell Start-Process
    try:
        subprocess.run([
            "powershell", "-Command",
            f"Start-Process -FilePath '{str(path)}' -Verb Print"
        ], capture_output=True, timeout=30)
        return True
    except Exception:
        pass

    # Last resort: open file
    try:
        os.startfile(str(path))
    except Exception:
        pass
    return False


def _print_office(path: Path) -> bool:
    printer = _get_default_printer()
    if printer:
        try:
            import win32api
            result = win32api.ShellExecuteW(
                None, "printto", str(path), f'"{printer}"', None, 0)
            if result > 32:
                return True
        except Exception:
            pass

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
