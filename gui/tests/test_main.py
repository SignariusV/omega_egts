# OMEGA_EGTS GUI
import pytest
from gui.main_window import MainWindow


@pytest.fixture
def app(qtbot):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


def test_main_window_opens(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()


def test_cmw_error_shown_in_statusbar(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window._event_bridge.cmw_error.emit("Test error message")

    assert window._status_bar.currentMessage() == "CMW Error: Test error message"


def test_command_error_shown_in_statusbar(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window._event_bridge.command_error.emit({"error": "Command failed"})

    assert window._status_bar.currentMessage() == "Command Error: {'error': 'Command failed'}"