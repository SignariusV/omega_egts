# OMEGA_EGTS GUI
import sys
import qasync
import asyncio
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.utils.theme import apply_theme

from core.python_logger import setup_python_logging

setup_python_logging(
    log_dir="logs",
    console_level="ERROR",
    file_level="DEBUG",
)


def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    app.aboutToQuit.connect(loop.stop)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
