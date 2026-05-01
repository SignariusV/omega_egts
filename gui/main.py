# OMEGA_EGTS GUI
import sys
import asyncio
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.utils.theme import apply_theme


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window._loop = loop
    window.show()

    def stop_loop():
        loop.stop()

    app.aboutToQuit.connect(stop_loop)
    app.exec()


if __name__ == "__main__":
    main()