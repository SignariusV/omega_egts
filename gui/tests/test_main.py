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