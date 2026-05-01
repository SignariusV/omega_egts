# OMEGA_EGTS GUI
import sys
import qasync
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from gui.main_window import MainWindow
from gui.utils.theme import apply_theme


async def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    apply_theme(app)
    window = MainWindow()
    window.show()
    await qasync.qeventloop(app)


if __name__ == "__main__":
    qasync.run(main())