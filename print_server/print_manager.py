"""Print manager: dispatches print jobs asynchronously via plain Python threads."""

import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, QTimer


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"}
PDF_EXT = ".pdf"


def _find_edge() -> str | None:
    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    try:
        result = subprocess.run(["where", "msedge"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except Exception:
        pass
    return None


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
    """Print PDF via Edge --kiosk-printing (silent, no popup)."""
    edge = _find_edge()
    if not edge:
        try:
            os.startfile(str(path), "print")
        except Exception:
            pass
        return False

    # HTML wrapper: embed PDF and call window.print() after loading
    file_url = str(path).replace("\\", "/")
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Print</title></head>
<body style="margin:0;overflow:hidden">
<embed src="file:///{file_url}" type="application/pdf"
 style="position:fixed;top:0;left:0;width:100%;height:100%">
<script>
let c=0;
let t=setInterval(()=>{{
 if(++c>8){{window.print();clearInterval(t);setTimeout(()=>{{window.close();}},6000);}}
}},500);
</script>
</body></html>"""

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html",
                                         delete=False, encoding="utf-8") as f:
            f.write(html)
            html_path = f.name

        subprocess.Popen(
            [edge, "--kiosk-printing", f"file:///{html_path.replace(chr(92), '/')}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(10)
        try:
            os.unlink(html_path)
        except Exception:
            pass
        return True
    except Exception:
        return False


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
