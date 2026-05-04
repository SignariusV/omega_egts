# OMEGA_EGTS GUI
import sys
import qasync
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.utils.theme import apply_theme


def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    loop = qasync.QEventLoop(app)
    loop.run_forever()


if __name__ == "__main__":
    main()