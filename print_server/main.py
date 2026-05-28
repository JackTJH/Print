"""TCP Print Server entry point."""

import sys
from PyQt5.QtWidgets import QApplication

from .server_gui import ServerGUI


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ServerGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
