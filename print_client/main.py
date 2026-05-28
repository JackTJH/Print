"""TCP Print Client entry point."""

import sys
from PyQt5.QtWidgets import QApplication

from .client_gui import ClientGUI


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ClientGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
