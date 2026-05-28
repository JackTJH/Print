"""TCP Print Server entry point."""

import os
import sys
import traceback
from datetime import datetime

from PyQt5.QtWidgets import QApplication

from .server_gui import ServerGUI

CRASH_LOG = os.path.join(os.path.expanduser("~"), "Desktop", "print_server_crash.log")


def _log_exception(exc_type, exc_value, exc_tb):
    """Global exception hook — writes to desktop log file."""
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CRASH_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n=== CRASH {timestamp} ===\n{msg}\n")
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main():
    sys.excepthook = _log_exception
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ServerGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
