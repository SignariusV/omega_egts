# OMEGA_EGTS GUI
import sys
import qasync
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.utils.theme import apply_theme


async def main():
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    await qasync.qeventloop(app)


if __name__ == "__main__":
    qasync.run(main())